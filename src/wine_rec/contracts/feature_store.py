"""Feature store protocol."""

from __future__ import annotations

from typing import Any, Protocol


class FeatureStore(Protocol):
    """Feature store interface (online serving)."""

    def get_features(self, *, entity_type: str, entity_id: str) -> dict[str, Any]:
        """Retrieve features for an entity."""
        ...

    def put_features(self, *, entity_type: str, entity_id: str, features: dict[str, Any]) -> None:
        """Store features for an entity."""
        ...

    def batch_get_features(
        self, *, entity_type: str, entity_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Batch retrieve features."""
        ...
