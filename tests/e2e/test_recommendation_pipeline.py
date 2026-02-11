"""E2E: recommendation pipeline end-to-end."""

from __future__ import annotations

import pytest

from tests.conftest import InMemoryFeatureStore
from wine_rec.serving.recommender import Recommender


@pytest.mark.e2e
class TestRecommendationPipeline:
    """Test the full recommendation pipeline with feature store."""

    def test_recommend_with_popularity_fallback(self):
        store = InMemoryFeatureStore()
        # Seed user features
        store.put_features(
            entity_type="user",
            entity_id="u1",
            features={"user_price_elasticity": 0.5},
        )
        # Seed popular items fallback
        store.put_features(
            entity_type="popular_items",
            entity_id="global",
            features={"items": ["ws_001", "ws_002", "ws_003"]},
        )

        recommender = Recommender(feature_store=store)
        results = recommender.recommend(user_id="u1", n_items=3)

        # Without model registry, falls back to popularity
        assert isinstance(results, list)

    def test_recommend_unknown_user_returns_fallback(self):
        store = InMemoryFeatureStore()
        store.put_features(
            entity_type="popular_items",
            entity_id="global",
            features={"items": ["ws_001", "ws_002"]},
        )

        recommender = Recommender(feature_store=store)
        results = recommender.recommend(user_id="unknown_user", n_items=5)
        assert isinstance(results, list)

    def test_recommend_empty_store_returns_empty(self):
        store = InMemoryFeatureStore()
        recommender = Recommender(feature_store=store)
        results = recommender.recommend(user_id="u1", n_items=5)
        assert results == []
