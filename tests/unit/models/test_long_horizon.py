"""Tests for long-horizon winner judgment."""

from __future__ import annotations

from wine_rec.models.evaluation.long_horizon import (
    JudgmentAction,
    check_repurchase_decline,
    check_short_term_only,
    judge_winner,
)


class TestRepurchaseDecline:
    def test_7d_decline_blocks_deploy(self):
        j = check_repurchase_decline(period_label="7d", decline_rate=-0.06, threshold=-0.05)
        assert j.action == JudgmentAction.BLOCK_DEPLOY

    def test_7d_no_decline_passes(self):
        j = check_repurchase_decline(period_label="7d", decline_rate=-0.03, threshold=-0.05)
        assert j.action == JudgmentAction.PASS

    def test_30d_decline_blocks_deploy(self):
        j = check_repurchase_decline(period_label="30d", decline_rate=-0.04, threshold=-0.03)
        assert j.action == JudgmentAction.BLOCK_DEPLOY

    def test_exact_threshold_passes(self):
        """At exactly the threshold, should pass (not strictly less)."""
        j = check_repurchase_decline(period_label="7d", decline_rate=-0.05, threshold=-0.05)
        assert j.action == JudgmentAction.PASS

    def test_positive_rate_passes(self):
        j = check_repurchase_decline(period_label="7d", decline_rate=0.02, threshold=-0.05)
        assert j.action == JudgmentAction.PASS


class TestShortTermOnly:
    def test_ctr_up_repurchase_down_tags(self):
        j = check_short_term_only(ctr_delta=0.05, repurchase_delta=-0.02)
        assert j.action == JudgmentAction.TAG_SHORT_TERM_ONLY

    def test_both_up_passes(self):
        j = check_short_term_only(ctr_delta=0.05, repurchase_delta=0.01)
        assert j.action == JudgmentAction.PASS

    def test_ctr_down_repurchase_down_passes(self):
        j = check_short_term_only(ctr_delta=-0.02, repurchase_delta=-0.01)
        assert j.action == JudgmentAction.PASS

    def test_both_zero_passes(self):
        j = check_short_term_only(ctr_delta=0.0, repurchase_delta=0.0)
        assert j.action == JudgmentAction.PASS


class TestJudgeWinner:
    def test_all_good_is_winner(self):
        v = judge_winner(
            repurchase_7d_decline=0.0,
            repurchase_30d_decline=0.0,
            ctr_delta=0.05,
            repurchase_delta=0.02,
        )
        assert v.is_winner is True
        assert v.tags == ()

    def test_7d_decline_blocks(self):
        v = judge_winner(
            repurchase_7d_decline=-0.06,
            repurchase_30d_decline=0.0,
        )
        assert v.is_winner is False

    def test_30d_decline_blocks(self):
        v = judge_winner(
            repurchase_7d_decline=0.0,
            repurchase_30d_decline=-0.04,
        )
        assert v.is_winner is False

    def test_short_term_only_not_winner(self):
        v = judge_winner(
            repurchase_7d_decline=0.0,
            repurchase_30d_decline=0.0,
            ctr_delta=0.05,
            repurchase_delta=-0.01,
        )
        assert v.is_winner is False
        assert "short_term_only" in v.tags

    def test_multiple_failures(self):
        v = judge_winner(
            repurchase_7d_decline=-0.10,
            repurchase_30d_decline=-0.05,
            ctr_delta=0.05,
            repurchase_delta=-0.03,
        )
        assert v.is_winner is False
        assert len(v.judgments) == 3
