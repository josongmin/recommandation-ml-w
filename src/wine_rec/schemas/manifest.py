"""Manifest schemas (RFC-DATASET-BUILDER-011, RFC-FEATURE-MANIFEST-010)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ── Dataset Manifest (RFC-DATASET-BUILDER-011 §8) ──


class DatasetManifest(BaseModel):
    """dataset_manifest_v1 — 학습 데이터 재현의 SSOT.

    어느 항목이든 변경되면 dataset_version을 반드시 bump (Non-Negotiable).
    """

    dataset_version: str
    split_id: str
    feature_set_version: str
    embedding_versions: dict[str, str] = Field(default_factory=dict)
    join_rules_json: JoinRules
    negative_sampling_spec_json: NegativeSamplingSpec
    attribution_spec_json: AttributionSpec
    candidate_budget_spec_version: str
    created_at: datetime


class JoinRules(BaseModel):
    """Time-travel join rules."""

    as_of_ts_le_event_ts: bool = True
    published_at_le_event_ts: bool = True


class NegativeSamplingSpec(BaseModel):
    """Negative sampling specification (seed 포함 필수)."""

    method: str = "shown_but_no_action"
    cap_per_pos: int = 10
    seed: int = Field(description="재현성을 위한 고정 seed")


class AttributionSpec(BaseModel):
    """Attribution rule specification."""

    rule: str = "last_impression_within_window"
    version: str = "attr_v1"
    window_days: int = 7


# ── Feature Manifest (RFC-FEATURE-MANIFEST-010 §1) ──


class FeatureTier(StrEnum):
    """Feature importance tier for parity gate."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    EXPERIMENTAL = "experimental"


class TimeTravelRule(BaseModel):
    """Feature time-travel join rule."""

    rule: str = Field(description="as_of_ts_le_event_ts|published_at_le_event_ts|none")
    timestamp_field: str


class FeatureSource(BaseModel):
    """Feature source reference."""

    table: str
    key: str
    value_path: str | None = None


class FeatureDef(BaseModel):
    """Single feature definition in manifest."""

    name: str
    dtype: str = Field(description="float|int|string|bool|vector|json")
    source: FeatureSource
    time_travel_rule: TimeTravelRule
    recipe_version: str
    default: Any = None
    null_policy: str = Field(default="default", description="error|default|allow_null")
    description: str = ""
    owner: str | None = None
    tier: FeatureTier = FeatureTier.EXPERIMENTAL


class EntityManifest(BaseModel):
    """Entity-level feature manifest."""

    entity_type: str = Field(description="user|session|wine_core|wine_sku|context|user_item")
    join_keys: list[str]
    features: list[FeatureDef]


class FeatureManifest(BaseModel):
    """feature_manifest_v1 — feature 정의의 SSOT."""

    feature_set_version: str
    generated_at: datetime
    entities: list[EntityManifest]
