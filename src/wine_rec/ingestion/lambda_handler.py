"""AWS Lambda handler for event ingestion.

API Gateway → Lambda → Kinesis (RFC-INFRA-IMPL-013 §1-2).
"""

from __future__ import annotations

import json
from typing import Any

from wine_rec.common.logging import get_logger
from wine_rec.ingestion.validator import validate_and_route


log = get_logger(__name__)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda entry point for API Gateway HTTP API."""
    body: dict[str, Any] = event.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)

    log_type = body.get("schema_version", "")

    try:
        validate_and_route(log_type=log_type, payload=body)
    except (KeyError, ValueError) as exc:
        log.warning("validation_failed", log_type=log_type, error=str(exc))
        return {"statusCode": 400, "body": f"Validation error: {exc}"}

    return {"statusCode": 202, "body": "accepted"}
