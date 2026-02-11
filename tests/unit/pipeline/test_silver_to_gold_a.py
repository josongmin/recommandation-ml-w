"""Tests for Silver → Gold-A ETL pipeline."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from wine_rec.pipeline.silver_to_gold_a import (
    compute_user_profiles,
    enrich_impressions,
    run_silver_to_gold_a,
)


class TestEnrichImpressions:
    def test_enrichment_with_actions_and_orders(self):
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp2"],
                "user_id": ["u1", "u2"],
            }
        )
        actions = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1", "imp1"],
                "action_type": ["VIEW", "CLICK", "CART"],
            }
        )
        orders = pl.DataFrame(
            {
                "impression_id": ["imp1"],
            }
        )

        result = enrich_impressions(impressions, actions, orders)
        assert len(result) == 2
        assert "n_actions" in result.columns
        assert "has_click" in result.columns
        assert "has_purchase" in result.columns

        imp1 = result.filter(pl.col("impression_id") == "imp1")
        assert imp1["n_actions"][0] == 3
        assert imp1["has_click"][0] is True
        assert imp1["has_purchase"][0] is True

        imp2 = result.filter(pl.col("impression_id") == "imp2")
        assert imp2["n_actions"][0] == 0
        assert imp2["has_click"][0] is False
        assert imp2["has_purchase"][0] is False

    def test_empty_actions_and_orders(self):
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
            }
        )
        empty_actions = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "action_type": pl.Utf8,
            }
        )
        empty_orders = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
            }
        )

        result = enrich_impressions(impressions, empty_actions, empty_orders)
        assert len(result) == 1
        assert result["n_actions"][0] == 0
        assert result["has_click"][0] is False
        assert result["has_purchase"][0] is False


class TestComputeUserProfiles:
    def test_basic_profiles(self):
        actions = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "action_type": pl.Utf8,
            }
        )
        orders = pl.DataFrame(
            {
                "user_id": ["u1", "u1", "u2"],
                "quantity": [2, 3, 1],
                "price": [50000.0, 30000.0, 20000.0],
            }
        )

        result = compute_user_profiles(actions, orders)
        assert len(result) == 2

        u1 = result.filter(pl.col("user_id") == "u1")
        assert u1["order_count"][0] == 2
        assert u1["total_quantity"][0] == 5
        assert u1["total_spend"][0] == 80000.0

        u2 = result.filter(pl.col("user_id") == "u2")
        assert u2["order_count"][0] == 1
        assert u2["total_quantity"][0] == 1
        assert u2["total_spend"][0] == 20000.0

    def test_empty_orders(self):
        actions = pl.DataFrame(schema={"impression_id": pl.Utf8, "action_type": pl.Utf8})
        orders = pl.DataFrame(
            schema={
                "user_id": pl.Utf8,
                "quantity": pl.Int64,
                "price": pl.Float64,
            }
        )
        result = compute_user_profiles(actions, orders)
        assert len(result) == 0

    def test_merge_with_existing_new_wins(self):
        """New batch data supersedes existing for overlapping users."""
        actions = pl.DataFrame(schema={"impression_id": pl.Utf8, "action_type": pl.Utf8})
        orders = pl.DataFrame(
            {
                "user_id": ["u1"],
                "quantity": [5],
                "price": [100000.0],
            }
        )
        existing = pl.DataFrame(
            {
                "user_id": ["u1", "u2"],
                "order_count": [2, 1],
                "total_quantity": [10, 3],
                "total_spend": [200000.0, 50000.0],
            }
        )

        result = compute_user_profiles(actions, orders, existing)
        assert len(result) == 2  # both u1 and u2

        # u1: new batch wins (1 order, qty 5, spend 100k)
        u1 = result.filter(pl.col("user_id") == "u1")
        assert u1["order_count"][0] == 1
        assert u1["total_quantity"][0] == 5
        assert u1["total_spend"][0] == 100000.0

        # u2: retained from existing (not in new batch)
        u2 = result.filter(pl.col("user_id") == "u2")
        assert u2["order_count"][0] == 1
        assert u2["total_quantity"][0] == 3
        assert u2["total_spend"][0] == 50000.0


class TestRunSilverToGoldA:
    def test_end_to_end(self, tmp_path: Path):
        silver = tmp_path / "silver"
        gold_a = tmp_path / "gold_a"

        # write Silver impression data
        imp_dir = silver / "impression_log_v1" / "dt=2026-01-15"
        imp_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "impression_id": ["imp1", "imp2", "imp3"],
                "user_id": ["u1", "u2", "u1"],
                "shown_ts": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                ],
                "surface": ["home", "search", "home"],
                "items": ["sku1,sku2", "sku3", "sku1"],
            }
        ).write_parquet(imp_dir / "data.parquet")

        # write Silver action data
        act_dir = silver / "action_log_v1" / "dt=2026-01-15"
        act_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1"],
                "wine_core_id": ["c1", "c2"],
                "wine_sku_id": ["sku1", "sku2"],
                "action_type": ["CLICK", "VIEW"],
            }
        ).write_parquet(act_dir / "data.parquet")

        # write Silver order data
        ord_dir = silver / "order_log_v1" / "dt=2026-01-15"
        ord_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "order_id": ["o1"],
                "user_id": ["u1"],
                "wine_sku_id": ["sku1"],
                "impression_id": ["imp1"],
                "quantity": [2],
                "price": [50000.0],
            }
        ).write_parquet(ord_dir / "data.parquet")

        result = run_silver_to_gold_a(
            input_path=str(silver),
            output_path=str(gold_a),
            dt="2026-01-15",
        )

        assert "enriched_impressions_v1" in result
        assert result["enriched_impressions_v1"] == 3
        assert "user_profile_computed_v1" in result
        assert result["user_profile_computed_v1"] == 1  # only u1 has orders

        # verify enriched impressions output
        enriched_path = gold_a / "enriched_impressions_v1" / "dt=2026-01-15" / "data.parquet"
        assert enriched_path.exists()
        enriched = pl.read_parquet(enriched_path)
        assert len(enriched) == 3
        imp1 = enriched.filter(pl.col("impression_id") == "imp1")
        assert imp1["has_purchase"][0] is True

        # verify user profiles output
        profile_path = gold_a / "user_profile_computed_v1" / "data.parquet"
        assert profile_path.exists()

    def test_missing_impressions_returns_empty(self, tmp_path: Path):
        result = run_silver_to_gold_a(
            input_path=str(tmp_path / "empty"),
            output_path=str(tmp_path / "gold_a"),
            dt="2026-01-15",
        )
        assert result == {}
