"""Tests for offline feature builder (RFC-FEATURE-MANIFEST-010 §4)."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from wine_rec.features.offline_builder import (
    _apply_null_policy,
    _apply_time_travel_filter,
    _cast_default,
    _extract_feature_value,
    build_offline_features,
    load_manifest,
)
from wine_rec.schemas.manifest import FeatureDef, FeatureSource, TimeTravelRule


def _make_feature_def(
    name: str = "test_feat",
    dtype: str = "float",
    table: str = "test_table",
    key: str = "id",
    value_path: str = "value",
    rule: str = "as_of_ts_le_event_ts",
    ts_field: str = "as_of_ts",
    default: str | None = "0.0",
    null_policy: str = "default",
) -> FeatureDef:
    return FeatureDef(
        name=name,
        dtype=dtype,
        source=FeatureSource(table=table, key=key, value_path=value_path),
        time_travel_rule=TimeTravelRule(rule=rule, timestamp_field=ts_field),
        recipe_version="test_v1",
        default=default,
        null_policy=null_policy,
    )


class TestLoadManifest:
    def test_load_default_manifest(self):
        manifest = load_manifest()
        assert manifest.feature_set_version == "fs_v1"
        assert len(manifest.entities) == 4
        # check entity types
        entity_types = {e.entity_type for e in manifest.entities}
        assert entity_types == {"user", "wine_core", "wine_sku", "context"}


class TestTimeTravelFilter:
    def test_filters_future_rows(self):
        df = pl.DataFrame(
            {
                "id": ["a", "b", "c"],
                "value": [1.0, 2.0, 3.0],
                "as_of_ts": [
                    "2026-01-01T00:00:00Z",
                    "2026-06-01T00:00:00Z",
                    "2026-12-01T00:00:00Z",
                ],
            }
        )
        feat = _make_feature_def()
        result = _apply_time_travel_filter(df, feat, "2026-06-15T00:00:00Z")
        assert len(result) == 2  # only a and b

    def test_none_rule_passes_all(self):
        df = pl.DataFrame(
            {
                "id": ["a", "b"],
                "value": [1.0, 2.0],
                "as_of_ts": ["2099-01-01T00:00:00Z", "2099-12-01T00:00:00Z"],
            }
        )
        feat = _make_feature_def(rule="none")
        result = _apply_time_travel_filter(df, feat, "2026-01-01T00:00:00Z")
        assert len(result) == 2  # none rule = no filtering


class TestExtractFeatureValue:
    def test_extract_existing_column(self):
        df = pl.DataFrame(
            {
                "id": ["a", "b"],
                "value": [1.5, 2.5],
            }
        )
        feat = _make_feature_def()
        result = _extract_feature_value(df, feat, "id")
        assert result.columns == ["id", "test_feat"]
        assert result["test_feat"].to_list() == [1.5, 2.5]

    def test_missing_column_returns_nulls(self):
        df = pl.DataFrame(
            {
                "id": ["a", "b"],
            }
        )
        feat = _make_feature_def(value_path="nonexistent")
        result = _extract_feature_value(df, feat, "id")
        assert result["test_feat"].null_count() == 2

    def test_dedup_keys(self):
        df = pl.DataFrame(
            {
                "id": ["a", "a", "b"],
                "value": [1.0, 2.0, 3.0],
            }
        )
        feat = _make_feature_def()
        result = _extract_feature_value(df, feat, "id")
        assert len(result) == 2  # deduped

    def test_source_key_differs_from_entity_key(self):
        """When source.key differs from entity key, use source.key and rename."""
        df = pl.DataFrame(
            {
                "wine_core_id": ["c1", "c2"],
                "rarity_score": [0.8, 0.3],
            }
        )
        feat = _make_feature_def(
            name="item_sku_rarity",
            key="wine_core_id",
            value_path="rarity_score",
        )
        # entity key is wine_sku_id but source key is wine_core_id
        result = _extract_feature_value(df, feat, "wine_sku_id")
        assert "wine_sku_id" in result.columns  # renamed from wine_core_id
        assert "item_sku_rarity" in result.columns
        assert result["item_sku_rarity"].to_list() == [0.8, 0.3]

    def test_neither_key_in_df_returns_empty(self):
        """When neither entity key nor source key exist, return empty DataFrame."""
        df = pl.DataFrame({"unrelated": ["x", "y"]})
        feat = _make_feature_def(key="missing_key")
        result = _extract_feature_value(df, feat, "also_missing")
        assert len(result) == 0


class TestApplyNullPolicy:
    def test_default_policy_fills_nulls(self):
        df = pl.DataFrame(
            {
                "test_feat": [1.0, None, 3.0],
            }
        )
        feat = _make_feature_def(default="0.0", null_policy="default")
        result = _apply_null_policy(df, feat)
        assert result["test_feat"].null_count() == 0
        assert result["test_feat"][1] == 0.0

    def test_allow_null_keeps_nulls(self):
        df = pl.DataFrame(
            {
                "test_feat": [1.0, None],
            }
        )
        feat = _make_feature_def(null_policy="allow_null")
        result = _apply_null_policy(df, feat)
        assert result["test_feat"].null_count() == 1

    def test_error_policy_raises_on_nulls(self):
        """null_policy='error' must raise ValueError, not just log."""
        df = pl.DataFrame(
            {
                "test_feat": [1.0, None, 3.0],
            }
        )
        feat = _make_feature_def(null_policy="error")
        with pytest.raises(ValueError, match=r"Null policy violation.*test_feat.*1 nulls"):
            _apply_null_policy(df, feat)

    def test_error_policy_passes_without_nulls(self):
        """null_policy='error' should not raise when there are no nulls."""
        df = pl.DataFrame(
            {
                "test_feat": [1.0, 2.0, 3.0],
            }
        )
        feat = _make_feature_def(null_policy="error")
        result = _apply_null_policy(df, feat)
        assert result["test_feat"].null_count() == 0


class TestCastDefault:
    def test_float(self):
        assert _cast_default("3.14", "float") == 3.14

    def test_int(self):
        assert _cast_default("42", "int") == 42

    def test_bool_true(self):
        assert _cast_default("true", "bool") is True

    def test_bool_false(self):
        assert _cast_default("false", "bool") is False

    def test_string(self):
        assert _cast_default("hello", "string") == "hello"

    def test_unknown_passthrough(self):
        assert _cast_default([1, 2], "vector") == [1, 2]


class TestBuildOfflineFeatures:
    def test_end_to_end(self, tmp_path: Path):
        # create minimal data
        data_root = tmp_path / "data"

        # wine core master
        core_dir = data_root / "gold_a" / "wine_core_master_v1"
        core_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1", "c2"],
                "variety": ["Pinot Noir", "Chardonnay"],
                "region": ["Burgundy", "Champagne"],
                "producer": ["DRC", "Krug"],
                "updated_at": ["2026-01-01T00:00:00Z"] * 2,
            }
        ).write_parquet(core_dir / "data.parquet")

        # review aggregate IR
        review_dir = data_root / "gold_b" / "wine_review_aggregate_ir_v1"
        review_dt = review_dir / "dt=2026-01-15"
        review_dt.mkdir(parents=True)
        pl.DataFrame(
            {
                "wine_core_id": ["c1", "c2"],
                "weighted_rating_mean": [0.92, 0.85],
                "critic_consensus_score": [50.0, 30.0],
                "as_of_ts": ["2026-01-10T00:00:00Z"] * 2,
            }
        ).write_parquet(review_dt / "data.parquet")

        # impression log
        imp_dir = data_root / "bronze" / "impression_log_v1"
        imp_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "impression_id": ["imp1"],
                "surface": ["home"],
                "shown_ts": ["2026-01-15T10:00:00Z"],
            }
        ).write_parquet(imp_dir / "data.parquet")

        out_path = tmp_path / "features"
        results = build_offline_features(
            feature_set_version="fs_v1",
            event_ts="2026-06-01T00:00:00Z",
            output_path=str(out_path),
            data_root=str(data_root),
        )

        # should have at least wine_core and context
        assert "wine_core" in results
        assert "context" in results

        # wine_core features
        wc = results["wine_core"]
        assert len(wc) == 2
        assert "item_core_variety" in wc.columns
        assert "item_core_weighted_rating_mean" in wc.columns

        # verify output files written
        assert (out_path / "features_offline_v1__wine_core" / "data.parquet").exists()
        assert (out_path / "features_offline_v1__context" / "data.parquet").exists()
