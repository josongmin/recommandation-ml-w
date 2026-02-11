"""Kinesis implementation of EventStream."""

from __future__ import annotations

import json
from typing import Any

import boto3

from wine_rec.common.config import get_settings


class KinesisEventStream:
    """EventStream backed by Kinesis Data Streams On-demand."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = boto3.client("kinesis", region_name=settings.aws_region)

    def put_event(self, *, stream_name: str, partition_key: str, data: dict[str, Any]) -> None:
        """Publish a single event to Kinesis."""
        self._client.put_record(
            StreamName=stream_name,
            Data=json.dumps(data, default=str).encode(),
            PartitionKey=partition_key,
        )

    def put_events_batch(self, *, stream_name: str, records: list[dict[str, Any]]) -> int:
        """Publish a batch of events. Returns number of failed records."""
        kinesis_records: list[dict[str, str | bytes]] = [
            {
                "Data": json.dumps(r["data"], default=str).encode(),
                "PartitionKey": str(r["partition_key"]),
            }
            for r in records
        ]
        resp = self._client.put_records(StreamName=stream_name, Records=kinesis_records)  # type: ignore[arg-type]
        failed: int = resp.get("FailedRecordCount", 0)
        return failed
