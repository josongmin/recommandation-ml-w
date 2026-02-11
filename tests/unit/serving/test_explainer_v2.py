"""Tests for v2 structured explanations (Phase H SOTA)."""

from __future__ import annotations

from wine_rec.serving.explainer import (
    EXPLANATION_TEMPLATES_V2,
    ExplanationResult,
    generate_explanation_v2,
)


class TestExplanationTemplatesV2:
    def test_temporal_templates_exist(self):
        assert "temporal_peak" in EXPLANATION_TEMPLATES_V2
        assert "temporal_approaching" in EXPLANATION_TEMPLATES_V2
        assert "temporal_declining" in EXPLANATION_TEMPLATES_V2

    def test_expert_templates_exist(self):
        assert "expert_high_consensus" in EXPLANATION_TEMPLATES_V2
        assert "expert_controversial" in EXPLANATION_TEMPLATES_V2
        assert "expert_match" in EXPLANATION_TEMPLATES_V2


class TestGenerateExplanationV2:
    def test_v2_temporal_peak(self):
        result = generate_explanation_v2(
            reason="temporal_peak",
            context={"confidence": 0.85},
        )
        assert isinstance(result, ExplanationResult)
        assert result.reason == "temporal_peak"
        assert result.template_version == "v2"
        assert "85%" in result.text
        assert result.confidence == 0.85

    def test_v2_temporal_approaching(self):
        result = generate_explanation_v2(
            reason="temporal_approaching",
            context={"days_to_peak": 365},
        )
        assert "365" in result.text

    def test_v2_expert_high_consensus(self):
        result = generate_explanation_v2(
            reason="expert_high_consensus",
            context={"n_experts": 5, "score": 92, "agreement": 0.95},
        )
        assert "5" in result.text
        assert "92" in result.text

    def test_unknown_reason_returns_empty_text(self):
        result = generate_explanation_v2(reason="nonexistent_reason")
        assert result.text == ""
        assert result.confidence == 0.0

    def test_v1_fallback(self):
        result = generate_explanation_v2(
            reason="temporal",
            template_version="v1",
        )
        assert result.template_version == "v1"
        assert "최적 음용 시기" in result.text

    def test_provenance_populated(self):
        ctx = {"confidence": 0.9, "days_to_peak": 180}
        result = generate_explanation_v2(reason="temporal_peak", context=ctx)
        assert result.provenance == ctx

    def test_missing_context_keys_returns_template(self):
        result = generate_explanation_v2(
            reason="expert_high_consensus",
            context={},
        )
        assert isinstance(result.text, str)

    def test_confidence_from_context(self):
        result = generate_explanation_v2(
            reason="temporal_peak",
            context={"confidence": 0.72},
        )
        assert result.confidence == 0.72

    def test_default_confidence_when_missing(self):
        result = generate_explanation_v2(
            reason="expert_match",
            context={},
        )
        assert result.confidence == 1.0

    def test_non_numeric_confidence_defaults_to_one(self):
        result = generate_explanation_v2(
            reason="temporal_peak",
            context={"confidence": "invalid"},
        )
        assert result.confidence == 1.0
