"""Exploration-aware recall policies (RFC-SOTA-ROADMAP-012 §4-3).

Provides epsilon-greedy, UCB1, and Thompson sampling for multi-recall
source selection.  All decisions are logged for offline policy evaluation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import StrEnum

from wine_rec.common.logging import get_logger


log = get_logger(__name__)


class ExplorationPolicy(StrEnum):
    """Available exploration policies."""

    GREEDY = "greedy"
    EPSILON_GREEDY = "epsilon_greedy"
    UCB = "ucb"
    THOMPSON = "thompson"


@dataclass(frozen=True)
class ExplorationDecision:
    """Logged decision from exploration policy."""

    policy: ExplorationPolicy
    selected_source: str
    was_exploration: bool
    exploration_probability: float
    source_scores: dict[str, float]


@dataclass(frozen=True)
class SourceStats:
    """Running statistics for a recall source (for UCB/Thompson)."""

    source_name: str
    n_pulls: int
    total_reward: float
    reward_sq_sum: float

    @property
    def mean_reward(self) -> float:
        if self.n_pulls == 0:
            return 0.0
        return self.total_reward / self.n_pulls

    @property
    def variance(self) -> float:
        if self.n_pulls < 2:
            return 1.0
        return max(
            (self.reward_sq_sum / self.n_pulls) - self.mean_reward**2,
            1e-6,
        )


def epsilon_greedy_select(
    *,
    source_stats: dict[str, SourceStats],
    epsilon: float = 0.1,
    seed: int | None = None,
) -> ExplorationDecision:
    """Epsilon-greedy source selection.

    With probability epsilon, selects a random source (exploration).
    Otherwise selects the source with highest mean reward (exploitation).
    """
    if not source_stats:
        msg = "At least one source is required"
        raise ValueError(msg)

    rng = random.Random(seed)  # noqa: S311

    sources = list(source_stats.keys())
    scores = {name: stats.mean_reward for name, stats in source_stats.items()}

    if rng.random() < epsilon:
        selected = rng.choice(sources)
        was_exploration = True
    else:
        selected = max(sources, key=lambda s: scores[s])
        was_exploration = False

    return ExplorationDecision(
        policy=ExplorationPolicy.EPSILON_GREEDY,
        selected_source=selected,
        was_exploration=was_exploration,
        exploration_probability=epsilon,
        source_scores=scores,
    )


def ucb_select(
    *,
    source_stats: dict[str, SourceStats],
    total_rounds: int,
    exploration_constant: float = 2.0,
) -> ExplorationDecision:
    """UCB1-based source selection for multi-recall.

    Selects source maximizing: mean_reward + c * sqrt(ln(total) / n_pulls).
    Sources with 0 pulls are selected first.
    """
    if not source_stats:
        msg = "At least one source is required"
        raise ValueError(msg)

    scores: dict[str, float] = {}
    ln_total = math.log(max(total_rounds, 1))

    for name, stats in source_stats.items():
        if stats.n_pulls == 0:
            scores[name] = float("inf")
        else:
            exploration_term = exploration_constant * math.sqrt(ln_total / stats.n_pulls)
            scores[name] = stats.mean_reward + exploration_term

    selected = max(scores, key=lambda s: scores[s])
    was_exploration = source_stats[selected].n_pulls == 0

    return ExplorationDecision(
        policy=ExplorationPolicy.UCB,
        selected_source=selected,
        was_exploration=was_exploration,
        exploration_probability=0.0,
        source_scores=scores,
    )


def thompson_select(
    *,
    source_stats: dict[str, SourceStats],
    seed: int | None = None,
) -> ExplorationDecision:
    """Thompson sampling for cold-start users (Gaussian posterior).

    Samples from a Gaussian posterior for each source and selects the
    highest sample.  Higher variance (less data) → more exploration.
    """
    if not source_stats:
        msg = "At least one source is required"
        raise ValueError(msg)

    rng = random.Random(seed)  # noqa: S311
    scores: dict[str, float] = {}

    for name, stats in source_stats.items():
        mean = stats.mean_reward
        std = math.sqrt(stats.variance / max(stats.n_pulls, 1))
        scores[name] = rng.gauss(mean, std)

    selected = max(scores, key=lambda s: scores[s])
    best_mean = max(source_stats.values(), key=lambda s: s.mean_reward)
    was_exploration = selected != best_mean.source_name

    return ExplorationDecision(
        policy=ExplorationPolicy.THOMPSON,
        selected_source=selected,
        was_exploration=was_exploration,
        exploration_probability=0.0,
        source_scores=scores,
    )
