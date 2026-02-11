"""Model registry protocol."""

from __future__ import annotations

from typing import Any, Protocol


class ModelArtifact(Protocol):
    """Loaded model artifact."""

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """Run prediction."""
        ...

    @property
    def version(self) -> str:
        """Model version identifier."""
        ...


class ModelRegistry(Protocol):
    """Model registry interface."""

    def load_model(self, *, model_name: str, version: str) -> ModelArtifact:
        """Load a model artifact by name and version."""
        ...

    def get_latest_version(self, *, model_name: str) -> str:
        """Get the latest approved model version."""
        ...
