"""Event stream protocol (Kinesis abstraction)."""

from __future__ import annotations

from typing import Any, Protocol


class EventStream(Protocol):
    """Event streaming interface."""

    def put_event(self, *, stream_name: str, partition_key: str, data: dict[str, Any]) -> None:
        """Publish a single event to the stream."""
        ...

    def put_events_batch(
        self,
        *,
        stream_name: str,
        records: list[dict[str, Any]],
    ) -> int:
        """Publish a batch of events. Returns number of failed records."""
        ...
