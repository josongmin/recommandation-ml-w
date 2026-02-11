"""DynamoDB implementation of FeatureStore."""

from __future__ import annotations

import json
from typing import Any

import boto3

from wine_rec.common.config import get_settings


class DynamoDBFeatureStore:
    """FeatureStore backed by DynamoDB On-demand."""

    def __init__(self, *, table_name: str | None = None) -> None:
        settings = get_settings()
        self._table_name = table_name or settings.dynamodb_features_table
        self._client = boto3.resource("dynamodb", region_name=settings.aws_region).Table(
            self._table_name
        )

    def get_features(self, *, entity_type: str, entity_id: str) -> dict[str, Any]:
        """Retrieve features for an entity from DynamoDB."""
        resp = self._client.get_item(Key={"pk": f"{entity_type}#{entity_id}", "sk": "LATEST"})
        item = resp.get("Item")
        if not item:
            return {}
        raw = item.get("feature_json", "{}")
        return json.loads(raw) if isinstance(raw, str) else raw  # type: ignore[return-value]

    def put_features(self, *, entity_type: str, entity_id: str, features: dict[str, Any]) -> None:
        """Store features for an entity to DynamoDB."""
        self._client.put_item(
            Item={
                "pk": f"{entity_type}#{entity_id}",
                "sk": "LATEST",
                "feature_json": json.dumps(features, default=str),
            }
        )

    def batch_get_features(
        self, *, entity_type: str, entity_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Batch retrieve features."""
        return [self.get_features(entity_type=entity_type, entity_id=eid) for eid in entity_ids]
