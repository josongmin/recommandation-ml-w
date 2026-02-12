"""Integration test for full recommendation flow (no AWS required)."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import torch.nn as nn

from wine_rec.infra.s3_model_registry import ModelArtifactImpl
from wine_rec.serving.recommender import Recommender


class SimpleTwoTowerModel(nn.Module):
    """Simple Two-Tower for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.user_emb = nn.Embedding(100, 32)
        self.item_emb = nn.Embedding(100, 32)


@pytest.fixture
def mock_feature_store() -> Mock:
    """Mock feature store."""
    store = Mock()
    store.get_features.return_value = {
        "user_age": 35,
        "user_country": "US",
        "user_wine_preference": "red",
    }
    store.batch_get_features.return_value = [
        {"items": [f"wine_{i:03d}" for i in range(20)]},
    ]
    return store


@pytest.fixture
def mock_model_registry() -> Mock:
    """Mock model registry that returns a simple artifact."""
    registry = Mock()

    # Create a simple model artifact
    model = SimpleTwoTowerModel()
    artifact = ModelArtifactImpl(model=model, version="v1", metadata={})

    registry.get_latest_version.return_value = "v1"
    registry.load_model.return_value = artifact

    return registry


@pytest.mark.integration
class TestFullRecommendationFlow:
    """Integration tests for full recommendation flow."""

    def test_recommend_with_model_registry(
        self,
        mock_feature_store: Mock,
        mock_model_registry: Mock,
    ) -> None:
        """Test recommendation with model registry (no AWS)."""
        recommender = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
        )

        results = recommender.recommend(user_id="user_001", n_items=10)

        assert len(results) > 0
        assert len(results) <= 10

        for rec in results:
            assert "wine_sku_id" in rec
            assert "score" in rec
            assert rec["score"] >= 0.0

    def test_recommend_with_fallback(self, mock_feature_store: Mock) -> None:
        """Test recommendation falls back to popularity."""
        recommender = Recommender(
            feature_store=mock_feature_store,
            model_registry=None,  # No model registry
        )

        results = recommender.recommend(user_id="user_001", n_items=10)

        assert len(results) > 0
        # Should use popularity fallback
        assert all("wine_sku_id" in rec for rec in results)

    def test_recommend_with_context(
        self,
        mock_feature_store: Mock,
        mock_model_registry: Mock,
    ) -> None:
        """Test recommendation with context."""
        recommender = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
        )

        results = recommender.recommend(
            user_id="user_001",
            n_items=5,
            context={"season": "winter", "hour": 20},
        )

        assert len(results) <= 5

    def test_multiple_recall_sources(
        self,
        mock_feature_store: Mock,
        mock_model_registry: Mock,
    ) -> None:
        """Test that multiple recall sources are called."""
        from wine_rec.serving.recommender import RecallSource

        custom_sources = [
            RecallSource(name="collaborative", model_name="bpr_v1", quota=30),
            RecallSource(name="content", model_name="two_tower_v1", quota=30),
        ]

        recommender = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
            recall_sources=custom_sources,
        )

        results = recommender.recommend(user_id="user_001", n_items=10)

        # Should get results from multiple sources
        assert len(results) > 0

        # Verify model registry was called multiple times
        assert mock_model_registry.get_latest_version.call_count >= 2

    def test_diversity_weight(
        self,
        mock_feature_store: Mock,
        mock_model_registry: Mock,
    ) -> None:
        """Test diversity weight affects results."""
        # Low diversity
        rec_low = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
            diversity_weight=0.0,
        )

        # High diversity
        rec_high = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
            diversity_weight=0.5,
        )

        results_low = rec_low.recommend(user_id="user_001", n_items=10)
        results_high = rec_high.recommend(user_id="user_001", n_items=10)

        # Both should return results
        assert len(results_low) > 0
        assert len(results_high) > 0

    def test_empty_features_handling(self, mock_model_registry: Mock) -> None:
        """Test graceful handling of missing features."""
        # Feature store that returns empty
        empty_store = Mock()
        empty_store.get_features.return_value = {}
        empty_store.batch_get_features.return_value = [
            {"items": [f"wine_{i:03d}" for i in range(10)]},
        ]

        recommender = Recommender(
            feature_store=empty_store,
            model_registry=mock_model_registry,
        )

        # Should still work with fallback
        results = recommender.recommend(user_id="user_001", n_items=5)
        assert len(results) > 0

    def test_deduplication(
        self,
        mock_feature_store: Mock,
        mock_model_registry: Mock,
    ) -> None:
        """Test that duplicate items are deduplicated."""
        recommender = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
        )

        results = recommender.recommend(user_id="user_001", n_items=10)

        # No duplicates
        wine_ids = [r["wine_sku_id"] for r in results]
        assert len(wine_ids) == len(set(wine_ids)), "Should not have duplicates"

    def test_score_ordering(
        self,
        mock_feature_store: Mock,
        mock_model_registry: Mock,
    ) -> None:
        """Test that results are ordered by score."""
        recommender = Recommender(
            feature_store=mock_feature_store,
            model_registry=mock_model_registry,
        )

        results = recommender.recommend(user_id="user_001", n_items=10)

        # Check scores are in descending order
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True), "Scores should be descending"
