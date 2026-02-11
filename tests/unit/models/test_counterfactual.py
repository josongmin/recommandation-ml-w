"""Tests for counterfactual evaluation."""

import numpy as np

from wine_rec.models.evaluation.counterfactual import (
    doubly_robust_estimate,
    ips_estimate,
    snips_estimate,
)


class TestIPS:
    def test_uniform_policy(self):
        rewards = np.array([1.0, 0.0, 1.0, 0.0])
        propensities = np.array([0.5, 0.5, 0.5, 0.5])
        new_probs = np.array([0.5, 0.5, 0.5, 0.5])
        result = ips_estimate(
            rewards=rewards, propensities=propensities, new_policy_probs=new_probs
        )
        assert result == 0.5


class TestSNIPS:
    def test_normalized(self):
        rewards = np.array([1.0, 0.0])
        propensities = np.array([0.5, 0.5])
        new_probs = np.array([0.5, 0.5])
        result = snips_estimate(
            rewards=rewards, propensities=propensities, new_policy_probs=new_probs
        )
        assert result == 0.5


class TestDoublyRobust:
    def test_perfect_model(self):
        rewards = np.array([1.0, 0.0])
        propensities = np.array([0.5, 0.5])
        new_probs = np.array([0.5, 0.5])
        model_preds = np.array([1.0, 0.0])
        result = doubly_robust_estimate(
            rewards=rewards,
            propensities=propensities,
            new_policy_probs=new_probs,
            reward_model_preds=model_preds,
        )
        assert result == 0.5
