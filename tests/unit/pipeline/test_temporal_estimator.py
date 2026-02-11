"""Tests for temporal estimator (RFC-SOTA-ROADMAP-012 R3)."""

from __future__ import annotations

import pytest

from wine_rec.pipeline.temporal_estimator import (
    TemporalEstimate,
    compute_current_stage,
    compute_peak_trajectory,
    estimate_expert_based,
    estimate_model_based,
    estimate_rule_based,
    merge_estimates,
)


class TestEstimateRuleBased:
    def test_red_wine_window(self):
        est = estimate_rule_based(wine_type="red", vintage_year=2015, reference_year=2026)
        assert est.drink_from_year == 2018  # 2015 + 3
        assert est.drink_to_year == 2027  # 2015 + 12
        assert est.method == "rule"

    def test_white_wine_window(self):
        est = estimate_rule_based(wine_type="white", vintage_year=2023, reference_year=2026)
        assert est.drink_from_year == 2024  # 2023 + 1
        assert est.drink_to_year == 2028  # 2023 + 5

    def test_fortified_wine_window(self):
        est = estimate_rule_based(wine_type="fortified", vintage_year=2000, reference_year=2026)
        assert est.drink_from_year == 2005  # 2000 + 5
        assert est.drink_to_year == 2030  # 2000 + 30

    def test_unknown_type_uses_default(self):
        est = estimate_rule_based(wine_type="unknown_type", vintage_year=2020, reference_year=2026)
        assert est.drink_from_year == 2022  # 2020 + 2
        assert est.drink_to_year == 2028  # 2020 + 8

    def test_too_young_confidence(self):
        """Before drink window → confidence 0.7."""
        est = estimate_rule_based(wine_type="red", vintage_year=2024, reference_year=2026)
        # drink_from = 2027, reference 2026 < 2027 → too_young
        assert est.confidence == 0.7

    def test_peak_confidence(self):
        """After midpoint in window → confidence 0.8."""
        est = estimate_rule_based(wine_type="red", vintage_year=2015, reference_year=2026)
        # drink_from=2018, drink_to=2027, mid=2022.5, 2026 >= mid → 0.8
        assert est.confidence == 0.8

    def test_early_confidence(self):
        """Before midpoint in window → confidence 0.6."""
        est = estimate_rule_based(wine_type="fortified", vintage_year=2020, reference_year=2026)
        # drink_from=2025, drink_to=2050, mid=2037.5, 2026 < mid → 0.6
        assert est.confidence == 0.6

    def test_past_confidence(self):
        """After drink window → confidence 0.5."""
        est = estimate_rule_based(wine_type="rosé", vintage_year=2018, reference_year=2026)
        # drink_from=2019, drink_to=2021, 2026 > 2021 → past
        assert est.confidence == 0.5


class TestEstimateModelBased:
    def test_heuristic_estimation(self):
        """Test model-based uses heuristic until ML model trained."""
        result = estimate_model_based(
            wine_type="red",
            variety="Pinot Noir",
            region="Burgundy",
            vintage_year=2015,
            review_signals={"avg_score": 92.0, "n_reviews": 100, "score_variance": 3.0},
            reference_year=2026,
        )
        assert result is not None
        assert result.method == "model"
        assert result.confidence > 0.7  # High score + many reviews
        assert result.drink_from_year < result.drink_to_year

    def test_low_quality_wine_shorter_window(self):
        """Test low-scored wines get shorter drinking windows."""
        result = estimate_model_based(
            wine_type="red",
            variety="Merlot",
            region="Unknown",
            vintage_year=2020,
            review_signals={"avg_score": 78.0, "n_reviews": 10},
            reference_year=2026,
        )
        assert result is not None
        assert result.confidence < 0.7  # Lower confidence for low quality


class TestEstimateExpertBased:
    def test_with_valid_data(self):
        est = estimate_expert_based(expert_drink_from=2020, expert_drink_to=2030)
        assert est is not None
        assert est.drink_from_year == 2020
        assert est.drink_to_year == 2030
        assert est.confidence == 0.9
        assert est.method == "expert"

    def test_none_from_missing(self):
        assert estimate_expert_based(expert_drink_from=None, expert_drink_to=2030) is None
        assert estimate_expert_based(expert_drink_from=2020, expert_drink_to=None) is None
        assert estimate_expert_based(expert_drink_from=None, expert_drink_to=None) is None

    def test_none_from_invalid_range(self):
        assert estimate_expert_based(expert_drink_from=2030, expert_drink_to=2020) is None


class TestMergeEstimates:
    def test_single_estimate_returned_as_is(self):
        est = TemporalEstimate(
            drink_from_year=2020, drink_to_year=2030, confidence=0.8, method="rule"
        )
        result = merge_estimates([est])
        assert result is est

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            merge_estimates([])

    def test_expert_high_confidence_preferred(self):
        rule = TemporalEstimate(
            drink_from_year=2020, drink_to_year=2028, confidence=0.7, method="rule"
        )
        expert = TemporalEstimate(
            drink_from_year=2022, drink_to_year=2032, confidence=0.9, method="expert"
        )
        result = merge_estimates([rule, expert])
        assert result.drink_from_year == 2022
        assert result.drink_to_year == 2032
        assert result.method == "ensemble"

    def test_weighted_average_without_expert(self):
        r1 = TemporalEstimate(
            drink_from_year=2020, drink_to_year=2030, confidence=0.8, method="rule"
        )
        r2 = TemporalEstimate(
            drink_from_year=2022, drink_to_year=2032, confidence=0.6, method="rule"
        )
        result = merge_estimates([r1, r2])
        assert result.method == "ensemble"
        # weighted avg: from = (2020*0.8 + 2022*0.6) / 1.4 ≈ 2020.86 → 2021
        assert result.drink_from_year == 2021

    def test_expert_low_confidence_not_preferred(self):
        """Expert with confidence <= 0.8 should not be auto-preferred."""
        rule = TemporalEstimate(
            drink_from_year=2020, drink_to_year=2028, confidence=0.8, method="rule"
        )
        expert = TemporalEstimate(
            drink_from_year=2022, drink_to_year=2032, confidence=0.7, method="expert"
        )
        result = merge_estimates([rule, expert])
        # Should be weighted average, not expert preferred
        assert result.method == "ensemble"
        assert result.confidence == 0.8  # max of 0.8, 0.7


class TestComputeCurrentStage:
    def test_too_young(self):
        assert (
            compute_current_stage(drink_from_year=2028, drink_to_year=2035, reference_year=2026)
            == "too_young"
        )

    def test_early(self):
        assert (
            compute_current_stage(drink_from_year=2025, drink_to_year=2035, reference_year=2026)
            == "early"
        )

    def test_peak(self):
        assert (
            compute_current_stage(drink_from_year=2020, drink_to_year=2028, reference_year=2026)
            == "peak"
        )

    def test_past(self):
        assert (
            compute_current_stage(drink_from_year=2018, drink_to_year=2022, reference_year=2026)
            == "past"
        )


class TestComputePeakTrajectory:
    def test_approaching_before_window(self):
        traj, days = compute_peak_trajectory(
            drink_from_year=2028, drink_to_year=2035, reference_year=2026
        )
        assert traj == "approaching"
        assert days is not None
        assert days > 0

    def test_at_peak_near_midpoint(self):
        traj, days = compute_peak_trajectory(
            drink_from_year=2024, drink_to_year=2028, reference_year=2026
        )
        # mid = 2026, ref = 2026, diff = 0 → at_peak
        assert traj == "at_peak"
        assert days is not None

    def test_declining_past_window(self):
        traj, days = compute_peak_trajectory(
            drink_from_year=2018, drink_to_year=2022, reference_year=2026
        )
        assert traj == "declining"
        assert days is not None
        assert days < 0
