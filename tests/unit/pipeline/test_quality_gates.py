"""Tests for quality gates."""

from wine_rec.pipeline.quality_gates import (
    check_join_success_gate,
    check_leakage_gate,
    check_propensity_full,
    check_propensity_gate,
    check_propensity_warning,
)


class TestLeakageGate:
    def test_zero_violations_passes(self):
        result = check_leakage_gate(violation_rate=0.0)
        assert result.passed is True

    def test_any_violation_fails(self):
        result = check_leakage_gate(violation_rate=0.001)
        assert result.passed is False


class TestJoinSuccessGate:
    def test_above_threshold_passes(self):
        result = check_join_success_gate(success_rate=0.995)
        assert result.passed is True

    def test_below_threshold_fails(self):
        result = check_join_success_gate(success_rate=0.98)
        assert result.passed is False


class TestPropensityGate:
    def test_low_missing_passes(self):
        result = check_propensity_gate(missing_rate=0.03)
        assert result.passed is True

    def test_high_missing_blocks(self):
        result = check_propensity_gate(missing_rate=0.25)
        assert result.passed is False


class TestPropensityWarning:
    def test_low_missing_passes(self):
        result = check_propensity_warning(missing_rate=0.03)
        assert result.passed is True

    def test_above_5pct_warns(self):
        result = check_propensity_warning(missing_rate=0.08)
        assert result.passed is False

    def test_at_threshold_passes(self):
        result = check_propensity_warning(missing_rate=0.05)
        assert result.passed is True


class TestPropensityFull:
    def test_low_rate_both_pass(self):
        result = check_propensity_full(missing_rate=0.02)
        assert result.should_proceed is True
        assert result.warning.passed is True
        assert result.blocking.passed is True

    def test_warn_tier_only(self):
        result = check_propensity_full(missing_rate=0.10)
        assert result.should_proceed is True
        assert result.warning.passed is False
        assert result.blocking.passed is True

    def test_block_tier(self):
        result = check_propensity_full(missing_rate=0.25)
        assert result.should_proceed is False
        assert result.warning.passed is False
        assert result.blocking.passed is False
