"""Tests for expert-aware evaluation metrics."""

from __future__ import annotations

from wine_rec.models.evaluation.expert_metrics import (
    expert_agreement_correlation,
    expert_coverage_at_k,
)


class TestExpertAgreementCorrelation:
    def test_perfect_agreement(self):
        """Model ranking matches expert consensus perfectly."""
        result = expert_agreement_correlation(
            predicted_rankings=["w1", "w2", "w3"],
            expert_consensus_scores={"w1": 0.95, "w2": 0.80, "w3": 0.60},
        )
        assert result == 1.0

    def test_inverse_agreement(self):
        """Model ranking is completely reversed from expert consensus."""
        result = expert_agreement_correlation(
            predicted_rankings=["w3", "w2", "w1"],
            expert_consensus_scores={"w1": 0.95, "w2": 0.80, "w3": 0.60},
        )
        assert result == -1.0

    def test_partial_overlap(self):
        """Only some predicted items have expert scores."""
        result = expert_agreement_correlation(
            predicted_rankings=["w1", "w2", "w3", "w4"],
            expert_consensus_scores={"w1": 0.9, "w3": 0.7},
        )
        assert -1.0 <= result <= 1.0

    def test_single_item_returns_zero(self):
        result = expert_agreement_correlation(
            predicted_rankings=["w1"],
            expert_consensus_scores={"w1": 0.9},
        )
        assert result == 0.0

    def test_no_overlap_returns_zero(self):
        result = expert_agreement_correlation(
            predicted_rankings=["w1", "w2"],
            expert_consensus_scores={"w3": 0.9, "w4": 0.8},
        )
        assert result == 0.0

    def test_empty_rankings_returns_zero(self):
        result = expert_agreement_correlation(
            predicted_rankings=[],
            expert_consensus_scores={"w1": 0.9},
        )
        assert result == 0.0

    def test_tied_expert_scores(self):
        """When expert scores are identical, correlation should handle gracefully."""
        result = expert_agreement_correlation(
            predicted_rankings=["w1", "w2", "w3"],
            expert_consensus_scores={"w1": 0.8, "w2": 0.8, "w3": 0.8},
        )
        assert -1.0 <= result <= 1.0


class TestExpertCoverageAtK:
    def test_full_coverage(self):
        result = expert_coverage_at_k(
            recommended_items=["w1", "w2", "w3"],
            expert_validated_items={"w1", "w2", "w3"},
            k=3,
        )
        assert result == 1.0

    def test_no_coverage(self):
        result = expert_coverage_at_k(
            recommended_items=["w1", "w2", "w3"],
            expert_validated_items={"w4", "w5"},
            k=3,
        )
        assert result == 0.0

    def test_partial_coverage(self):
        result = expert_coverage_at_k(
            recommended_items=["w1", "w2", "w3", "w4"],
            expert_validated_items={"w1", "w3"},
            k=4,
        )
        assert result == 0.5

    def test_k_less_than_list(self):
        result = expert_coverage_at_k(
            recommended_items=["w1", "w2", "w3", "w4"],
            expert_validated_items={"w1", "w2"},
            k=2,
        )
        assert result == 1.0

    def test_k_zero_returns_zero(self):
        result = expert_coverage_at_k(
            recommended_items=["w1"],
            expert_validated_items={"w1"},
            k=0,
        )
        assert result == 0.0

    def test_empty_recommendations_returns_zero(self):
        result = expert_coverage_at_k(
            recommended_items=[],
            expert_validated_items={"w1"},
            k=5,
        )
        assert result == 0.0
