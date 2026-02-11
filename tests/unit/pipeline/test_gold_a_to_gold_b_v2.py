"""Tests for Gold-A → Gold-B v2 IR builders (Phase H SOTA)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from wine_rec.pipeline.gold_a_to_gold_b import (
    build_expert_profile_ir,
    build_review_aggregate_ir_v2,
    build_temporal_ir_v2,
    run_gold_a_to_gold_b,
)


def _make_reviews_with_published_at() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "wine_core_id": ["c1", "c1", "c1", "c2", "c2"],
            "rating": [90.0, 88.0, 85.0, 16.0, 17.0],
            "rating_scale": ["100", "100", "100", "20", "20"],
            "author_type": ["critic", "expert", "user", "user", "critic"],
            "author_id": ["a1", "a2", "a3", "a3", "a4"],
            "published_at": [
                "2025-01-01",
                "2024-06-01",
                "2023-01-01",
                "2025-06-01",
                "2024-01-01",
            ],
            "region": ["Burgundy", "Burgundy", "Bordeaux", "Champagne", "Champagne"],
        }
    )


def _make_cores() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "wine_core_id": ["c1", "c2", "c3"],
            "wine_type": ["red", "white", "sparkling"],
            "region": ["Burgundy", "Champagne", "Champagne"],
        }
    )


class TestBuildReviewAggregateIRv2:
    def test_output_columns(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        expected_cols = {
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
        }
        assert set(result.columns) == expected_cols

    def test_all_cores_represented(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        assert len(result) == 3
        assert set(result["wine_core_id"].to_list()) == {"c1", "c2", "c3"}

    def test_missing_reviews_filled_with_defaults(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        c3 = result.filter(pl.col("wine_core_id") == "c3")
        assert c3["weighted_rating_mean"][0] == 0.0
        assert c3["decay_weighted_rating_mean"][0] == 0.0
        assert c3["consensus_category"][0] == "insufficient"

    def test_decay_weighted_differs_from_v1(self):
        """Decay-weighted mean should differ from static mean when reviews span time."""
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        c1 = result.filter(pl.col("wine_core_id") == "c1")
        # With temporal decay, recent reviews are weighted more
        assert c1["decay_weighted_rating_mean"][0] != c1["weighted_rating_mean"][0]

    def test_consensus_category_insufficient_few_reviewers(self):
        """Less than 3 reviewers → insufficient."""
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c1"],
                "rating": [90.0, 92.0],
                "rating_scale": ["100", "100"],
                "author_type": ["critic", "critic"],
                "author_id": ["a1", "a2"],
                "published_at": ["2025-01-01", "2025-06-01"],
            }
        )
        cores = pl.DataFrame({"wine_core_id": ["c1"]})
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        assert result["consensus_category"][0] == "insufficient"

    def test_consensus_category_high_agreement(self):
        """Very similar ratings from 3+ reviewers → high_agreement."""
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1"] * 4,
                "rating": [90.0, 90.0, 90.0, 90.0],
                "rating_scale": ["100"] * 4,
                "author_type": ["critic", "expert", "user", "critic"],
                "author_id": ["a1", "a2", "a3", "a4"],
                "published_at": ["2025-01-01"] * 4,
            }
        )
        cores = pl.DataFrame({"wine_core_id": ["c1"]})
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        assert result["consensus_category"][0] == "high_agreement"

    def test_inter_expert_variance_nonnegative(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        for val in result["inter_expert_variance"].to_list():
            assert val >= 0.0

    def test_expert_agreement_pct_bounded(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        for val in result["expert_agreement_pct"].to_list():
            assert 0.0 <= val <= 1.0

    def test_as_of_ts_deterministic(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        ts = "2026-02-01T00:00:00Z"
        result = build_review_aggregate_ir_v2(reviews, cores, as_of_ts=ts)
        for val in result["as_of_ts"].to_list():
            assert val == ts

    def test_custom_decay_half_life(self):
        """Shorter half-life should amplify recency effect."""
        reviews = _make_reviews_with_published_at()
        cores = pl.DataFrame({"wine_core_id": ["c1"]})
        ts = "2026-01-15T00:00:00Z"
        long_hl = build_review_aggregate_ir_v2(
            reviews, cores, as_of_ts=ts, decay_half_life_days=730.0
        )
        short_hl = build_review_aggregate_ir_v2(
            reviews, cores, as_of_ts=ts, decay_half_life_days=90.0
        )
        # Shorter half-life should produce different decay-weighted mean
        assert long_hl["decay_weighted_rating_mean"][0] != short_hl["decay_weighted_rating_mean"][0]


class TestBuildExpertProfileIR:
    def test_output_columns(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        expected_cols = {
            "author_id",
            "author_type",
            "review_count",
            "wine_region_coverage",
            "avg_rating_given",
            "rating_variance",
            "authority_score",
            "specialization_tags",
            "as_of_ts",
        }
        assert set(result.columns) == expected_cols

    def test_author_count(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        # a1, a2, a3, a4 = 4 unique authors
        assert len(result) == 4

    def test_review_count_per_author(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        a3 = result.filter(pl.col("author_id") == "a3")
        assert a3["review_count"][0] == 2  # a3 reviewed c1 and c2

    def test_authority_score_bounded(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        for score in result["authority_score"].to_list():
            assert 0.0 <= score <= 1.0

    def test_critic_has_higher_authority_than_user(self):
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(reviews, cores, as_of_ts="2026-01-15T00:00:00Z")
        critic = result.filter(pl.col("author_type") == "critic")
        user = result.filter(pl.col("author_type") == "user")
        # Critic type weight (3.0) > user type weight (1.0) → higher authority component
        assert critic["authority_score"].mean() > user["authority_score"].mean()

    def test_specialization_with_low_threshold(self):
        """With specialization_threshold=1, authors with 1+ reviews in a region qualify."""
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(
            reviews, cores, as_of_ts="2026-01-15T00:00:00Z", specialization_threshold=1
        )
        a1 = result.filter(pl.col("author_id") == "a1")
        tags = a1["specialization_tags"][0]
        assert "Burgundy" in tags

    def test_specialization_with_high_threshold(self):
        """With high threshold, no one qualifies for specialization."""
        reviews = _make_reviews_with_published_at()
        cores = _make_cores()
        result = build_expert_profile_ir(
            reviews, cores, as_of_ts="2026-01-15T00:00:00Z", specialization_threshold=100
        )
        for tags in result["specialization_tags"].to_list():
            assert tags == []


class TestBuildTemporalIRv2:
    def test_output_columns(self):
        cores = pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]})
        skus = pl.DataFrame({"wine_core_id": ["c1"], "vintage_year": [2015]})
        result = build_temporal_ir_v2(
            cores, skus, reference_year=2026, as_of_ts="2026-01-15T00:00:00Z"
        )
        expected = {
            "wine_core_id",
            "vintage_year",
            "drink_from_year",
            "drink_to_year",
            "current_stage",
            "estimation_method",
            "rule_confidence",
            "model_confidence",
            "expert_confidence",
            "merged_confidence",
            "peak_trajectory",
            "days_to_peak",
            "vintage_effect_score",
            "as_of_ts",
        }
        assert set(result.columns) == expected

    def test_rule_based_method(self):
        cores = pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]})
        skus = pl.DataFrame({"wine_core_id": ["c1"], "vintage_year": [2015]})
        result = build_temporal_ir_v2(
            cores, skus, reference_year=2026, as_of_ts="2026-01-15T00:00:00Z"
        )
        assert result["estimation_method"][0] == "rule"
        assert result["rule_confidence"][0] is not None
        assert result["model_confidence"][0] is None

    def test_peak_trajectory_present(self):
        cores = pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]})
        skus = pl.DataFrame({"wine_core_id": ["c1"], "vintage_year": [2015]})
        result = build_temporal_ir_v2(
            cores, skus, reference_year=2026, as_of_ts="2026-01-15T00:00:00Z"
        )
        assert result["peak_trajectory"][0] in {"approaching", "at_peak", "declining"}

    def test_days_to_peak_present(self):
        cores = pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]})
        skus = pl.DataFrame({"wine_core_id": ["c1"], "vintage_year": [2015]})
        result = build_temporal_ir_v2(
            cores, skus, reference_year=2026, as_of_ts="2026-01-15T00:00:00Z"
        )
        assert result["days_to_peak"][0] is not None

    def test_no_vintage_defaults_to_reference_minus_3(self):
        cores = pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]})
        skus = pl.DataFrame(schema={"wine_core_id": pl.Utf8, "vintage_year": pl.Int64})
        result = build_temporal_ir_v2(
            cores, skus, reference_year=2026, as_of_ts="2026-01-15T00:00:00Z"
        )
        assert result["vintage_year"][0] == 2023

    def test_multiple_wines(self):
        cores = pl.DataFrame({"wine_core_id": ["c1", "c2"], "wine_type": ["red", "white"]})
        skus = pl.DataFrame({"wine_core_id": ["c1", "c2"], "vintage_year": [2015, 2023]})
        result = build_temporal_ir_v2(
            cores, skus, reference_year=2026, as_of_ts="2026-01-15T00:00:00Z"
        )
        assert len(result) == 2


class TestRunGoldAToGoldBV2:
    def test_v2_irs_generated_with_published_at(self, tmp_path: Path):
        """When reviews have published_at column, v2 IRs should be generated."""
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"

        core_dir = gold_a / "wine_core_master_v1"
        core_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1", "c2"],
                "variety": ["Pinot Noir", "Chardonnay"],
                "region": ["Burgundy", "Champagne"],
                "wine_type": ["red", "white"],
                "producer": ["DRC", "Krug"],
            }
        ).write_parquet(core_dir / "data.parquet")

        sku_dir = gold_a / "wine_sku_master_v1"
        sku_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_sku_id": ["sku1", "sku2"],
                "wine_core_id": ["c1", "c2"],
                "vintage_year": [2015, 2023],
            }
        ).write_parquet(sku_dir / "data.parquet")

        review_dir = gold_a / "review_master_v1"
        review_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1", "c1", "c2"],
                "rating": [90.0, 88.0, 16.0],
                "rating_scale": ["100", "100", "20"],
                "author_type": ["critic", "expert", "user"],
                "author_id": ["a1", "a2", "a3"],
                "published_at": ["2025-01-01", "2024-06-01", "2025-06-01"],
                "region": ["Burgundy", "Burgundy", "Champagne"],
            }
        ).write_parquet(review_dir / "data.parquet")

        result = run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
        )

        # v1 IRs still generated
        assert "wine_review_aggregate_ir_v1" in result
        assert "wine_temporal_ir_v1" in result
        assert "wine_scarcity_ir_v1" in result

        # v2 IRs also generated
        assert "wine_review_aggregate_ir_v2" in result
        assert "expert_profile_ir_v1" in result
        assert "wine_temporal_ir_v2" in result

    def test_v1_backward_compat(self, tmp_path: Path):
        """v1 IRs should still work without published_at column."""
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"

        core_dir = gold_a / "wine_core_master_v1"
        core_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "wine_type": ["red"],
                "variety": ["Pinot Noir"],
                "region": ["Burgundy"],
                "producer": ["DRC"],
            }
        ).write_parquet(core_dir / "data.parquet")

        sku_dir = gold_a / "wine_sku_master_v1"
        sku_dir.mkdir(parents=True)
        pl.DataFrame(
            {"wine_sku_id": ["s1"], "wine_core_id": ["c1"], "vintage_year": [2020]}
        ).write_parquet(sku_dir / "data.parquet")

        review_dir = gold_a / "review_master_v1"
        review_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "rating": [90.0],
                "rating_scale": ["100"],
                "author_type": ["critic"],
            }
        ).write_parquet(review_dir / "data.parquet")

        result = run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
        )

        # v1 IRs present
        assert "wine_review_aggregate_ir_v1" in result
        # v2 review aggregate NOT generated (no published_at)
        assert "wine_review_aggregate_ir_v2" not in result
        # v2 temporal is still generated (doesn't need published_at)
        assert "wine_temporal_ir_v2" in result
