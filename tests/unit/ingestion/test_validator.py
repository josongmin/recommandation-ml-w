"""Tests for event validation."""

import pytest
from pydantic import ValidationError

from wine_rec.ingestion.validator import validate_and_route
from wine_rec.schemas.events import ActionEvent, ImpressionEvent


class TestValidateAndRoute:
    def test_valid_impression_event(self):
        payload = {
            "impression_id": "imp-001",
            "user_id": "user-001",
            "shown_ts": "2026-01-01T00:00:00Z",
            "surface": "home",
            "items": ["sku-001", "sku-002"],
            "schema_version": "impression_log_v1",
        }
        result = validate_and_route(log_type="impression_log_v1", payload=payload)
        assert isinstance(result, ImpressionEvent)
        assert result.impression_id == "imp-001"

    def test_valid_action_event(self):
        payload = {
            "impression_id": "imp-001",
            "wine_core_id": "core-001",
            "wine_sku_id": "sku-001",
            "action_type": "CLICK",
            "action_ts": "2026-01-01T00:01:00Z",
        }
        result = validate_and_route(log_type="action_log_v1", payload=payload)
        assert isinstance(result, ActionEvent)
        assert result.wine_sku_id == "sku-001"

    def test_unknown_log_type_raises(self):
        with pytest.raises(KeyError, match="Unknown log type"):
            validate_and_route(log_type="unknown_v1", payload={})

    def test_invalid_payload_raises(self):
        with pytest.raises(ValidationError):
            validate_and_route(log_type="impression_log_v1", payload={"bad": "data"})
