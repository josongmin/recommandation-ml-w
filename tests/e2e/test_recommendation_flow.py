"""E2E test for full recommendation flow with LocalStack."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import torch
import torch.nn as nn

from wine_rec.infra.dynamodb_feature_store import DynamoDBFeatureStore
from wine_rec.infra.s3_model_registry import S3ModelRegistry
from wine_rec.serving.recommender import Recommender


# Simple mock model for testing
class MockTwoTowerModel(nn.Module):
    """Mock Two-Tower model for E2E testing."""

    def __init__(self, embedding_dim: int = 64) -> None:
        super().__init__()
        self.user_embedding = nn.Embedding(1000, embedding_dim)
        self.item_embedding = nn.Embedding(1000, embedding_dim)

    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """Forward pass."""
        user_emb = self.user_embedding(user_ids)
        item_emb = self.item_embedding(item_ids)
        return (user_emb * item_emb).sum(dim=-1)


@pytest.fixture(scope="module")
def localstack_endpoint() -> str:
    """LocalStack endpoint URL."""
    return os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


@pytest.fixture(scope="module")
def setup_s3_models(localstack_endpoint: str) -> None:
    """Setup mock models in S3."""
    model_registry = S3ModelRegistry(
        bucket_name="wine-rec-dev-models",
        endpoint_url=localstack_endpoint,
    )

    # Create and save mock model
    model = MockTwoTowerModel()

    model_registry.save_model(
        model=model,
        model_name="two_tower",
        version="v1",
        metadata={
            "embedding_dim": 64,
            "trained_at": "2024-02-12",
            "dataset": "wine_v1",
        },
        set_as_latest=True,
    )


@pytest.fixture(scope="module")
def setup_dynamodb_features(localstack_endpoint: str) -> None:
    """Setup mock features in DynamoDB."""
    # Set AWS endpoint for boto3
    os.environ["AWS_ENDPOINT_URL"] = localstack_endpoint

    feature_store = DynamoDBFeatureStore(table_name="wine-rec-dev-features")

    # Add user features
    feature_store.put_features(
        entity_type="user",
        entity_id="user_test_001",
        features={
            "user_age": 35,
            "user_country": "US",
            "user_total_orders": 15,
            "user_avg_order_value": 120.50,
            "user_wine_preference": "red",
        },
    )

    # Add popular items fallback
    feature_store.put_features(
        entity_type="popular_items",
        entity_id="global",
        features={
            "items": [f"wine_{i:03d}" for i in range(20)],
        },
    )


@pytest.mark.e2e
@pytest.mark.skipif(
    os.getenv("SKIP_E2E") == "1",
    reason="E2E tests require LocalStack running",
)
class TestRecommendationFlow:
    """E2E tests for recommendation flow."""

    def test_full_recommendation_with_model(
        self,
        localstack_endpoint: str,
        setup_s3_models: None,
        setup_dynamodb_features: None,
    ) -> None:
        """Test full recommendation flow with model loading."""
        # Set AWS endpoint
        os.environ["AWS_ENDPOINT_URL"] = localstack_endpoint

        # Initialize components
        feature_store = DynamoDBFeatureStore(table_name="wine-rec-dev-features")
        model_registry = S3ModelRegistry(
            bucket_name="wine-rec-dev-models",
            endpoint_url=localstack_endpoint,
        )

        # Create recommender
        recommender = Recommender(
            feature_store=feature_store,
            model_registry=model_registry,
        )

        # Get recommendations
        recommendations = recommender.recommend(
            user_id="user_test_001",
            n_items=10,
        )

        # Assertions
        assert len(recommendations) > 0, "Should return recommendations"
        assert len(recommendations) <= 10, "Should not exceed requested items"

        for rec in recommendations:
            assert "wine_sku_id" in rec
            assert "score" in rec
            assert isinstance(rec["score"], int | float)
            assert rec["score"] >= 0.0

    def test_recommendation_with_fallback(
        self,
        localstack_endpoint: str,
        setup_dynamodb_features: None,
    ) -> None:
        """Test recommendation falls back to popularity when model unavailable."""
        os.environ["AWS_ENDPOINT_URL"] = localstack_endpoint

        feature_store = DynamoDBFeatureStore(table_name="wine-rec-dev-features")

        # No model registry
        recommender = Recommender(
            feature_store=feature_store,
            model_registry=None,
        )

        recommendations = recommender.recommend(
            user_id="user_test_001",
            n_items=10,
        )

        assert len(recommendations) > 0, "Should return popularity fallback"
        assert all("wine_sku_id" in rec for rec in recommendations)

    def test_feature_store_integration(
        self,
        localstack_endpoint: str,
        setup_dynamodb_features: None,
    ) -> None:
        """Test feature store retrieval."""
        os.environ["AWS_ENDPOINT_URL"] = localstack_endpoint

        feature_store = DynamoDBFeatureStore(table_name="wine-rec-dev-features")

        # Get user features
        features = feature_store.get_features(
            entity_type="user",
            entity_id="user_test_001",
        )

        assert features is not None
        assert features.get("user_age") == 35
        assert features.get("user_country") == "US"
        assert features.get("user_wine_preference") == "red"

    def test_model_registry_integration(
        self,
        localstack_endpoint: str,
        setup_s3_models: None,
    ) -> None:
        """Test model registry load."""
        model_registry = S3ModelRegistry(
            bucket_name="wine-rec-dev-models",
            endpoint_url=localstack_endpoint,
        )

        # Get latest version
        latest = model_registry.get_latest_version(model_name="two_tower")
        assert latest == "v1"

        # Load model
        artifact = model_registry.load_model(model_name="two_tower", version="v1")
        assert artifact.version == "v1"

        # Test prediction
        result = artifact.predict({"user_id": "test_user", "n_items": 5})
        assert "items" in result
        assert len(result["items"]) == 5


@pytest.mark.e2e
class TestFeatureManifest:
    """Test feature manifest loading."""

    def test_manifest_exists(self) -> None:
        """Test that feature manifest file exists."""
        manifest_path = Path("manifests/feature_manifest_v1.yaml")
        assert manifest_path.exists(), f"Manifest not found at {manifest_path}"

    def test_manifest_loads(self) -> None:
        """Test that manifest can be loaded."""
        from wine_rec.features.offline_builder import _load_manifest

        manifest = _load_manifest(Path("manifests/feature_manifest_v1.yaml"))

        assert manifest.manifest_version == "1.0"
        assert len(manifest.features) > 0

        # Check critical features
        critical_features = [f for f in manifest.features if f.critical]
        assert len(critical_features) >= 10, "Should have at least 10 critical features"

        # Verify required feature fields
        for feature in manifest.features:
            assert feature.name
            assert feature.type in ["numerical", "categorical", "boolean"]
            assert feature.time_travel_rule is not None
