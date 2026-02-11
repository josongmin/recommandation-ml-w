"""Shared test fixtures."""

from __future__ import annotations

import json
from typing import Any

import pytest


# ── In-memory test doubles for contracts ──


class InMemoryFeatureStore:
    """Test double for FeatureStore protocol."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def get_features(self, *, entity_type: str, entity_id: str) -> dict[str, Any]:
        return self._data.get(f"{entity_type}#{entity_id}", {})

    def put_features(self, *, entity_type: str, entity_id: str, features: dict[str, Any]) -> None:
        self._data[f"{entity_type}#{entity_id}"] = features

    def batch_get_features(
        self, *, entity_type: str, entity_ids: list[str]
    ) -> list[dict[str, Any]]:
        return [self.get_features(entity_type=entity_type, entity_id=eid) for eid in entity_ids]


class InMemoryObjectStore:
    """Test double for ObjectStore protocol."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def get_bytes(self, *, bucket: str, key: str) -> bytes:
        return self._data[f"{bucket}/{key}"]

    def put_bytes(self, *, bucket: str, key: str, data: bytes) -> None:
        self._data[f"{bucket}/{key}"] = data

    def get_json(self, *, bucket: str, key: str) -> dict[str, object]:
        return json.loads(self.get_bytes(bucket=bucket, key=key))

    def put_json(self, *, bucket: str, key: str, data: dict[str, object]) -> None:
        self.put_bytes(bucket=bucket, key=key, data=json.dumps(data).encode())

    def list_keys(self, *, bucket: str, prefix: str) -> list[str]:
        full_prefix = f"{bucket}/{prefix}"
        return [k.removeprefix(f"{bucket}/") for k in self._data if k.startswith(full_prefix)]


# ── Fixtures ──


@pytest.fixture
def feature_store() -> InMemoryFeatureStore:
    """In-memory feature store for testing."""
    return InMemoryFeatureStore()


@pytest.fixture
def object_store() -> InMemoryObjectStore:
    """In-memory object store for testing."""
    return InMemoryObjectStore()
