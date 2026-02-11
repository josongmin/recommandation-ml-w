"""Tests for recommendation explainer."""

from wine_rec.serving.explainer import generate_explanation


class TestGenerateExplanation:
    def test_temporal_explanation(self):
        result = generate_explanation(reason="temporal")
        assert "최적 음용 시기" in result

    def test_expert_explanation_with_context(self):
        result = generate_explanation(
            reason="expert",
            context={"score": 95, "consensus": 87},
        )
        assert "95" in result
        assert "87" in result

    def test_unknown_reason_returns_empty(self):
        result = generate_explanation(reason="nonexistent")
        assert result == ""

    def test_missing_context_keys_returns_template(self):
        result = generate_explanation(reason="expert", context={})
        # Should return template as-is when keys are missing
        assert isinstance(result, str)
