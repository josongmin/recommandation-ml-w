"""AWS Lambda handler for event ingestion.

API Gateway → Lambda → Kinesis (RFC-INFRA-IMPL-013 §1-2).
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
from pydantic import ValidationError

from wine_rec.common.logging import get_logger
from wine_rec.ingestion.validator import validate_and_route
from wine_rec.schemas.events import ActionEvent, ImpressionEvent, OrderEvent, PolicyEvent


log = get_logger(__name__)

# Environment
KINESIS_STREAM_NAME = os.environ.get("KINESIS_STREAM_NAME", "wine-rec-dev-events-stream")

# Kinesis client (reused across invocations)
kinesis_client = boto3.client("kinesis")


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda entry point for API Gateway HTTP API."""
    # Parse body
    body: dict[str, Any] = event.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)

    log_type = body.get("schema_version", "")

    try:
        # Validate
        validated_event = validate_and_route(log_type=log_type, payload=body)

        # Send to Kinesis
        response = kinesis_client.put_record(
            StreamName=KINESIS_STREAM_NAME,
            Data=validated_event.model_dump_json(),
            PartitionKey=_partition_key(validated_event),
        )

        log.info(
            "event_accepted",
            log_type=log_type,
            sequence_number=response["SequenceNumber"],
        )

        return {
            "statusCode": 202,
            "body": json.dumps(
                {
                    "message": "Event accepted",
                    "sequence_number": response["SequenceNumber"],
                }
            ),
        }

    except (KeyError, ValueError, ValidationError) as exc:
        log.warning("validation_failed", log_type=log_type, error=str(exc))
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Validation error: {exc}"}),
        }
    except Exception as exc:
        log.error("internal_error", error=str(exc))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def _partition_key(
    event: ImpressionEvent | ActionEvent | OrderEvent | PolicyEvent,
) -> str:
    """Determine Kinesis partition key based on event type."""
    if isinstance(event, ImpressionEvent):
        return event.user_id
    if isinstance(event, ActionEvent):
        return event.wine_sku_id
    if isinstance(event, OrderEvent):
        return event.user_id
    if isinstance(event, PolicyEvent):
        return event.impression_id
    return "unknown"
