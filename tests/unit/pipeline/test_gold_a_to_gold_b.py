"""Tests for Gold-A → Gold-B IR derivation."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from wine_rec.pipeline.gold_a_to_gold_b import (
    build_review_aggregate_ir,
    build_scarcity_ir,
    build_temporal_ir,
    run_gold_a_to_gold_b,
)


class TestBuildReviewAggregateIR:
    def test_basic_aggregation(self):
        cores = pl.DataFrame({"wine_core_id": ["c1", "c2"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c1", "c2"],
                "rating": [90.0, 88.0, 16.0],
                "rating_scale": ["100", "100", "20"],
                "author_type": ["critic", "expert", "user"],
            }
        )

        result = build_review_aggregate_ir(reviews, cores)
        assert len(result) == 2
        assert "weighted_rating_mean" in result.columns
        assert "critic_consensus_score" in result.columns

        c1 = result.filter(pl.col("wine_core_id") == "c1")
        # c1: critic(90/100 * 3.0) + expert(88/100 * 2.0) → weighted mean > 0.8
        assert c1["weighted_rating_mean"][0] > 0.8

        c2 = result.filter(pl.col("wine_core_id") == "c2")
        # c2: user(16/20 * 1.0) → weighted mean = 0.8
        assert c2["weighted_rating_mean"][0] == 0.8

    def test_missing_reviews_filled(self):
        cores = pl.DataFrame({"wine_core_id": ["c1", "c2"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "rating": [92.0],
                "rating_scale": ["100"],
                "author_type": ["critic"],
            }
        )

        result = build_review_aggregate_ir(reviews, cores)
        assert len(result) == 2

        c2 = result.filter(pl.col("wine_core_id") == "c2")
        assert c2["weighted_rating_mean"][0] == 0.0
        assert c2["authority_weighted_count"][0] == 0

    def test_empty_reviews(self):
        cores = pl.DataFrame({"wine_core_id": ["c1"]})
        reviews = pl.DataFrame(
            schema={
                "wine_core_id": pl.Utf8,
                "rating": pl.Float64,
                "rating_scale": pl.Utf8,
                "author_type": pl.Utf8,
            }
        )

        result = build_review_aggregate_ir(reviews, cores)
        assert len(result) == 1
        assert result["weighted_rating_mean"][0] == 0.0

    def test_as_of_ts_is_deterministic(self):
        """When as_of_ts is passed, it should be used instead of datetime.now()."""
        cores = pl.DataFrame({"wine_core_id": ["c1"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "rating": [90.0],
                "rating_scale": ["100"],
                "author_type": ["critic"],
            }
        )

        fixed_ts = "2026-01-15T00:00:00Z"
        result = build_review_aggregate_ir(reviews, cores, as_of_ts=fixed_ts)
        assert result["as_of_ts"][0] == fixed_ts

    def test_as_of_ts_default_uses_now(self):
        """When as_of_ts is None, function still works (uses datetime.now)."""
        cores = pl.DataFrame({"wine_core_id": ["c1"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "rating": [90.0],
                "rating_scale": ["100"],
                "author_type": ["critic"],
            }
        )

        result = build_review_aggregate_ir(reviews, cores)
        # should have some as_of_ts value (not null)
        assert result["as_of_ts"][0] is not None


class TestBuildTemporalIR:
    def test_basic_temporal(self):
        cores = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c2"],
                "wine_type": ["red", "white"],
            }
        )
        skus = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c2"],
                "vintage_year": [2015, 2023],
            }
        )

        result = build_temporal_ir(cores, skus, reference_year=2026)
        assert len(result) == 2
        assert "current_stage" in result.columns
        assert "drink_from_year" in result.columns
        assert "confidence" in result.columns

        c1 = result.filter(pl.col("wine_core_id") == "c1")
        # 2015 red: drink from 2018, drink to 2027 → peak at 2026
        assert c1["current_stage"][0] == "peak"

        c2 = result.filter(pl.col("wine_core_id") == "c2")
        # 2023 white: drink from 2024, drink to 2028, mid=2026 → peak at 2026
        assert c2["current_stage"][0] == "peak"

    def test_no_vintage_defaults(self):
        cores = pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "wine_type": ["red"],
            }
        )
        skus = pl.DataFrame(
            schema={
                "wine_core_id": pl.Utf8,
                "vintage_year": pl.Int64,
            }
        )

        result = build_temporal_ir(cores, skus, reference_year=2026)
        assert len(result) == 1
        # should use default vintage (reference_year - 3 = 2023)
        assert result["vintage_year"][0] == 2023

    def test_temporal_as_of_ts_propagated(self):
        """as_of_ts should be stored in the output."""
        cores = pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]})
        skus = pl.DataFrame({"wine_core_id": ["c1"], "vintage_year": [2020]})

        result = build_temporal_ir(cores, skus, as_of_ts="2026-03-01T00:00:00Z")
        assert result["as_of_ts"][0] == "2026-03-01T00:00:00Z"


class TestBuildScarcityIR:
    def test_basic_scarcity(self):
        cores = pl.DataFrame({"wine_core_id": ["c1", "c2"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c1", "c1", "c2"],
            }
        )

        result = build_scarcity_ir(cores, reviews)
        assert len(result) == 2
        assert "rarity_score" in result.columns

        c1 = result.filter(pl.col("wine_core_id") == "c1")
        c2 = result.filter(pl.col("wine_core_id") == "c2")
        # fewer reviews = higher rarity
        assert c2["rarity_score"][0] > c1["rarity_score"][0]

    def test_no_reviews_highest_rarity(self):
        cores = pl.DataFrame({"wine_core_id": ["c1", "c2"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c1", "c1"],
            }
        )

        result = build_scarcity_ir(cores, reviews)
        c2 = result.filter(pl.col("wine_core_id") == "c2")
        # 0 reviews = max rarity
        assert c2["rarity_score"][0] == 1.0

    def test_max_reviews_zero_rarity(self):
        """Wine with the most reviews should have rarity ~ 0."""
        cores = pl.DataFrame({"wine_core_id": ["c1", "c2"]})
        reviews = pl.DataFrame(
            {
                "wine_core_id": ["c1"] * 10 + ["c2"],
            }
        )

        result = build_scarcity_ir(cores, reviews)
        c1 = result.filter(pl.col("wine_core_id") == "c1")
        # c1 has max reviews → rarity should be 0.0 with log/log scaling
        assert c1["rarity_score"][0] == 0.0


class TestRunGoldAToGoldB:
    def test_end_to_end(self, tmp_path: Path):
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"

        # write wine_core_master
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

        # write wine_sku_master
        sku_dir = gold_a / "wine_sku_master_v1"
        sku_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_sku_id": ["sku1", "sku2"],
                "wine_core_id": ["c1", "c2"],
                "vintage_year": [2015, 2023],
            }
        ).write_parquet(sku_dir / "data.parquet")

        # write review_master
        review_dir = gold_a / "review_master_v1"
        review_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1", "c1", "c2"],
                "rating": [90.0, 88.0, 16.0],
                "rating_scale": ["100", "100", "20"],
                "author_type": ["critic", "expert", "user"],
            }
        ).write_parquet(review_dir / "data.parquet")

        result = run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
        )

        assert "wine_review_aggregate_ir_v1" in result
        assert result["wine_review_aggregate_ir_v1"] == 2
        assert "wine_temporal_ir_v1" in result
        assert result["wine_temporal_ir_v1"] == 2
        assert "wine_scarcity_ir_v1" in result
        assert result["wine_scarcity_ir_v1"] == 2

        # verify output files
        assert (gold_b / "wine_review_aggregate_ir_v1" / "dt=2026-01-15" / "data.parquet").exists()
        assert (gold_b / "wine_temporal_ir_v1" / "dt=2026-01-15" / "data.parquet").exists()
        assert (gold_b / "wine_scarcity_ir_v1" / "dt=2026-01-15" / "data.parquet").exists()

        # verify review aggregate content
        review_ir = pl.read_parquet(
            gold_b / "wine_review_aggregate_ir_v1" / "dt=2026-01-15" / "data.parquet"
        )
        c1 = review_ir.filter(pl.col("wine_core_id") == "c1")
        assert c1["weighted_rating_mean"][0] > 0.8

    def test_as_of_ts_passed_through(self, tmp_path: Path):
        """as_of_ts should propagate to all IR outputs."""
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"

        core_dir = gold_a / "wine_core_master_v1"
        core_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1"],
                "variety": ["Pinot Noir"],
                "region": ["Burgundy"],
                "wine_type": ["red"],
                "producer": ["DRC"],
            }
        ).write_parquet(core_dir / "data.parquet")

        sku_dir = gold_a / "wine_sku_master_v1"
        sku_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_sku_id": ["sku1"],
                "wine_core_id": ["c1"],
                "vintage_year": [2015],
            }
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

        fixed_ts = "2026-01-15T00:00:00Z"
        run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
            as_of_ts=fixed_ts,
        )

        # verify review IR has the fixed timestamp
        review_ir = pl.read_parquet(
            gold_b / "wine_review_aggregate_ir_v1" / "dt=2026-01-15" / "data.parquet"
        )
        assert review_ir["as_of_ts"][0] == fixed_ts

        # verify temporal IR has the fixed timestamp
        temporal_ir = pl.read_parquet(
            gold_b / "wine_temporal_ir_v1" / "dt=2026-01-15" / "data.parquet"
        )
        assert temporal_ir["as_of_ts"][0] == fixed_ts

    def test_default_as_of_ts_uses_dt(self, tmp_path: Path):
        """When no as_of_ts, should default to dt-based timestamp."""
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"

        core_dir = gold_a / "wine_core_master_v1"
        core_dir.mkdir(parents=True)
        pl.DataFrame({"wine_core_id": ["c1"], "wine_type": ["red"]}).write_parquet(
            core_dir / "data.parquet"
        )

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

        run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
        )

        temporal_ir = pl.read_parquet(
            gold_b / "wine_temporal_ir_v1" / "dt=2026-01-15" / "data.parquet"
        )
        # should use "2026-01-15T00:00:00Z" not datetime.now()
        assert temporal_ir["as_of_ts"][0] == "2026-01-15T00:00:00Z"

    def test_missing_cores_returns_empty(self, tmp_path: Path):
        result = run_gold_a_to_gold_b(
            input_path=str(tmp_path / "empty"),
            output_path=str(tmp_path / "gold_b"),
            dt="2026-01-15",
        )
        assert result == {}
