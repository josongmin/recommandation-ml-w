"""Tests for dataset builder (RFC-DATASET-BUILDER-011)."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from wine_rec.pipeline.dataset_builder import (
    _assign_labels,
    _run_quality_gates,
    _sample_negatives,
    _time_split,
    build_training_examples,
)


class TestAssignLabels:
    def test_basic_label_assignment(self):
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1,sku2,sku3"],
            }
        )
        actions = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1"],
                "wine_sku_id": ["sku1", "sku2"],
                "action_type": ["CLICK", "WISHLIST"],
            }
        )
        orders = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
            }
        )

        result = _assign_labels(impressions, actions, orders)
        assert len(result) == 3  # 3 items shown

        sku1 = result.filter(pl.col("wine_sku_id") == "sku1")
        assert sku1["label"][0] == 2  # CLICK = 2

        sku2 = result.filter(pl.col("wine_sku_id") == "sku2")
        assert sku2["label"][0] == 3  # WISHLIST = 3

        sku3 = result.filter(pl.col("wine_sku_id") == "sku3")
        assert sku3["label"][0] == 0  # no action

    def test_purchase_overrides_action(self):
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1"],
            }
        )
        actions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "wine_sku_id": ["sku1"],
                "action_type": ["CLICK"],
            }
        )
        orders = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "wine_sku_id": ["sku1"],
            }
        )

        result = _assign_labels(impressions, actions, orders)
        assert result["label"][0] == 5  # purchase label

    def test_empty_actions_and_orders(self):
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1,sku2"],
            }
        )
        empty_actions = pl.DataFrame()
        empty_orders = pl.DataFrame()

        result = _assign_labels(impressions, empty_actions, empty_orders)
        assert len(result) == 2
        assert result["label"].sum() == 0

    def test_attribution_window_filters_late_actions(self):
        """Actions beyond attribution_window_days should be excluded."""
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1,sku2"],
            }
        )
        actions = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1"],
                "wine_sku_id": ["sku1", "sku2"],
                "action_type": ["CLICK", "CLICK"],
                # sku1: 2 days later (within window)
                # sku2: 30 days later (outside 7-day window)
                "action_ts": ["2026-01-03T00:00:00Z", "2026-01-31T00:00:00Z"],
            }
        )
        orders = pl.DataFrame(schema={"impression_id": pl.Utf8, "wine_sku_id": pl.Utf8})

        result = _assign_labels(impressions, actions, orders, attribution_window_days=7)

        sku1 = result.filter(pl.col("wine_sku_id") == "sku1")
        assert sku1["label"][0] == 2  # within window → labeled

        sku2 = result.filter(pl.col("wine_sku_id") == "sku2")
        assert sku2["label"][0] == 0  # outside window → no label

    def test_attribution_window_no_action_ts_graceful(self):
        """When action_ts is missing, all actions pass through (backwards compat)."""
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1"],
            }
        )
        actions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "wine_sku_id": ["sku1"],
                "action_type": ["CLICK"],
                # no action_ts column
            }
        )
        orders = pl.DataFrame(schema={"impression_id": pl.Utf8, "wine_sku_id": pl.Utf8})

        result = _assign_labels(impressions, actions, orders)
        sku1 = result.filter(pl.col("wine_sku_id") == "sku1")
        assert sku1["label"][0] == 2  # still labeled despite no action_ts

    def test_order_attribution_window_filters_late_orders(self):
        """Orders beyond attribution_window_days should be excluded."""
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1,sku2"],
            }
        )
        actions = pl.DataFrame(
            schema={"impression_id": pl.Utf8, "wine_sku_id": pl.Utf8, "action_type": pl.Utf8}
        )
        orders = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1"],
                "wine_sku_id": ["sku1", "sku2"],
                # sku1: 3 days later (within 7-day window)
                # sku2: 20 days later (outside window)
                "order_ts": ["2026-01-04T00:00:00Z", "2026-01-21T00:00:00Z"],
            }
        )

        result = _assign_labels(impressions, actions, orders, attribution_window_days=7)

        sku1 = result.filter(pl.col("wine_sku_id") == "sku1")
        assert sku1["label"][0] == 5  # purchase within window

        sku2 = result.filter(pl.col("wine_sku_id") == "sku2")
        assert sku2["label"][0] == 0  # purchase outside window → excluded

    def test_order_no_order_ts_passes_all(self):
        """Orders without order_ts column still get labeled (backwards compat)."""
        impressions = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "user_id": ["u1"],
                "shown_ts": ["2026-01-01T00:00:00Z"],
                "items": ["sku1"],
            }
        )
        actions = pl.DataFrame(
            schema={"impression_id": pl.Utf8, "wine_sku_id": pl.Utf8, "action_type": pl.Utf8}
        )
        orders = pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "wine_sku_id": ["sku1"],
                # no order_ts column
            }
        )

        result = _assign_labels(impressions, actions, orders)
        assert result["label"][0] == 5  # purchase label without order_ts


class TestSampleNegatives:
    def test_cap_negatives(self):
        labeled = pl.DataFrame(
            {
                "impression_id": ["imp1"] * 6,
                "wine_sku_id": [f"sku{i}" for i in range(6)],
                "user_id": ["u1"] * 6,
                "shown_ts": ["2026-01-01T00:00:00Z"] * 6,
                "label": [2, 0, 0, 0, 0, 0],  # 1 positive, 5 negatives
            }
        )

        result = _sample_negatives(labeled, cap_per_positive=2, seed=42)
        positives = result.filter(pl.col("label") > 0)
        negatives = result.filter(pl.col("label") == 0)
        assert len(positives) == 1
        assert len(negatives) == 2  # exactly capped at 2 per positive

    def test_no_positives_returns_all(self):
        labeled = pl.DataFrame(
            {
                "impression_id": ["imp1"] * 3,
                "wine_sku_id": ["sku1", "sku2", "sku3"],
                "user_id": ["u1"] * 3,
                "shown_ts": ["2026-01-01T00:00:00Z"] * 3,
                "label": [0, 0, 0],
            }
        )

        result = _sample_negatives(labeled, cap_per_positive=5)
        assert len(result) == 3  # all returned when no positives

    def test_deterministic(self):
        labeled = pl.DataFrame(
            {
                "impression_id": ["imp1"] * 10,
                "wine_sku_id": [f"sku{i}" for i in range(10)],
                "user_id": ["u1"] * 10,
                "shown_ts": ["2026-01-01T00:00:00Z"] * 10,
                "label": [3] + [0] * 9,
            }
        )

        r1 = _sample_negatives(labeled, cap_per_positive=3, seed=42)
        r2 = _sample_negatives(labeled, cap_per_positive=3, seed=42)
        assert r1["wine_sku_id"].to_list() == r2["wine_sku_id"].to_list()


class TestTimeSplit:
    def test_chronological_split(self):
        df = pl.DataFrame(
            {
                "shown_ts": [
                    "2026-01-01T00:00:00Z",
                    "2026-02-01T00:00:00Z",
                    "2026-03-01T00:00:00Z",
                    "2026-04-01T00:00:00Z",
                    "2026-05-01T00:00:00Z",
                    "2026-06-01T00:00:00Z",
                    "2026-07-01T00:00:00Z",
                    "2026-08-01T00:00:00Z",
                    "2026-09-01T00:00:00Z",
                    "2026-10-01T00:00:00Z",
                ],
                "label": list(range(10)),
            }
        )

        result = _time_split(df, train_ratio=0.7, val_ratio=0.15)
        assert "split" in result.columns

        splits = result["split"].to_list()
        assert splits.count("train") == 7
        assert splits.count("val") == 1
        assert splits.count("test") == 2

        # verify chronological order: all train before val before test
        train_idx = [i for i, s in enumerate(splits) if s == "train"]
        val_idx = [i for i, s in enumerate(splits) if s == "val"]
        test_idx = [i for i, s in enumerate(splits) if s == "test"]
        assert max(train_idx) < min(val_idx)
        assert max(val_idx) < min(test_idx)


class TestQualityGates:
    def test_valid_split_passes_leakage_gate(self):
        """Properly ordered splits should pass the leakage gate."""
        examples = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp2", "imp3"],
                "shown_ts": [
                    "2026-01-01T00:00:00Z",
                    "2026-06-01T00:00:00Z",
                    "2026-12-01T00:00:00Z",
                ],
                "label": [2, 0, 1],
                "split": ["train", "val", "test"],
            }
        ).with_columns(pl.col("shown_ts").str.to_datetime(time_zone="UTC"))

        gates = _run_quality_gates(examples)
        leakage_gate = next(g for g in gates if g.gate_name == "leakage")
        assert leakage_gate.passed is True
        assert leakage_gate.metric_value == 0.0

    def test_leaking_split_fails_gate(self):
        """Overlapping splits should fail the leakage gate."""
        examples = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp2", "imp3"],
                "shown_ts": [
                    "2026-06-01T00:00:00Z",  # train has later date
                    "2026-01-01T00:00:00Z",  # val has earlier date → leakage!
                    "2026-12-01T00:00:00Z",
                ],
                "label": [2, 0, 1],
                "split": ["train", "val", "test"],
            }
        ).with_columns(pl.col("shown_ts").str.to_datetime(time_zone="UTC"))

        with pytest.raises(ValueError, match=r"Quality gate FAILED.*leakage"):
            _run_quality_gates(examples)

    def test_join_success_gate_computed(self):
        """Join success gate should measure positive impression coverage."""
        examples = pl.DataFrame(
            {
                "impression_id": ["imp1", "imp1", "imp2", "imp2"],
                "shown_ts": ["2026-01-01T00:00:00Z"] * 4,
                "label": [2, 0, 0, 0],
                "split": ["train"] * 4,
            }
        ).with_columns(pl.col("shown_ts").str.to_datetime(time_zone="UTC"))

        gates = _run_quality_gates(examples)
        join_gate = next(g for g in gates if g.gate_name == "join_success")
        # 1 out of 2 impressions have positives = 50%
        assert join_gate.metric_value == 0.5
        assert join_gate.passed is True  # threshold is 0.01


class TestBuildTrainingExamples:
    def test_end_to_end(self, tmp_path: Path):
        # set up Bronze data
        bronze = tmp_path / "bronze"
        imp_dir = bronze / "impression_log_v1"
        imp_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "impression_id": [f"imp{i}" for i in range(20)],
                "user_id": [f"u{i % 5}" for i in range(20)],
                "shown_ts": [f"2026-01-{i + 1:02d}T00:00:00Z" for i in range(20)],
                "surface": ["home"] * 20,
                "items": ["sku1,sku2,sku3"] * 20,
            }
        ).write_parquet(imp_dir / "data.parquet")

        act_dir = bronze / "action_log_v1"
        act_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "impression_id": ["imp0", "imp1", "imp5", "imp10"],
                "wine_sku_id": ["sku1", "sku2", "sku1", "sku3"],
                "action_type": ["CLICK", "WISHLIST", "CART", "CLICK"],
            }
        ).write_parquet(act_dir / "data.parquet")

        result = build_training_examples(
            dataset_version="test_v1",
            feature_set_version="fs_v1",
            data_root=str(tmp_path),
            output_root=str(tmp_path / "training"),
        )

        assert len(result) > 0
        assert "split" in result.columns
        assert "label" in result.columns
        assert set(result["split"].unique().to_list()) == {"train", "val", "test"}

        # verify manifest written with quality gates
        manifest_dir = tmp_path / "training" / "training_examples_v1__ds=test_v1"
        manifest_path = manifest_dir / "manifest.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text())
        assert manifest["dataset_version"] == "test_v1"
        assert manifest["feature_set_version"] == "fs_v1"
        assert manifest["attribution_spec_json"]["window_days"] == 7
        assert "stats" in manifest
        assert manifest["stats"]["total_examples"] == len(result)

        # verify quality gates are recorded in manifest
        assert "quality_gates" in manifest
        gate_names = {g["gate"] for g in manifest["quality_gates"]}
        assert "leakage" in gate_names
        assert "join_success" in gate_names
        assert all(g["passed"] for g in manifest["quality_gates"])
