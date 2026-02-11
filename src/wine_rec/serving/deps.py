"""FastAPI dependency injection — wire contracts to infra adapters."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from wine_rec.infra.dynamodb_feature_store import DynamoDBFeatureStore
from wine_rec.infra.s3_object_store import S3ObjectStore


if TYPE_CHECKING:
    from wine_rec.contracts.feature_store import FeatureStore
    from wine_rec.contracts.object_store import ObjectStore


@lru_cache(maxsize=1)
def get_feature_store() -> FeatureStore:
    """Feature store singleton (DynamoDB in prod)."""
    return DynamoDBFeatureStore()


@lru_cache(maxsize=1)
def get_object_store() -> ObjectStore:
    """Object store singleton (S3 in prod)."""
    return S3ObjectStore()
