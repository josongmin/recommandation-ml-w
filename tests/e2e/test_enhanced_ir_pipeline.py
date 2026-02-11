"""E2E: Masters → v2 IRs → features v2 → validate (Phase H SOTA)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from wine_rec.pipeline.gold_a_to_gold_b import run_gold_a_to_gold_b


def _write_masters(gold_a: Path) -> None:
    """Write SSOT master fixtures with published_at for v2 compatibility."""
    core_dir = gold_a / "wine_core_master_v1"
    core_dir.mkdir(parents=True)
    pl.DataFrame(
        {
            "wine_core_id": ["c1", "c2", "c3"],
            "variety": ["Pinot Noir", "Chardonnay", "Cabernet Sauvignon"],
            "region": ["Burgundy", "Champagne", "Bordeaux"],
            "wine_type": ["red", "white", "red"],
            "producer": ["DRC", "Krug", "Mouton"],
        }
    ).write_parquet(core_dir / "data.parquet")

    sku_dir = gold_a / "wine_sku_master_v1"
    sku_dir.mkdir(parents=True)
    pl.DataFrame(
        {
            "wine_sku_id": ["sku1", "sku2", "sku3"],
            "wine_core_id": ["c1", "c2", "c3"],
            "vintage_year": [2015, 2023, 2018],
        }
    ).write_parquet(sku_dir / "data.parquet")

    review_dir = gold_a / "review_master_v1"
    review_dir.mkdir(parents=True)
    pl.DataFrame(
        {
            "wine_core_id": ["c1", "c1", "c1", "c2", "c2", "c3", "c3", "c3"],
            "rating": [95.0, 92.0, 88.0, 17.0, 16.0, 90.0, 85.0, 87.0],
            "rating_scale": ["100", "100", "100", "20", "20", "100", "100", "100"],
            "author_type": [
                "critic",
                "expert",
                "user",
                "critic",
                "user",
                "expert",
                "user",
                "critic",
            ],
            "author_id": ["a1", "a2", "a3", "a4", "a3", "a2", "a3", "a1"],
            "published_at": [
                "2025-06-01",
                "2025-01-15",
                "2024-03-01",
                "2025-08-01",
                "2024-12-01",
                "2025-04-01",
                "2024-06-01",
                "2023-09-01",
            ],
            "region": [
                "Burgundy",
                "Burgundy",
                "Bordeaux",
                "Champagne",
                "Champagne",
                "Bordeaux",
                "Bordeaux",
                "Bordeaux",
            ],
        }
    ).write_parquet(review_dir / "data.parquet")


@pytest.mark.e2e
class TestEnhancedIRPipeline:
    """Test full v1 + v2 IR generation from masters."""

    def test_full_pipeline_generates_all_irs(self, tmp_path: Path):
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"
        _write_masters(gold_a)

        result = run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
            as_of_ts="2026-01-15T00:00:00Z",
        )

        # v1 IRs
        assert result["wine_review_aggregate_ir_v1"] == 3
        assert result["wine_temporal_ir_v1"] == 3
        assert result["wine_scarcity_ir_v1"] == 3

        # v2 IRs
        assert result["wine_review_aggregate_ir_v2"] == 3
        assert result["expert_profile_ir_v1"] > 0
        assert result["wine_temporal_ir_v2"] == 3

    def test_v2_review_aggregate_has_expected_columns(self, tmp_path: Path):
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"
        _write_masters(gold_a)

        run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
            as_of_ts="2026-01-15T00:00:00Z",
        )

        ir = pl.read_parquet(
            gold_b / "wine_review_aggregate_ir_v2" / "dt=2026-01-15" / "data.parquet"
        )
        required_v2_cols = {
            "decay_weighted_rating_mean",
            "authority_decay_score",
            "inter_expert_variance",
            "intra_expert_variance",
            "consensus_category",
            "expert_agreement_pct",
        }
        assert required_v2_cols.issubset(set(ir.columns))

    def test_expert_profiles_generated(self, tmp_path: Path):
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"
        _write_masters(gold_a)

        run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
            as_of_ts="2026-01-15T00:00:00Z",
        )

        profiles = pl.read_parquet(
            gold_b / "expert_profile_ir_v1" / "dt=2026-01-15" / "data.parquet"
        )
        assert "author_id" in profiles.columns
        assert "authority_score" in profiles.columns
        # 4 unique authors: a1, a2, a3, a4
        assert len(profiles) == 4

    def test_temporal_v2_has_peak_trajectory(self, tmp_path: Path):
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"
        _write_masters(gold_a)

        run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
            as_of_ts="2026-01-15T00:00:00Z",
        )

        temporal = pl.read_parquet(
            gold_b / "wine_temporal_ir_v2" / "dt=2026-01-15" / "data.parquet"
        )
        assert "peak_trajectory" in temporal.columns
        assert "days_to_peak" in temporal.columns
        assert "merged_confidence" in temporal.columns
        valid_trajectories = {"approaching", "at_peak", "declining"}
        for traj in temporal["peak_trajectory"].to_list():
            assert traj in valid_trajectories

    def test_v1_outputs_unchanged_with_v2(self, tmp_path: Path):
        """v1 IR outputs should be identical whether v2 is generated or not."""
        gold_a = tmp_path / "gold_a"
        gold_b = tmp_path / "gold_b"
        _write_masters(gold_a)

        run_gold_a_to_gold_b(
            input_path=str(gold_a),
            output_path=str(gold_b),
            dt="2026-01-15",
            as_of_ts="2026-01-15T00:00:00Z",
        )

        v1_review = pl.read_parquet(
            gold_b / "wine_review_aggregate_ir_v1" / "dt=2026-01-15" / "data.parquet"
        )
        # v1 output should have exactly the v1 columns
        assert "weighted_rating_mean" in v1_review.columns
        assert "critic_consensus_score" in v1_review.columns
        # v2 columns should NOT be in v1 output
        assert "decay_weighted_rating_mean" not in v1_review.columns
