"""E2E: event ingestion -> feature materializer -> feature store."""

from __future__ import annotations

import pytest

from tests.conftest import InMemoryFeatureStore
from wine_rec.features.online_materializer import OnlineMaterializer


@pytest.mark.e2e
class TestEventToFeatureFlow:
    """Test the full event -> materializer -> feature store flow."""

    def test_sequential_events_accumulate(self):
        store = InMemoryFeatureStore()
        mat = OnlineMaterializer(feature_store=store)

        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "WineCoreUpdated",
                "item_core_variety": ["Pinot Noir"],
                "item_core_region": "Burgundy",
            },
        )
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "TextUnitAdded",
                "text_embedding": [0.1, 0.2, 0.3],
            },
        )
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "StructUnitAdded",
                "item_core_temporal_stage": "peak",
                "item_core_peak_proximity": 0.95,
            },
        )

        features = store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert features["item_core_variety"] == ["Pinot Noir"]
        assert features["item_core_text_embedding"] == [0.1, 0.2, 0.3]
        assert features["item_core_temporal_stage"] == "peak"
        assert features["item_core_peak_proximity"] == 0.95

    def test_price_event_for_sku(self):
        store = InMemoryFeatureStore()
        mat = OnlineMaterializer(feature_store=store)

        mat.process_event(
            entity_type="wine_sku",
            entity_id="ws_001",
            event={
                "event_type": "PriceSnapshotAdded",
                "item_sku_median_price": 55000,
                "item_sku_in_stock": True,
                "item_sku_rarity_score": 0.85,
            },
        )
        features = store.get_features(entity_type="wine_sku", entity_id="ws_001")
        assert features["item_sku_median_price"] == 55000
        assert features["item_sku_rarity_score"] == 0.85

    def test_encoder_roll_updates_embedding(self):
        store = InMemoryFeatureStore()
        mat = OnlineMaterializer(feature_store=store)

        # First set text embedding
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "TextUnitAdded",
                "text_embedding": [0.1, 0.2],
            },
        )
        # Then roll encoder
        mat.process_event(
            entity_type="wine_core",
            entity_id="wc_001",
            event={
                "event_type": "EmbeddingEncoderRolled",
                "new_embedding": [0.9, 0.8],
                "encoder_version": "enc_v2",
            },
        )

        features = store.get_features(entity_type="wine_core", entity_id="wc_001")
        assert features["item_core_text_embedding"] == [0.9, 0.8]
        assert features["_embedding_encoder_version"] == "enc_v2"
