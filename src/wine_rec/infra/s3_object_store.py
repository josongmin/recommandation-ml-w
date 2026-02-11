"""S3 implementation of ObjectStore."""

from __future__ import annotations

import json
from typing import Any

import boto3

from wine_rec.common.config import get_settings


class S3ObjectStore:
    """ObjectStore backed by S3."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = boto3.client("s3", region_name=settings.aws_region)

    def get_bytes(self, *, bucket: str, key: str) -> bytes:
        """Read raw bytes from S3."""
        resp = self._client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def put_bytes(self, *, bucket: str, key: str, data: bytes) -> None:
        """Write raw bytes to S3."""
        self._client.put_object(Bucket=bucket, Key=key, Body=data)

    def get_json(self, *, bucket: str, key: str) -> dict[str, Any]:
        """Read and parse JSON from S3."""
        raw = self.get_bytes(bucket=bucket, key=key)
        return json.loads(raw)

    def put_json(self, *, bucket: str, key: str, data: dict[str, Any]) -> None:
        """Serialize and write JSON to S3."""
        self.put_bytes(bucket=bucket, key=key, data=json.dumps(data, default=str).encode())

    def list_keys(self, *, bucket: str, prefix: str) -> list[str]:
        """List object keys under a prefix."""
        resp = self._client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        contents: list[dict[str, Any]] = resp.get("Contents", [])  # type: ignore[assignment]
        return [str(obj["Key"]) for obj in contents]
