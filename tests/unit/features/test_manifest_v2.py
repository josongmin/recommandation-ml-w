"""Tests for feature manifest v2 YAML."""

from __future__ import annotations

from pathlib import Path

import yaml


_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "wine_rec"
    / "features"
    / "manifest"
    / "feature_manifest_v2.yaml"
)


class TestFeatureManifestV2:
    def test_file_exists(self):
        assert _MANIFEST_PATH.exists()

    def test_valid_yaml(self):
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_version_is_fs_v2(self):
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        assert data["feature_set_version"] == "fs_v2"

    def test_has_entities(self):
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        assert "entities" in data
        entity_names = {e["entity_type"] for e in data["entities"]}
        assert "user" in entity_names
        assert "wine_core" in entity_names
        assert "wine_sku" in entity_names
        assert "context" in entity_names

    def test_critical_features_count(self):
        """v2 should have ~36+ critical features."""
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        critical_count = 0
        for entity in data["entities"]:
            for feat in entity.get("features", []):
                if feat.get("tier") == "critical":
                    critical_count += 1
        assert critical_count >= 30

    def test_important_features_count(self):
        """v2 should have ~20 important features."""
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        important_count = 0
        for entity in data["entities"]:
            for feat in entity.get("features", []):
                if feat.get("tier") == "important":
                    important_count += 1
        assert important_count >= 15

    def test_expert_aware_features_present(self):
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        all_names = set()
        for entity in data["entities"]:
            for feat in entity.get("features", []):
                all_names.add(feat["name"])
        expert_features = {
            "item_core_decay_weighted_rating_mean",
            "item_core_authority_decay_score",
            "item_core_consensus_category",
            "item_core_expert_agreement_pct",
        }
        assert expert_features.issubset(all_names)

    def test_temporal_v2_features_present(self):
        with _MANIFEST_PATH.open() as f:
            data = yaml.safe_load(f)
        all_names = set()
        for entity in data["entities"]:
            for feat in entity.get("features", []):
                all_names.add(feat["name"])
        temporal_features = {
            "item_core_days_to_peak",
            "item_core_peak_trajectory",
            "item_core_merged_confidence",
        }
        assert temporal_features.issubset(all_names)
