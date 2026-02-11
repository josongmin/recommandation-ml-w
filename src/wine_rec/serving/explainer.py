"""Recommendation explainer (RFC-E2E-PIPELINE-006 §8).

v1: Simple format-string templates (Phase A-G)
v2: Structured explanations with provenance tracking (Phase H SOTA)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── v1 Templates (backward compatible) ──

EXPLANATION_TEMPLATES: dict[str, str] = {
    "temporal": "현재 최적 음용 시기인 와인입니다 (peak stage)",
    "expert": "전문가 평균 {score}점, 높은 합의도 ({consensus}%)",
    "scarcity": "연간 생산량 {volume}병, 희소성 높음",
    "price": "가격 대비 전문가 평가가 우수합니다",
    "discovery": "같은 지역의 숨겨진 생산자 발견",
}


def generate_explanation(*, reason: str, context: dict[str, Any] | None = None) -> str:
    """Generate a human-readable explanation for a recommendation."""
    template = EXPLANATION_TEMPLATES.get(reason, "")
    if not template:
        return ""
    try:
        return template.format(**(context or {}))
    except KeyError:
        return template


# ── v2 Structured Explanations (Phase H SOTA) ──

EXPLANATION_TEMPLATES_V2: dict[str, str] = {
    "temporal_peak": "현재 최적 음용 시기입니다 (confidence: {confidence:.0%})",
    "temporal_approaching": "최적 음용 시기에 다가가고 있습니다 ({days_to_peak}일 후 예상)",
    "temporal_declining": "음용 적기를 지나고 있습니다",
    "expert_high_consensus": "전문가 {n_experts}명 평균 {score}점, 높은 합의도 ({agreement:.0%})",
    "expert_controversial": "전문가 의견이 나뉩니다 (평균 {score}점, 합의도 {agreement:.0%})",
    "expert_match": "당신이 신뢰하는 전문가들이 높이 평가한 와인입니다",
    "scarcity": "연간 생산량 {volume}병, 희소성 높음",
    "price_quality": "가격 대비 전문가 평가가 우수합니다",
    "discovery": "같은 지역의 숨겨진 생산자 발견",
}


@dataclass(frozen=True)
class ExplanationResult:
    """Structured explanation output with provenance tracking (SSOT)."""

    reason: str
    template_version: str
    text: str
    provenance: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


def generate_explanation_v2(
    *,
    reason: str,
    context: dict[str, Any] | None = None,
    template_version: str = "v2",
) -> ExplanationResult:
    """Generate structured explanation with provenance tracking.

    Args:
        reason: Explanation reason key (e.g. "temporal_peak", "expert_high_consensus").
        context: Template context values.
        template_version: "v1" uses legacy templates, "v2" uses expanded set.

    Returns:
        ExplanationResult with text, provenance, and confidence.
    """
    templates = EXPLANATION_TEMPLATES_V2 if template_version == "v2" else EXPLANATION_TEMPLATES
    ctx = context or {}

    template = templates.get(reason, "")
    if not template:
        return ExplanationResult(
            reason=reason,
            template_version=template_version,
            text="",
            provenance=ctx,
            confidence=0.0,
        )

    try:
        text = template.format(**ctx)
    except (KeyError, ValueError):
        text = template

    confidence = ctx.get("confidence", 1.0)
    if not isinstance(confidence, (int, float)):
        confidence = 1.0

    return ExplanationResult(
        reason=reason,
        template_version=template_version,
        text=text,
        provenance=ctx,
        confidence=float(confidence),
    )
