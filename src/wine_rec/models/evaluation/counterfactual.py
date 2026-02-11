"""Counterfactual evaluation — IPS / SNIPS / DR (RFC-DATASET-BENCH-005 §5-4).

모든 벤치 리포트에 필수 포함 (Non-Negotiable).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np


if TYPE_CHECKING:
    from numpy.typing import NDArray


def ips_estimate(
    *,
    rewards: NDArray[np.float64],
    propensities: NDArray[np.float64],
    new_policy_probs: NDArray[np.float64],
) -> float:
    """Inverse Propensity Scoring (IPS) estimator."""
    weights = new_policy_probs / np.clip(propensities, 1e-6, None)
    return float(np.mean(weights * rewards))


def snips_estimate(
    *,
    rewards: NDArray[np.float64],
    propensities: NDArray[np.float64],
    new_policy_probs: NDArray[np.float64],
) -> float:
    """Self-Normalized IPS (SNIPS) — lower variance than IPS."""
    weights = new_policy_probs / np.clip(propensities, 1e-6, None)
    return float(np.sum(weights * rewards) / np.sum(weights))


def doubly_robust_estimate(
    *,
    rewards: NDArray[np.float64],
    propensities: NDArray[np.float64],
    new_policy_probs: NDArray[np.float64],
    reward_model_preds: NDArray[np.float64],
) -> float:
    """Doubly Robust (DR) estimator — combines IPS with reward model."""
    weights = new_policy_probs / np.clip(propensities, 1e-6, None)
    correction = weights * (rewards - reward_model_preds)
    return float(np.mean(reward_model_preds + correction))
