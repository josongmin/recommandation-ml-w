"""IR (Information Representation) schemas (RFC-IR-SCHEMA-007, RFC-REC-EXT-004).

v1 schemas: Phase A-G (16-week MVP)
v2 schemas: Phase H (SOTA — Expert-Aware + Temporal IR Enhancement)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ── v1 Schemas ──────────────────────────────────────────────


class WineTextIR(BaseModel):
    """wine_text_ir_v1 — text embedding."""

    wine_core_id: str
    embedding_ref: str
    embedding_model: str
    chunk_strategy: str
    text_version: str
    as_of_ts: datetime


class WineTemporalIR(BaseModel):
    """wine_temporal_ir_v1 — drinking window (RFC-REC-EXT-004 §2-2)."""

    wine_core_id: str
    vintage_year: int
    drink_from_year: int
    drink_to_year: int
    current_stage: str = Field(description="too_young|early|peak|past")
    estimation_method: str = Field(description="rule|model|expert")
    confidence: float = Field(ge=0.0, le=1.0)
    as_of_ts: datetime


class WineReviewAggregateIR(BaseModel):
    """wine_review_aggregate_ir_v1 — expert-aware aggregate (RFC-REC-EXT-004 §2-1)."""

    wine_core_id: str
    weighted_rating_mean: float
    authority_weighted_count: int
    critic_consensus_score: float = Field(description="전문가 간 의견 일치도 (분산의 역수)")
    discrepancy_note: str | None = None
    as_of_ts: datetime


class WineScarcityIR(BaseModel):
    """wine_scarcity_ir_v1 (RFC-REC-EXT-004 §4-2)."""

    wine_core_id: str
    production_volume_est: int | None = None
    rarity_score: float = Field(ge=0.0, le=1.0)
    market_scope: str = "global"
    scarcity_version: str


# ── v2 Enums ────────────────────────────────────────────────


class ConsensusCategory(StrEnum):
    """Expert consensus classification (R2)."""

    HIGH_AGREEMENT = "high_agreement"
    MODERATE = "moderate"
    CONTROVERSIAL = "controversial"
    INSUFFICIENT = "insufficient"


class PeakTrajectory(StrEnum):
    """Peak trajectory classification (R3)."""

    APPROACHING = "approaching"
    AT_PEAK = "at_peak"
    DECLINING = "declining"
    UNKNOWN = "unknown"


# ── v2 Schemas ──────────────────────────────────────────────


class WineReviewAggregateIRv2(BaseModel):
    """wine_review_aggregate_ir_v2 — expert-aware with temporal decay (RFC-SOTA-ROADMAP-012 R2)."""

    wine_core_id: str

    # Backward-compatible v1 fields
    weighted_rating_mean: float
    authority_weighted_count: int
    critic_consensus_score: float

    # Temporal decay
    decay_weighted_rating_mean: float = Field(
        description="Authority-weighted mean with temporal decay on review age",
    )
    authority_decay_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Combined authority+recency weight score (0-1)",
    )

    # Variance decomposition
    inter_expert_variance: float = Field(
        ge=0.0,
        description="Variance between different expert reviewers",
    )
    intra_expert_variance: float = Field(
        ge=0.0,
        description="Avg variance within same expert's reviews over time",
    )

    # Consensus
    consensus_category: ConsensusCategory
    expert_agreement_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of experts within 0.1 of the weighted mean rating",
    )

    discrepancy_note: str | None = None
    as_of_ts: datetime


class WineTemporalIRv2(BaseModel):
    """wine_temporal_ir_v2 — model-aware drinking window (RFC-SOTA-ROADMAP-012 R3)."""

    wine_core_id: str
    vintage_year: int

    # Drinking window
    drink_from_year: int
    drink_to_year: int
    current_stage: str = Field(description="too_young|early|peak|past")

    # Multi-method estimation
    estimation_method: str = Field(description="rule|model|expert|ensemble")
    rule_confidence: float = Field(ge=0.0, le=1.0)
    model_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    expert_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    merged_confidence: float = Field(ge=0.0, le=1.0)

    # Peak trajectory
    peak_trajectory: PeakTrajectory
    days_to_peak: int | None = Field(
        default=None,
        description="Signed: negative=past peak, positive=before peak",
    )

    # Vintage effect
    vintage_effect_score: float = Field(
        default=0.0,
        description="Vintage quality effect on window (-1 to 1)",
    )

    as_of_ts: datetime


class ExpertProfileIR(BaseModel):
    """expert_profile_ir_v1 — expert classification and profiling (RFC-SOTA-ROADMAP-012 R2)."""

    author_id: str
    author_type: str = Field(description="critic|expert|user|anonymous")
    review_count: int
    wine_region_coverage: list[str] = Field(default_factory=list)
    avg_rating_given: float
    rating_variance: float
    authority_score: float = Field(ge=0.0, le=1.0)
    specialization_tags: list[str] = Field(default_factory=list)
    as_of_ts: datetime
