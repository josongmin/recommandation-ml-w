"""SSOT log event schemas (RFC-LOG-SCHEMA-009)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ── Enums ──


class ActionType(StrEnum):
    """User action types."""

    VIEW = "VIEW"
    CLICK = "CLICK"
    DWELL = "DWELL"
    LIKE = "LIKE"
    WISHLIST = "WISHLIST"
    CART = "CART"


class Surface(StrEnum):
    """Recommendation surfaces."""

    HOME = "home"
    SEARCH = "search"
    DETAIL = "detail"
    CART = "cart"
    PUSH = "push"


# ── Events ──


class ImpressionEvent(BaseModel):
    """Impression log (RFC-LOG-SCHEMA-009 §2)."""

    impression_id: str
    user_id: str
    shown_ts: datetime
    surface: Surface
    items: list[str] = Field(description="wine_sku_ids shown")
    schema_version: str = "impression_log_v1"


class PolicyEvent(BaseModel):
    """Policy log (RFC-LOG-SCHEMA-009 §3).

    propensity는 스키마상 nullable이지만 운영 관점에서 사실상 필수.
    누락률 >5% 경보, >20% 차단 (RFC-LOG-SCHEMA-009 propensity 강제 규칙).
    """

    impression_id: str
    model_version: str
    feature_set_version: str
    candidates: list[CandidateScore]
    exploration_policy: str | None = None
    propensity: float | None = None
    propensity_model: str | None = Field(
        default=None, description="'logged'|'estimated' + version tag"
    )
    schema_version: str = "policy_log_v1"


class CandidateScore(BaseModel):
    """Single candidate in policy log."""

    wine_sku_id: str
    score: float
    source: str = Field(description="recall source name")


class ActionEvent(BaseModel):
    """Action log (RFC-LOG-SCHEMA-009 §4)."""

    impression_id: str
    wine_core_id: str
    wine_sku_id: str
    action_type: ActionType
    action_ts: datetime
    dwell_ms: int | None = None
    schema_version: str = "action_log_v1"


class OrderEvent(BaseModel):
    """Order log (RFC-LOG-SCHEMA-009 §5)."""

    order_id: str
    user_id: str
    wine_sku_id: str
    order_ts: datetime
    quantity: int = 1
    price: float | None = None
    impression_id: str | None = None
    schema_version: str = "order_log_v1"


# forward ref 해결
PolicyEvent.model_rebuild()
