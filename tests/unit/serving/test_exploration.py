"""Tests for exploration-aware recall policies."""

from __future__ import annotations

import pytest

from wine_rec.serving.exploration import (
    ExplorationDecision,
    ExplorationPolicy,
    SourceStats,
    epsilon_greedy_select,
    thompson_select,
    ucb_select,
)


def _make_stats() -> dict[str, SourceStats]:
    return {
        "collaborative": SourceStats(
            source_name="collaborative", n_pulls=100, total_reward=80.0, reward_sq_sum=70.0
        ),
        "content": SourceStats(
            source_name="content", n_pulls=50, total_reward=30.0, reward_sq_sum=20.0
        ),
        "popular": SourceStats(
            source_name="popular", n_pulls=200, total_reward=120.0, reward_sq_sum=80.0
        ),
    }


class TestSourceStats:
    def test_mean_reward(self):
        stats = SourceStats(source_name="test", n_pulls=10, total_reward=8.0, reward_sq_sum=7.0)
        assert stats.mean_reward == 0.8

    def test_mean_reward_zero_pulls(self):
        stats = SourceStats(source_name="test", n_pulls=0, total_reward=0.0, reward_sq_sum=0.0)
        assert stats.mean_reward == 0.0

    def test_variance_insufficient_pulls(self):
        stats = SourceStats(source_name="test", n_pulls=1, total_reward=1.0, reward_sq_sum=1.0)
        assert stats.variance == 1.0

    def test_variance_with_data(self):
        stats = SourceStats(source_name="test", n_pulls=10, total_reward=5.0, reward_sq_sum=3.5)
        # variance = (3.5/10) - (0.5)^2 = 0.35 - 0.25 = 0.10
        assert abs(stats.variance - 0.10) < 0.01


class TestEpsilonGreedySelect:
    def test_exploit_selects_best(self):
        """With epsilon=0, always selects the highest mean reward."""
        stats = _make_stats()
        decision = epsilon_greedy_select(source_stats=stats, epsilon=0.0, seed=42)
        assert isinstance(decision, ExplorationDecision)
        assert decision.policy == ExplorationPolicy.EPSILON_GREEDY
        # collaborative: 80/100=0.8, content: 30/50=0.6, popular: 120/200=0.6
        assert decision.selected_source == "collaborative"
        assert decision.was_exploration is False

    def test_explore_with_epsilon_1(self):
        """With epsilon=1, always explores (random selection)."""
        stats = _make_stats()
        decision = epsilon_greedy_select(source_stats=stats, epsilon=1.0, seed=42)
        assert decision.was_exploration is True
        assert decision.selected_source in stats

    def test_exploration_probability_recorded(self):
        stats = _make_stats()
        decision = epsilon_greedy_select(source_stats=stats, epsilon=0.15, seed=0)
        assert decision.exploration_probability == 0.15

    def test_source_scores_populated(self):
        stats = _make_stats()
        decision = epsilon_greedy_select(source_stats=stats, epsilon=0.0, seed=42)
        assert len(decision.source_scores) == 3
        assert "collaborative" in decision.source_scores

    def test_single_source(self):
        stats = {
            "only": SourceStats(source_name="only", n_pulls=10, total_reward=5.0, reward_sq_sum=3.0)
        }
        decision = epsilon_greedy_select(source_stats=stats, epsilon=0.0)
        assert decision.selected_source == "only"

    def test_empty_stats_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            epsilon_greedy_select(source_stats={}, epsilon=0.1)

    def test_deterministic_with_seed(self):
        stats = _make_stats()
        d1 = epsilon_greedy_select(source_stats=stats, epsilon=0.5, seed=123)
        d2 = epsilon_greedy_select(source_stats=stats, epsilon=0.5, seed=123)
        assert d1.selected_source == d2.selected_source


class TestUCBSelect:
    def test_unpulled_source_selected_first(self):
        stats = {
            "a": SourceStats(source_name="a", n_pulls=100, total_reward=80.0, reward_sq_sum=70.0),
            "b": SourceStats(source_name="b", n_pulls=0, total_reward=0.0, reward_sq_sum=0.0),
        }
        decision = ucb_select(source_stats=stats, total_rounds=100)
        assert decision.selected_source == "b"
        assert decision.was_exploration is True

    def test_ucb_score_includes_exploration_term(self):
        stats = _make_stats()
        decision = ucb_select(source_stats=stats, total_rounds=350)
        assert decision.policy == ExplorationPolicy.UCB
        # All sources have been pulled, so scores should all be finite
        for score in decision.source_scores.values():
            assert score != float("inf")

    def test_single_source(self):
        stats = {
            "only": SourceStats(
                source_name="only", n_pulls=50, total_reward=25.0, reward_sq_sum=15.0
            )
        }
        decision = ucb_select(source_stats=stats, total_rounds=50)
        assert decision.selected_source == "only"

    def test_empty_stats_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            ucb_select(source_stats={}, total_rounds=100)


class TestThompsonSelect:
    def test_basic_selection(self):
        stats = _make_stats()
        decision = thompson_select(source_stats=stats, seed=42)
        assert isinstance(decision, ExplorationDecision)
        assert decision.policy == ExplorationPolicy.THOMPSON
        assert decision.selected_source in stats

    def test_deterministic_with_seed(self):
        stats = _make_stats()
        d1 = thompson_select(source_stats=stats, seed=42)
        d2 = thompson_select(source_stats=stats, seed=42)
        assert d1.selected_source == d2.selected_source

    def test_empty_stats_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            thompson_select(source_stats={}, seed=42)

    def test_cold_start_source_has_high_variance(self):
        """Sources with few pulls should have more variance → more exploration."""
        stats = {
            "established": SourceStats(
                source_name="established", n_pulls=1000, total_reward=600.0, reward_sq_sum=400.0
            ),
            "new": SourceStats(source_name="new", n_pulls=2, total_reward=1.5, reward_sq_sum=1.2),
        }
        # With many runs, the "new" source should sometimes be picked
        selections = set()
        for seed in range(50):
            d = thompson_select(source_stats=stats, seed=seed)
            selections.add(d.selected_source)
        assert "new" in selections
