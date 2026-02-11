"""Gold-A → Gold-B IR generation (RFC-E2E-PIPELINE-006 §4).

Derives IR (Intermediate Representation) assets from SSOT masters.
Each IR is versioned and reproducible. IR ≠ SSOT — can be regenerated.

v1 builders: Phase A-G (16-week MVP)
v2 builders: Phase H (SOTA — Expert-Aware + Temporal IR Enhancement)
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from wine_rec.common.io import write_parquet_atomic
from wine_rec.common.logging import get_logger
from wine_rec.pipeline.temporal_estimator import (
    compute_current_stage,
    compute_peak_trajectory,
    estimate_rule_based,
    merge_estimates,
)


log = get_logger(__name__)

# Expert authority weights (RFC-REC-EXT-004 §2-1)
AUTHORITY_WEIGHTS: dict[str, float] = {
    "critic": 3.0,
    "expert": 2.0,
    "user": 1.0,
    "anonymous": 0.5,
}

# Half-life in days for review freshness decay (2 years)
REVIEW_DECAY_HALF_LIFE_DAYS: float = 730.0

# Consensus category thresholds
_CONSENSUS_HIGH: float = 0.01
_CONSENSUS_MODERATE: float = 0.05
_MIN_REVIEWERS_FOR_CONSENSUS: int = 3


def build_review_aggregate_ir(
    reviews: pl.DataFrame,
    cores: pl.DataFrame,
    as_of_ts: str | None = None,
) -> pl.DataFrame:
    """Build wine_review_aggregate_ir_v1.

    Expert-aware aggregate: weights by author_type,
    critic_consensus_score = 1 / (variance + epsilon).

    Args:
        as_of_ts: ISO timestamp for reproducibility. If None, uses current time.
                  For offline training, pass the training event boundary.
    """
    as_of = as_of_ts or datetime.now(UTC).isoformat()

    # normalize ratings to 0-1 scale
    scale_map = {"100": 100.0, "20": 20.0, "5": 5.0}
    reviews_norm = reviews.with_columns(
        (pl.col("rating") / pl.col("rating_scale").replace_strict(scale_map, default=5.0)).alias(
            "rating_normalized"
        ),
        pl.col("author_type")
        .replace_strict(AUTHORITY_WEIGHTS, default=1.0)
        .alias("authority_weight"),
    )

    # weighted aggregates per wine_core_id
    agg = reviews_norm.group_by("wine_core_id").agg(
        # weighted mean
        (pl.col("rating_normalized") * pl.col("authority_weight")).sum().alias("_weighted_sum"),
        pl.col("authority_weight").sum().alias("_weight_total"),
        pl.col("authority_weight").sum().cast(pl.Int64).alias("authority_weighted_count"),
        # variance for consensus
        pl.col("rating_normalized").var().alias("_rating_var"),
        pl.len().alias("review_count"),
    )

    ir = agg.with_columns(
        (pl.col("_weighted_sum") / pl.col("_weight_total").clip(lower_bound=0.01))
        .round(4)
        .alias("weighted_rating_mean"),
        (1.0 / (pl.col("_rating_var").fill_null(1.0) + 0.01))
        .round(4)
        .alias("critic_consensus_score"),
        pl.when(pl.col("_rating_var") > 0.05)
        .then(pl.lit("High variance among reviewers"))
        .otherwise(pl.lit(None))
        .alias("discrepancy_note"),
        pl.lit(as_of).alias("as_of_ts"),
    ).select(
        "wine_core_id",
        "weighted_rating_mean",
        "authority_weighted_count",
        "critic_consensus_score",
        "discrepancy_note",
        "as_of_ts",
    )

    # ensure all cores are represented
    return (
        cores.select("wine_core_id")
        .join(ir, on="wine_core_id", how="left")
        .with_columns(
            pl.col("weighted_rating_mean").fill_null(0.0),
            pl.col("authority_weighted_count").fill_null(0),
            pl.col("critic_consensus_score").fill_null(0.0),
            pl.col("as_of_ts").fill_null(as_of),
        )
    )


def build_temporal_ir(
    cores: pl.DataFrame,
    skus: pl.DataFrame,
    reference_year: int = 2026,
    as_of_ts: str | None = None,
) -> pl.DataFrame:
    """Build wine_temporal_ir_v1.

    Drinking window estimation based on vintage year and wine type.
    Rule-based for now; model-based in Phase E.

    Args:
        as_of_ts: ISO timestamp for reproducibility. If None, uses current time.
    """
    as_of = as_of_ts or datetime.now(UTC).isoformat()

    # join cores with skus to get vintage info
    vintage_info = (
        skus.filter(pl.col("vintage_year").is_not_null())
        .group_by("wine_core_id")
        .agg(pl.col("vintage_year").median().cast(pl.Int64).alias("vintage_year"))
    )

    core_with_vintage = cores.join(vintage_info, on="wine_core_id", how="left")

    # rule-based drinking window by wine type
    def _drinking_window(wine_type: str) -> tuple[int, int]:
        windows = {
            "red": (3, 12),
            "white": (1, 5),
            "sparkling": (1, 8),
            "rosé": (1, 3),
            "fortified": (5, 30),
            "dessert": (3, 20),
        }
        return windows.get(wine_type, (2, 8))

    rows = []
    for row in core_with_vintage.to_dicts():
        vintage = row.get("vintage_year")
        if vintage is None:
            vintage = reference_year - 3  # assume 3 years old

        wine_type = row.get("wine_type", "red")
        min_age, max_age = _drinking_window(wine_type)
        drink_from = vintage + min_age
        drink_to = vintage + max_age

        if reference_year < drink_from:
            stage = "too_young"
            confidence = 0.7
        elif reference_year <= drink_to:
            mid = (drink_from + drink_to) / 2
            if reference_year < mid:
                stage = "early"
                confidence = 0.6
            else:
                stage = "peak"
                confidence = 0.8
        else:
            stage = "past"
            confidence = 0.5

        rows.append(
            {
                "wine_core_id": row["wine_core_id"],
                "vintage_year": vintage,
                "drink_from_year": drink_from,
                "drink_to_year": drink_to,
                "current_stage": stage,
                "estimation_method": "rule",
                "confidence": round(confidence, 2),
                "as_of_ts": as_of,
            }
        )

    return pl.DataFrame(rows)


def build_scarcity_ir(
    cores: pl.DataFrame,
    reviews: pl.DataFrame,
) -> pl.DataFrame:
    """Build wine_scarcity_ir_v1.

    Proxy rarity from review count + producer prestige signals.
    Fewer reviews → higher rarity (as a heuristic).
    """
    review_counts = reviews.group_by("wine_core_id").agg(
        pl.len().alias("review_count"),
    )

    scored = (
        cores.select("wine_core_id")
        .join(review_counts, on="wine_core_id", how="left")
        .with_columns(pl.col("review_count").fill_null(0))
    )

    # inverse log scaling: fewer reviews → higher rarity
    max_reviews = int(scored["review_count"].max() or 1)  # type: ignore[arg-type]
    max_log = max(math.log1p(max_reviews), 0.01)
    scored = scored.with_columns(
        (1.0 - (pl.col("review_count").log1p() / max_log).clip(upper_bound=1.0))
        .round(3)
        .alias("rarity_score"),
        pl.lit(None).cast(pl.Int64).alias("production_volume_est"),
        pl.lit("global").alias("market_scope"),
        pl.lit("scarcity_v1").alias("scarcity_version"),
    )

    return scored.select(
        "wine_core_id",
        "production_volume_est",
        "rarity_score",
        "market_scope",
        "scarcity_version",
    )


# ── v2 builders (Phase H: SOTA) ────────────────────────────


def build_review_aggregate_ir_v2(
    reviews: pl.DataFrame,
    cores: pl.DataFrame,
    *,
    as_of_ts: str | None = None,
    decay_half_life_days: float = REVIEW_DECAY_HALF_LIFE_DAYS,
) -> pl.DataFrame:
    """Build wine_review_aggregate_ir_v2 with temporal decay + variance decomposition.

    Backward-compatible: includes all v1 fields plus new expert-aware features.
    All computation is Polars-vectorized (no Python loops).
    """
    as_of = as_of_ts or datetime.now(UTC).isoformat()
    ln2 = math.log(2)

    # normalize ratings to 0-1 scale
    scale_map = {"100": 100.0, "20": 20.0, "5": 5.0}
    reviews_norm = reviews.with_columns(
        (pl.col("rating") / pl.col("rating_scale").replace_strict(scale_map, default=5.0)).alias(
            "rating_normalized"
        ),
        pl.col("author_type")
        .replace_strict(AUTHORITY_WEIGHTS, default=1.0)
        .alias("authority_weight"),
    )

    # Temporal decay: exp(-ln2 * days_since / half_life)
    ref_ts = pl.lit(as_of).str.to_datetime(format="%Y-%m-%dT%H:%M:%S%Z").cast(pl.Date)
    reviews_norm = reviews_norm.with_columns(
        (
            (
                -ln2
                * (ref_ts - pl.col("published_at").cast(pl.Date)).dt.total_days()
                / decay_half_life_days
            ).exp()
        )
        .clip(lower_bound=0.01, upper_bound=1.0)
        .alias("decay_factor"),
    )

    reviews_norm = reviews_norm.with_columns(
        (pl.col("authority_weight") * pl.col("decay_factor")).alias("combined_weight"),
    )

    # ── Per-wine aggregates ──

    # v1-compatible fields
    agg = reviews_norm.group_by("wine_core_id").agg(
        # v1 weighted mean (no decay)
        (pl.col("rating_normalized") * pl.col("authority_weight")).sum().alias("_weighted_sum"),
        pl.col("authority_weight").sum().alias("_weight_total"),
        pl.col("authority_weight").sum().cast(pl.Int64).alias("authority_weighted_count"),
        pl.col("rating_normalized").var().alias("_rating_var"),
        # v2 decay-weighted mean
        (pl.col("rating_normalized") * pl.col("combined_weight"))
        .sum()
        .alias("_decay_weighted_sum"),
        pl.col("combined_weight").sum().alias("_combined_weight_total"),
        pl.col("combined_weight").mean().alias("_avg_combined_weight"),
        # reviewer count
        pl.col("author_id").n_unique().alias("_n_reviewers"),
        pl.len().alias("review_count"),
    )

    # ── Inter-expert variance: variance of per-author mean ratings ──
    author_means = reviews_norm.group_by("wine_core_id", "author_id").agg(
        pl.col("rating_normalized").mean().alias("author_mean")
    )
    inter_var = author_means.group_by("wine_core_id").agg(
        pl.col("author_mean").var().alias("inter_expert_variance")
    )

    # ── Intra-expert variance: avg of within-author variance ──
    author_var = (
        reviews_norm.group_by("wine_core_id", "author_id")
        .agg(pl.col("rating_normalized").var().alias("author_var"))
        .filter(pl.col("author_var").is_not_null())
    )
    intra_var = author_var.group_by("wine_core_id").agg(
        pl.col("author_var").mean().alias("intra_expert_variance")
    )

    # ── Expert agreement: fraction within 0.1 of weighted mean ──
    # Compute weighted mean per wine first
    wine_means = agg.select(
        "wine_core_id",
        (pl.col("_weighted_sum") / pl.col("_weight_total").clip(lower_bound=0.01)).alias("_wmean"),
    )
    reviews_with_mean = reviews_norm.join(wine_means, on="wine_core_id", how="left")
    agreement_df = reviews_with_mean.group_by("wine_core_id").agg(
        ((pl.col("rating_normalized") - pl.col("_wmean")).abs() <= 0.1)
        .mean()
        .alias("expert_agreement_pct"),
    )

    # ── Assemble v2 IR ──
    ir = (
        agg.join(inter_var, on="wine_core_id", how="left")
        .join(intra_var, on="wine_core_id", how="left")
        .join(agreement_df, on="wine_core_id", how="left")
    )

    ir = ir.with_columns(
        # v1 fields
        (pl.col("_weighted_sum") / pl.col("_weight_total").clip(lower_bound=0.01))
        .round(4)
        .alias("weighted_rating_mean"),
        (1.0 / (pl.col("_rating_var").fill_null(1.0) + 0.01))
        .round(4)
        .alias("critic_consensus_score"),
        # v2 fields
        (pl.col("_decay_weighted_sum") / pl.col("_combined_weight_total").clip(lower_bound=0.01))
        .round(4)
        .alias("decay_weighted_rating_mean"),
        pl.col("_avg_combined_weight").round(4).alias("authority_decay_score"),
        pl.col("inter_expert_variance").fill_null(0.0).round(4),
        pl.col("intra_expert_variance").fill_null(0.0).round(4),
        pl.col("expert_agreement_pct").fill_null(0.0).round(4),
        # Consensus category
        pl.when(pl.col("_n_reviewers") < _MIN_REVIEWERS_FOR_CONSENSUS)
        .then(pl.lit("insufficient"))
        .when(pl.col("inter_expert_variance").fill_null(0.0) < _CONSENSUS_HIGH)
        .then(pl.lit("high_agreement"))
        .when(pl.col("inter_expert_variance").fill_null(0.0) < _CONSENSUS_MODERATE)
        .then(pl.lit("moderate"))
        .otherwise(pl.lit("controversial"))
        .alias("consensus_category"),
        # Discrepancy note
        pl.when(pl.col("_rating_var") > 0.05)
        .then(pl.lit("High variance among reviewers"))
        .otherwise(pl.lit(None))
        .alias("discrepancy_note"),
        pl.lit(as_of).alias("as_of_ts"),
    )

    ir = ir.select(
        "wine_core_id",
        "weighted_rating_mean",
        "authority_weighted_count",
        "critic_consensus_score",
        "decay_weighted_rating_mean",
        "authority_decay_score",
        "inter_expert_variance",
        "intra_expert_variance",
        "consensus_category",
        "expert_agreement_pct",
        "discrepancy_note",
        "as_of_ts",
    )

    # ensure all cores are represented
    return (
        cores.select("wine_core_id")
        .join(ir, on="wine_core_id", how="left")
        .with_columns(
            pl.col("weighted_rating_mean").fill_null(0.0),
            pl.col("authority_weighted_count").fill_null(0),
            pl.col("critic_consensus_score").fill_null(0.0),
            pl.col("decay_weighted_rating_mean").fill_null(0.0),
            pl.col("authority_decay_score").fill_null(0.0),
            pl.col("inter_expert_variance").fill_null(0.0),
            pl.col("intra_expert_variance").fill_null(0.0),
            pl.col("consensus_category").fill_null("insufficient"),
            pl.col("expert_agreement_pct").fill_null(0.0),
            pl.col("as_of_ts").fill_null(as_of),
        )
    )


def build_expert_profile_ir(
    reviews: pl.DataFrame,
    cores: pl.DataFrame,
    *,
    as_of_ts: str | None = None,
    specialization_threshold: int = 5,
) -> pl.DataFrame:
    """Build expert_profile_ir_v1 from review history.

    Per-author aggregates: review_count, avg_rating, variance,
    region coverage, authority score, specialization tags.
    """
    as_of = as_of_ts or datetime.now(UTC).isoformat()

    # Join reviews with cores to get region info
    reviews_with_region = reviews.join(
        cores.select("wine_core_id", "region"),
        on="wine_core_id",
        how="left",
    )

    # Per-author aggregates
    scale_map = {"100": 100.0, "20": 20.0, "5": 5.0}
    reviews_norm = reviews_with_region.with_columns(
        (pl.col("rating") / pl.col("rating_scale").replace_strict(scale_map, default=5.0)).alias(
            "rating_normalized"
        ),
    )

    author_agg = reviews_norm.group_by("author_id", "author_type").agg(
        pl.len().alias("review_count"),
        pl.col("rating_normalized").mean().round(4).alias("avg_rating_given"),
        pl.col("rating_normalized").var().fill_null(0.0).round(4).alias("rating_variance"),
        pl.col("region").drop_nulls().unique().alias("wine_region_coverage"),
    )

    # Region specialization: regions with >= threshold reviews
    region_counts = (
        reviews_norm.filter(pl.col("region").is_not_null())
        .group_by("author_id", "region")
        .agg(pl.len().alias("region_review_count"))
        .filter(pl.col("region_review_count") >= specialization_threshold)
        .group_by("author_id")
        .agg(pl.col("region").alias("specialization_tags"))
    )

    author_agg = author_agg.join(region_counts, on="author_id", how="left").with_columns(
        pl.col("specialization_tags").fill_null([]),
    )

    # Authority score: normalized composite of type weight + count + consistency
    _max_raw = author_agg["review_count"].max()
    max_count = max(int(_max_raw) if isinstance(_max_raw, (int, float)) else 1, 1)
    author_agg = author_agg.with_columns(
        pl.col("author_type").replace_strict(AUTHORITY_WEIGHTS, default=1.0).alias("_type_weight"),
    ).with_columns(
        (
            (pl.col("_type_weight") / 3.0) * 0.4
            + (pl.col("review_count").log1p() / math.log1p(max_count)).clip(upper_bound=1.0) * 0.3
            + (1.0 - pl.col("rating_variance").clip(upper_bound=1.0)) * 0.3
        )
        .clip(lower_bound=0.0, upper_bound=1.0)
        .round(4)
        .alias("authority_score"),
    )

    return author_agg.with_columns(pl.lit(as_of).alias("as_of_ts")).select(
        "author_id",
        "author_type",
        "review_count",
        "wine_region_coverage",
        "avg_rating_given",
        "rating_variance",
        "authority_score",
        "specialization_tags",
        "as_of_ts",
    )


def build_temporal_ir_v2(
    cores: pl.DataFrame,
    skus: pl.DataFrame,
    *,
    reference_year: int = 2026,
    as_of_ts: str | None = None,
) -> pl.DataFrame:
    """Build wine_temporal_ir_v2 with multi-method estimation + peak trajectory.

    Currently uses rule-based estimation only. Model-based estimation is
    called but returns None (graceful fallback), ready for Phase H+ ML models.
    """
    as_of = as_of_ts or datetime.now(UTC).isoformat()

    # join cores with skus to get vintage info
    vintage_info = (
        skus.filter(pl.col("vintage_year").is_not_null())
        .group_by("wine_core_id")
        .agg(pl.col("vintage_year").median().cast(pl.Int64).alias("vintage_year"))
    )

    core_with_vintage = cores.join(vintage_info, on="wine_core_id", how="left")

    rows: list[dict[str, object]] = []
    for row in core_with_vintage.to_dicts():
        vintage = row.get("vintage_year")
        if vintage is None:
            vintage = reference_year - 3

        wine_type = row.get("wine_type", "red")

        # Rule-based estimate
        rule_est = estimate_rule_based(
            wine_type=str(wine_type),
            vintage_year=int(vintage),
            reference_year=reference_year,
        )

        # Merge (currently only rule-based; model/expert return None)
        merged = merge_estimates([rule_est])

        stage = compute_current_stage(
            drink_from_year=merged.drink_from_year,
            drink_to_year=merged.drink_to_year,
            reference_year=reference_year,
        )

        trajectory, days_to_peak = compute_peak_trajectory(
            drink_from_year=merged.drink_from_year,
            drink_to_year=merged.drink_to_year,
            reference_year=reference_year,
        )

        rows.append(
            {
                "wine_core_id": row["wine_core_id"],
                "vintage_year": int(vintage),
                "drink_from_year": merged.drink_from_year,
                "drink_to_year": merged.drink_to_year,
                "current_stage": stage,
                "estimation_method": merged.method,
                "rule_confidence": rule_est.confidence,
                "model_confidence": None,
                "expert_confidence": None,
                "merged_confidence": merged.confidence,
                "peak_trajectory": trajectory,
                "days_to_peak": days_to_peak,
                "vintage_effect_score": 0.0,
                "as_of_ts": as_of,
            }
        )

    return pl.DataFrame(rows)


def run_gold_a_to_gold_b(
    *, input_path: str, output_path: str, dt: str, as_of_ts: str | None = None
) -> dict[str, int]:
    """Generate IR derived assets from SSOT masters.

    Args:
        input_path: Gold-A root path (masters)
        output_path: Gold-B output root path
        dt: Processing date
        as_of_ts: ISO timestamp for IR reproducibility. Defaults to dt value.

    Returns:
        Dict mapping IR table name to row count.
    """
    gold_a = Path(input_path)
    gold_b = Path(output_path)
    results: dict[str, int] = {}

    # load masters
    cores_path = gold_a / "wine_core_master_v1" / "data.parquet"
    skus_path = gold_a / "wine_sku_master_v1" / "data.parquet"
    reviews_path = gold_a / "review_master_v1" / "data.parquet"

    if not cores_path.exists():
        log.warning("missing_masters", msg="No wine_core_master found")
        return results

    cores = pl.read_parquet(cores_path)
    skus = pl.read_parquet(skus_path) if skus_path.exists() else pl.DataFrame()
    reviews = pl.read_parquet(reviews_path) if reviews_path.exists() else pl.DataFrame()

    ir_ts = as_of_ts or f"{dt}T00:00:00Z"

    # 1. Review Aggregate IR
    log.info("building_review_aggregate_ir")
    review_agg = build_review_aggregate_ir(reviews, cores, as_of_ts=ir_ts)
    _write_ir(review_agg, gold_b / "wine_review_aggregate_ir_v1" / f"dt={dt}" / "data.parquet")
    results["wine_review_aggregate_ir_v1"] = len(review_agg)

    # 2. Temporal IR
    log.info("building_temporal_ir")
    temporal = build_temporal_ir(cores, skus, as_of_ts=ir_ts)
    _write_ir(temporal, gold_b / "wine_temporal_ir_v1" / f"dt={dt}" / "data.parquet")
    results["wine_temporal_ir_v1"] = len(temporal)

    # 3. Scarcity IR
    log.info("building_scarcity_ir")
    scarcity = build_scarcity_ir(cores, reviews)
    _write_ir(scarcity, gold_b / "wine_scarcity_ir_v1" / f"dt={dt}" / "data.parquet")
    results["wine_scarcity_ir_v1"] = len(scarcity)

    # ── v2 IRs (Phase H: SOTA) ──

    # 4. Review Aggregate IR v2
    if len(reviews) > 0 and "published_at" in reviews.columns:
        log.info("building_review_aggregate_ir_v2")
        review_agg_v2 = build_review_aggregate_ir_v2(reviews, cores, as_of_ts=ir_ts)
        _write_ir(
            review_agg_v2,
            gold_b / "wine_review_aggregate_ir_v2" / f"dt={dt}" / "data.parquet",
        )
        results["wine_review_aggregate_ir_v2"] = len(review_agg_v2)

        # 5. Expert Profile IR
        log.info("building_expert_profile_ir")
        expert_profiles = build_expert_profile_ir(reviews, cores, as_of_ts=ir_ts)
        _write_ir(
            expert_profiles,
            gold_b / "expert_profile_ir_v1" / f"dt={dt}" / "data.parquet",
        )
        results["expert_profile_ir_v1"] = len(expert_profiles)

    # 6. Temporal IR v2
    log.info("building_temporal_ir_v2")
    temporal_v2 = build_temporal_ir_v2(cores, skus, as_of_ts=ir_ts)
    _write_ir(
        temporal_v2,
        gold_b / "wine_temporal_ir_v2" / f"dt={dt}" / "data.parquet",
    )
    results["wine_temporal_ir_v2"] = len(temporal_v2)

    log.info("gold_a_to_gold_b_done", results=results)
    return results


def _write_ir(df: pl.DataFrame, path: Path) -> None:
    write_parquet_atomic(df, path)
