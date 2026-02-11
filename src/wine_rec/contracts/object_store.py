"""Object store protocol (S3 abstraction)."""

from __future__ import annotations

from typing import Protocol


class ObjectStore(Protocol):
    """Object storage interface."""

    def get_bytes(self, *, bucket: str, key: str) -> bytes:
        """Read raw bytes from storage."""
        ...

    def put_bytes(self, *, bucket: str, key: str, data: bytes) -> None:
        """Write raw bytes to storage."""
        ...

    def get_json(self, *, bucket: str, key: str) -> dict[str, object]:
        """Read and parse JSON from storage."""
        ...

    def put_json(self, *, bucket: str, key: str, data: dict[str, object]) -> None:
        """Serialize and write JSON to storage."""
        ...

    def list_keys(self, *, bucket: str, prefix: str) -> list[str]:
        """List object keys under a prefix."""
        ...
