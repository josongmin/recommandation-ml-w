"""Tests for OnlineMaterializer."""

from __future__ import annotations

from wine_rec.features.online_materializer import OnlineMaterializer


class TestWineCoreUpdated:
    def test_upserts_core_fields(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "WineCoreUpdated",
                "item_core_variety": ["Pinot Noir"],
                "item_core_region": "Burgundy",
                "item_core_producer": "DRC",
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_variety"] == ["Pinot Noir"]
        assert stored["item_core_region"] == "Burgundy"
        assert stored["item_core_producer"] == "DRC"
        assert "_updated_at" in stored

    def test_merges_with_existing(self, feature_store):
        feature_store.put_features(
            entity_type="wine_core",
            entity_id="wc_001",
            features={"item_core_variety": ["Merlot"], "item_core_region": "Bordeaux"},
        )
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={"event_type": "WineCoreUpdated", "item_core_region": "Burgundy"},
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_variety"] == ["Merlot"]  # not overwritten
        assert stored["item_core_region"] == "Burgundy"  # updated


class TestTextUnitAdded:
    def test_updates_text_embedding(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "TextUnitAdded",
                "text_embedding": [0.1, 0.2, 0.3],
                "embedding_version": "enc_v1",
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_text_embedding"] == [0.1, 0.2, 0.3]
        assert stored["_text_embedding_version"] == "enc_v1"


class TestStructUnitAdded:
    def test_updates_struct_fields(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "StructUnitAdded",
                "item_core_temporal_stage": "peak",
                "item_core_peak_proximity": 0.95,
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_temporal_stage"] == "peak"
        assert stored["item_core_peak_proximity"] == 0.95


class TestPriceSnapshotAdded:
    def test_updates_price_fields(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_sku",
            entity_id="ws_001",
            event={
                "event_type": "PriceSnapshotAdded",
                "item_sku_median_price": 42000,
                "item_sku_in_stock": True,
                "item_sku_rarity_score": 0.85,
            },
        )
        stored = feature_store.get_features(entity_type="wine_sku", entity_id="ws_001")
        assert stored["item_sku_median_price"] == 42000
        assert stored["item_sku_in_stock"] is True
        assert stored["item_sku_rarity_score"] == 0.85


class TestEmbeddingEncoderRolled:
    def test_updates_embedding_and_version(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "EmbeddingEncoderRolled",
                "new_embedding": [0.5, 0.6],
                "encoder_version": "enc_v2",
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_text_embedding"] == [0.5, 0.6]
        assert stored["_embedding_encoder_version"] == "enc_v2"


class TestExpertAggregateUpdated:
    def test_updates_expert_fields(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "ExpertAggregateUpdated",
                "item_core_decay_weighted_rating_mean": 0.88,
                "item_core_authority_decay_score": 0.72,
                "item_core_consensus_category": "high_agreement",
                "item_core_expert_agreement_pct": 0.95,
                "item_core_inter_expert_variance": 0.003,
                "item_core_intra_expert_variance": 0.001,
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_decay_weighted_rating_mean"] == 0.88
        assert stored["item_core_consensus_category"] == "high_agreement"
        assert stored["item_core_expert_agreement_pct"] == 0.95
        assert "_updated_at" in stored

    def test_merges_with_existing_features(self, feature_store):
        feature_store.put_features(
            entity_type="wine_core",
            entity_id="wc_001",
            features={"item_core_variety": ["Pinot Noir"]},
        )
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "ExpertAggregateUpdated",
                "item_core_decay_weighted_rating_mean": 0.88,
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_variety"] == ["Pinot Noir"]
        assert stored["item_core_decay_weighted_rating_mean"] == 0.88


class TestTemporalV2Updated:
    def test_updates_temporal_v2_fields(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "TemporalV2Updated",
                "item_core_days_to_peak": 365,
                "item_core_peak_trajectory": "approaching",
                "item_core_merged_confidence": 0.85,
                "item_core_vintage_effect": 0.3,
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_days_to_peak"] == 365
        assert stored["item_core_peak_trajectory"] == "approaching"
        assert stored["item_core_merged_confidence"] == 0.85
        assert stored["item_core_vintage_effect"] == 0.3
        assert "_updated_at" in stored

    def test_ignores_non_temporal_fields(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "TemporalV2Updated",
                "item_core_days_to_peak": 365,
                "item_core_variety": "Pinot Noir",  # not in _TEMPORAL_V2_FIELDS
            },
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored["item_core_days_to_peak"] == 365
        assert "item_core_variety" not in stored


class TestUnknownEvent:
    def test_unknown_event_type_is_silently_ignored(self, feature_store):
        mat = OnlineMaterializer(feature_store=feature_store)
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={"event_type": "SomeUnknownEvent"},
        )
        stored = feature_store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert stored == {}
