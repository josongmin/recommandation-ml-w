"""Tests for Bronze → Silver ETL pipeline."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from wine_rec.pipeline.bronze_to_silver import (
    clean_actions,
    clean_impressions,
    clean_orders,
    clean_policies,
    run_bronze_to_silver,
)


class TestCleanImpressions:
    def test_dedup_by_impression_id(self):
        df = pl.DataFrame(
            {
                "impression_id": ["a", "a", "b"],
                "user_id": ["u1", "u1", "u2"],
                "shown_ts": ["2026-01-01T00:00:00Z"] * 3,
                "surface": ["home"] * 3,
                "items": ["sku1"] * 3,
            }
        )
        result = clean_impressions(df)
        assert len(result) == 2

    def test_drop_null_required_fields(self):
        df = pl.DataFrame(
            {
                "impression_id": ["a", None, "c"],
                "user_id": ["u1", "u2", None],
                "shown_ts": ["2026-01-01T00:00:00Z"] * 3,
                "surface": ["home"] * 3,
                "items": ["sku1"] * 3,
            }
        )
        result = clean_impressions(df)
        assert len(result) == 1  # only "a" has all fields

    def test_normalize_timestamps(self):
        df = pl.DataFrame(
            {
                "impression_id": ["a"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-15T10:30:00Z"],
                "surface": ["home"],
                "items": ["sku1,sku2"],
            }
        )
        result = clean_impressions(df)
        assert result["shown_ts"].dtype != pl.Utf8


class TestCleanActions:
    def test_dedup_by_composite_key(self):
        df = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1", "imp1"],
                "wine_sku_id": ["sku1", "sku1", "sku2"],
                "action_type": ["CLICK", "CLICK", "VIEW"],
                "action_ts": ["2026-01-01T00:00:00Z"] * 3,
            }
        )
        result = clean_actions(df)
        assert len(result) == 2

    def test_empty_dataframe(self):
        df = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
                "action_type": pl.Utf8,
                "action_ts": pl.Utf8,
            }
        )
        result = clean_actions(df)
        assert len(result) == 0


class TestCleanOrders:
    def test_clamp_negative_quantity(self):
        df = pl.DataFrame(
            {
                "order_id": ["o1"],
                "user_id": ["u1"],
                "wine_sku_id": ["sku1"],
                "order_ts": ["2026-01-01T00:00:00Z"],
                "quantity": [-5],
            }
        )
        result = clean_orders(df)
        assert result["quantity"][0] == 1

    def test_dedup_by_order_id(self):
        df = pl.DataFrame(
            {
                "order_id": ["o1", "o1"],
                "user_id": ["u1", "u1"],
                "wine_sku_id": ["sku1", "sku2"],
                "order_ts": ["2026-01-01T00:00:00Z"] * 2,
            }
        )
        result = clean_orders(df)
        assert len(result) == 1


class TestCleanPolicies:
    def test_dedup_by_impression_id(self):
        df = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1"],
                "model_version": ["v1", "v2"],
                "feature_set_version": ["fs_v1"] * 2,
            }
        )
        result = clean_policies(df)
        assert len(result) == 1


class TestRunBronzeToSilver:
    def test_end_to_end(self, tmp_path: Path):
        bronze = tmp_path / "bronze"
        silver = tmp_path / "silver"

        # write test impression data
        imp_dir = bronze / "impression_log_v1"
        imp_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "impression_id": ["imp1", "imp2"],
                "user_id": ["u1", "u2"],
                "shown_ts": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
                "surface": ["home", "search"],
                "items": ["sku1,sku2", "sku3"],
            }
        ).write_parquet(imp_dir / "data.parquet")

        result = run_bronze_to_silver(
            input_path=str(bronze),
            output_path=str(silver),
            dt="2026-01-15",
        )
        assert "impression_log_v1" in result
        assert result["impression_log_v1"] == 2

        # verify output written
        out_path = silver / "impression_log_v1" / "dt=2026-01-15" / "data.parquet"
        assert out_path.exists()

    def test_missing_input_skipped(self, tmp_path: Path):
        result = run_bronze_to_silver(
            input_path=str(tmp_path / "empty"),
            output_path=str(tmp_path / "silver"),
            dt="2026-01-15",
        )
        assert result == {}
