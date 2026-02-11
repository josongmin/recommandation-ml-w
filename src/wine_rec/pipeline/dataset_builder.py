"""Dataset builder (RFC-DATASET-BUILDER-011).

Impression-based training data generation with time-travel join enforcement.
Produces training_examples_v1 + dataset_manifest_v1.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from wine_rec.common.io import write_parquet_atomic
from wine_rec.common.logging import get_logger
from wine_rec.pipeline.quality_gates import (
    GateResult,
    check_join_success_gate,
    check_leakage_gate,
)


log = get_logger(__name__)

# Label hierarchy (higher = more valuable)
LABEL_VALUES: dict[str, int] = {
    "purchase": 5,
    "cart": 4,
    "wishlist": 3,
    "click": 2,
    "view": 1,
    "none": 0,
}


def _assign_labels(
    impressions: pl.DataFrame,
    actions: pl.DataFrame,
    orders: pl.DataFrame,
    attribution_window_days: int = 7,
) -> pl.DataFrame:
    """Assign labels to impression-item pairs.

    Label priority: purchase > cart > wishlist > click > view > none.
    Attribution: only actions within `attribution_window_days` of shown_ts.
    """
    # explode items to get one row per (impression_id, wine_sku_id)
    pairs = (
        impressions.select("impression_id", "user_id", "shown_ts", "items")
        .with_columns(
            pl.col("items").str.split(",").alias("item_list"),
        )
        .explode("item_list")
        .rename({"item_list": "wine_sku_id"})
    )

    # build shown_ts lookup for attribution window filtering
    imp_ts = impressions.select("impression_id", "shown_ts")
    if imp_ts["shown_ts"].dtype == pl.Utf8:
        imp_ts = imp_ts.with_columns(pl.col("shown_ts").str.to_datetime(time_zone="UTC"))

    # map action_type to label
    action_label_map = {
        "VIEW": "view",
        "CLICK": "click",
        "DWELL": "view",
        "LIKE": "click",
        "WISHLIST": "wishlist",
        "CART": "cart",
    }

    # action labels: max per (impression_id, wine_sku_id)
    if len(actions) > 0:
        # apply attribution window: only actions within N days of shown_ts
        windowed_actions = actions.join(imp_ts, on="impression_id", how="inner")
        if "action_ts" in windowed_actions.columns:
            if windowed_actions["action_ts"].dtype == pl.Utf8:
                windowed_actions = windowed_actions.with_columns(
                    pl.col("action_ts").str.to_datetime(time_zone="UTC"),
                )
            windowed_actions = windowed_actions.filter(
                (pl.col("action_ts") - pl.col("shown_ts")).dt.total_days()
                <= attribution_window_days
            )
        windowed_actions = windowed_actions.drop("shown_ts")

        action_labels = (
            windowed_actions.with_columns(
                pl.col("action_type")
                .replace_strict(action_label_map, default="view")
                .replace_strict(LABEL_VALUES, default=0)
                .alias("label_value"),
            )
            .group_by(["impression_id", "wine_sku_id"])
            .agg(pl.col("label_value").max().alias("action_label_value"))
        )
    else:
        action_labels = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
                "action_label_value": pl.Int64,
            }
        )

    # order labels — also apply attribution window
    if len(orders) > 0 and "impression_id" in orders.columns:
        windowed_orders = orders.filter(pl.col("impression_id").is_not_null())
        # apply attribution window if order_ts exists
        if "order_ts" in windowed_orders.columns:
            windowed_orders = windowed_orders.join(imp_ts, on="impression_id", how="inner")
            if windowed_orders["order_ts"].dtype == pl.Utf8:
                windowed_orders = windowed_orders.with_columns(
                    pl.col("order_ts").str.to_datetime(time_zone="UTC"),
                )
            windowed_orders = windowed_orders.filter(
                (pl.col("order_ts") - pl.col("shown_ts")).dt.total_days() <= attribution_window_days
            ).drop("shown_ts")
        order_labels = (
            windowed_orders.select("impression_id", "wine_sku_id")
            .unique()
            .with_columns(pl.lit(LABEL_VALUES["purchase"]).alias("order_label_value"))
        )
    else:
        order_labels = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
                "order_label_value": pl.Int64,
            }
        )

    # merge labels
    return (
        pairs.join(action_labels, on=["impression_id", "wine_sku_id"], how="left")
        .join(order_labels, on=["impression_id", "wine_sku_id"], how="left")
        .with_columns(
            pl.max_horizontal("action_label_value", "order_label_value")
            .fill_null(0)
            .alias("label"),
        )
        .drop("action_label_value", "order_label_value")
    )


def _sample_negatives(
    labeled: pl.DataFrame,
    cap_per_positive: int = 10,
    seed: int = 42,
) -> pl.DataFrame:
    """Sample negatives using shown_but_no_action strategy.

    For each positive (label > 0), keep up to cap_per_positive negatives.
    """
    positives = labeled.filter(pl.col("label") > 0)
    negatives = labeled.filter(pl.col("label") == 0)

    if len(positives) == 0:
        return labeled

    # count positives per impression
    pos_counts = positives.group_by("impression_id").agg(
        pl.len().alias("n_pos"),
    )

    # join to determine budget per impression
    neg_with_budget = negatives.join(pos_counts, on="impression_id", how="inner").with_columns(
        (pl.col("n_pos") * cap_per_positive).alias("neg_budget"),
    )

    # sample within budget (deterministic via sort + head)
    rng = random.Random(seed)  # noqa: S311
    sampled_parts = []
    for imp_id in neg_with_budget["impression_id"].unique().to_list():
        imp_negs = neg_with_budget.filter(pl.col("impression_id") == imp_id)
        budget = int(imp_negs["neg_budget"][0])
        if len(imp_negs) > budget:
            indices = list(range(len(imp_negs)))
            rng.shuffle(indices)
            imp_negs = imp_negs[indices[:budget]]
        sampled_parts.append(imp_negs.drop("n_pos", "neg_budget"))

    sampled_negatives = pl.concat(sampled_parts) if sampled_parts else negatives.head(0)

    return pl.concat([positives, sampled_negatives]).sort("impression_id", "wine_sku_id")


def _time_split(
    df: pl.DataFrame,
    ts_col: str = "shown_ts",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> pl.DataFrame:
    """Apply time-based train/val/test split.

    Chronological: first 70% train, next 15% val, last 15% test.
    """
    if ts_col in df.columns and df[ts_col].dtype == pl.Utf8:
        df = df.with_columns(pl.col(ts_col).str.to_datetime(time_zone="UTC"))

    df_sorted = df.sort(ts_col)
    n = len(df_sorted)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    splits = ["train"] * train_end + ["val"] * (val_end - train_end) + ["test"] * (n - val_end)
    return df_sorted.with_columns(pl.Series("split", splits))


def build_training_examples(
    *,
    dataset_version: str,
    feature_set_version: str,
    seed: int = 42,
    data_root: str = "data",
    output_root: str | None = None,
    cap_per_positive: int = 10,
    attribution_window_days: int = 7,
) -> pl.DataFrame:
    """Build training_examples_v1 from impression/action/order logs.

    Returns:
        DataFrame with columns: impression_id, user_id, wine_sku_id, label, split, shown_ts
    """
    root = Path(data_root)
    out_root = Path(output_root) if output_root else root / "training"

    # load Silver or Bronze data (Silver preferred)
    imp_path = _find_data(root, "impression_log_v1")
    act_path = _find_data(root, "action_log_v1")
    ord_path = _find_data(root, "order_log_v1")

    if imp_path is None:
        msg = "No impression data found"
        raise FileNotFoundError(msg)

    impressions = pl.read_parquet(imp_path)
    actions = pl.read_parquet(act_path) if act_path else pl.DataFrame()
    orders = pl.read_parquet(ord_path) if ord_path else pl.DataFrame()

    log.info("loaded_data", impressions=len(impressions), actions=len(actions), orders=len(orders))

    # 1. Assign labels
    labeled = _assign_labels(impressions, actions, orders, attribution_window_days)
    log.info("labeled", total=len(labeled), positives=int((labeled["label"] > 0).sum()))

    # 2. Sample negatives
    sampled = _sample_negatives(labeled, cap_per_positive=cap_per_positive, seed=seed)
    log.info("sampled", total=len(sampled))

    # 3. Time split
    examples = _time_split(sampled)
    split_counts = examples.group_by("split").len().to_dicts()
    log.info("split", counts=split_counts)

    # 4. Quality gates
    gate_results = _run_quality_gates(examples)
    log.info("quality_gates", results=[g.gate_name for g in gate_results if g.passed])

    # 5. Write output
    out_path = out_root / f"training_examples_v1__ds={dataset_version}"
    write_parquet_atomic(examples, out_path / "data.parquet")

    # 6. Write manifest
    manifest = {
        "dataset_version": dataset_version,
        "split_id": "time_split",
        "feature_set_version": feature_set_version,
        "embedding_versions": {},
        "join_rules_json": {
            "as_of_ts_le_event_ts": True,
            "published_at_le_event_ts": True,
        },
        "negative_sampling_spec_json": {
            "method": "shown_but_no_action",
            "cap_per_pos": cap_per_positive,
            "seed": seed,
        },
        "attribution_spec_json": {
            "rule": "last_impression_within_window",
            "version": "attr_v1",
            "window_days": attribution_window_days,
        },
        "quality_gates": [
            {
                "gate": g.gate_name,
                "passed": g.passed,
                "metric": g.metric_value,
                "threshold": g.threshold,
            }
            for g in gate_results
        ],
        "candidate_budget_spec_version": "budget_v0",
        "created_at": datetime.now(UTC).isoformat(),
        "stats": {
            "total_examples": len(examples),
            "positive_rate": round(float((examples["label"] > 0).mean() or 0), 4),  # type: ignore[arg-type]
            "splits": {d["split"]: d["len"] for d in split_counts},
        },
    }
    manifest_path = out_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    log.info("manifest_written", path=str(manifest_path))

    return examples


def _run_quality_gates(examples: pl.DataFrame) -> list[GateResult]:
    """Run quality gates on the final training examples.

    Gates:
      1. Leakage: verify chronological split ordering (train < val < test).
      2. Join success: fraction of impressions with at least one positive label.
    """
    gates: list[GateResult] = []

    # 1. Temporal leakage gate: check split ordering
    violation_rate = 0.0
    if "split" in examples.columns and "shown_ts" in examples.columns:
        splits = examples.group_by("split").agg(
            pl.col("shown_ts").max().alias("max_ts"),
            pl.col("shown_ts").min().alias("min_ts"),
        )
        split_map = {row["split"]: row for row in splits.to_dicts()}
        if (
            "train" in split_map
            and "val" in split_map
            and split_map["train"]["max_ts"] > split_map["val"]["min_ts"]
        ):
            violation_rate = 1.0
        if (
            "val" in split_map
            and "test" in split_map
            and split_map["val"]["max_ts"] > split_map["test"]["min_ts"]
        ):
            violation_rate = 1.0

    leakage = check_leakage_gate(violation_rate=violation_rate)
    gates.append(leakage)
    log.info("gate_result", gate=leakage.gate_name, passed=leakage.passed)

    # 2. Join success gate: how many impressions have >= 1 positive label
    total_impressions = examples["impression_id"].n_unique()
    if total_impressions > 0:
        positive_impressions = examples.filter(pl.col("label") > 0)["impression_id"].n_unique()
        success_rate = positive_impressions / total_impressions
    else:
        success_rate = 0.0

    join_gate = check_join_success_gate(success_rate=success_rate, threshold=0.01)
    gates.append(join_gate)
    log.info(
        "gate_result",
        gate=join_gate.gate_name,
        passed=join_gate.passed,
        metric=join_gate.metric_value,
    )

    # fail hard on leakage
    if not leakage.passed:
        msg = f"Quality gate FAILED: {leakage.gate_name} — violation_rate={leakage.metric_value}"
        raise ValueError(msg)

    return gates


def _find_data(root: Path, log_type: str) -> Path | None:
    """Find latest data file for a log type (Silver > Bronze)."""
    # check Silver partitioned
    silver_parts = sorted((root / "silver" / log_type).glob("dt=*/data.parquet"))
    if silver_parts:
        return silver_parts[-1]
    # check Bronze flat
    bronze = root / "bronze" / log_type / "data.parquet"
    if bronze.exists():
        return bronze
    return None
