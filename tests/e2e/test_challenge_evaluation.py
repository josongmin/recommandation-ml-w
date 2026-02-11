"""E2E: Samples → challenge suite → leaderboard entries (C1-C3)."""

from __future__ import annotations

import numpy as np
import pytest

from tests.conftest import InMemoryObjectStore
from wine_rec.models.evaluation.challenge import (
    ChallengeTrack,
    get_leaderboard,
    run_challenge_suite,
    update_leaderboard,
)
from wine_rec.models.evaluation.evaluator import EvalSample


def _make_diverse_samples() -> list[EvalSample]:
    """Samples spanning all challenge track filters."""
    return [
        # u1: high-end + expert
        EvalSample(
            user_id="u1",
            y_true=np.array([1, 0, 1, 0, 0, 1, 0]),
            y_pred=np.array([0.9, 0.2, 0.8, 0.1, 0.3, 0.7, 0.15]),
            item_ids=["w1", "w2", "w3", "w4", "w5", "w6", "w7"],
            metadata={"is_high_end": True, "has_expert_consensus": True},
        ),
        # u2: cold-start (3 items)
        EvalSample(
            user_id="u2",
            y_true=np.array([0, 1, 0]),
            y_pred=np.array([0.3, 0.85, 0.1]),
            item_ids=["w1", "w8", "w9"],
            metadata={"is_high_end": False, "has_expert_consensus": False},
        ),
        # u3: high-end + expert + cold-start (2 items)
        EvalSample(
            user_id="u3",
            y_true=np.array([1, 0]),
            y_pred=np.array([0.6, 0.4]),
            item_ids=["w10", "w11"],
            metadata={"is_high_end": True, "has_expert_consensus": True},
        ),
        # u4: expert, not high-end, not cold-start
        EvalSample(
            user_id="u4",
            y_true=np.array([1, 0, 0, 1, 0, 1]),
            y_pred=np.array([0.7, 0.3, 0.2, 0.6, 0.1, 0.8]),
            item_ids=["w12", "w13", "w14", "w15", "w16", "w17"],
            metadata={"is_high_end": False, "has_expert_consensus": True},
        ),
    ]


@pytest.mark.e2e
class TestChallengeEvaluation:
    """Test full challenge evaluation pipeline."""

    def test_challenge_suite_produces_all_tracks(self):
        samples = _make_diverse_samples()
        entries = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        assert len(entries) == 3
        tracks = {e.track for e in entries}
        assert tracks == {
            ChallengeTrack.HIGH_END,
            ChallengeTrack.COLD_START,
            ChallengeTrack.EXPERT_AWARE,
        }

    def test_high_end_track_uses_correct_samples(self):
        samples = _make_diverse_samples()
        entries = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        he = next(e for e in entries if e.track == ChallengeTrack.HIGH_END)
        assert he.all_metrics["n_users"] == 2.0  # u1, u3

    def test_cold_start_track_filters_correctly(self):
        samples = _make_diverse_samples()
        entries = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        cs = next(e for e in entries if e.track == ChallengeTrack.COLD_START)
        # u2 (3 items) + u3 (2 items) → cold-start
        assert cs.all_metrics["n_users"] == 2.0

    def test_expert_aware_track_filters_correctly(self):
        samples = _make_diverse_samples()
        entries = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        ea = next(e for e in entries if e.track == ChallengeTrack.EXPERT_AWARE)
        # u1, u3, u4 have expert consensus
        assert ea.all_metrics["n_users"] == 3.0

    def test_leaderboard_end_to_end(self):
        """Run suite → update leaderboard → verify persistence."""
        samples = _make_diverse_samples()
        store = InMemoryObjectStore()

        # Model 1
        entries_v1 = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        for entry in entries_v1:
            update_leaderboard(object_store=store, entry=entry)

        # Model 2
        entries_v2 = run_challenge_suite(
            model_name="two_tower",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        for entry in entries_v2:
            update_leaderboard(object_store=store, entry=entry)

        # Verify each track has 2 entries, sorted by primary_score descending
        for track in ChallengeTrack:
            lb = get_leaderboard(object_store=store, track=track)
            assert len(lb.entries) == 2
            assert lb.entries[0].primary_score >= lb.entries[1].primary_score

    def test_all_tracks_have_counterfactual_metrics(self):
        """Every challenge track result should include IPS/SNIPS/DR."""
        samples = _make_diverse_samples()
        entries = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        for entry in entries:
            if entry.all_metrics.get("n_users", 0) > 0:
                assert "ips" in entry.all_metrics, f"Missing IPS in {entry.track}"
                assert "snips" in entry.all_metrics, f"Missing SNIPS in {entry.track}"
                assert "dr" in entry.all_metrics, f"Missing DR in {entry.track}"
