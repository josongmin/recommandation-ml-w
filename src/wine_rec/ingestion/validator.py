"""Event validation and routing (RFC-LOG-SCHEMA-009)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from wine_rec.schemas.events import (
    ActionEvent,
    ImpressionEvent,
    OrderEvent,
    PolicyEvent,
)


if TYPE_CHECKING:
    from pydantic import BaseModel


_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "impression_log_v1": ImpressionEvent,
    "action_log_v1": ActionEvent,
    "order_log_v1": OrderEvent,
    "policy_log_v1": PolicyEvent,
}


def validate_and_route(*, log_type: str, payload: dict[str, Any]) -> BaseModel:
    """Validate event payload against its schema.

    Raises:
        KeyError: If log_type is unknown.
        pydantic.ValidationError: If payload doesn't match schema.
    """
    schema_cls = _SCHEMA_MAP.get(log_type)
    if schema_cls is None:
        msg = f"Unknown log type: {log_type}"
        raise KeyError(msg)
    return schema_cls.model_validate(payload)
