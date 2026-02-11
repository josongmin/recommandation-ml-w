"""Tests for challenge tracks and leaderboard (C1-C3)."""

from __future__ import annotations

import numpy as np

from tests.conftest import InMemoryObjectStore
from wine_rec.models.evaluation.challenge import (
    CHALLENGE_SPECS,
    ChallengeTrack,
    Leaderboard,
    LeaderboardEntry,
    evaluate_challenge_track,
    filter_challenge_samples,
    get_leaderboard,
    run_challenge_suite,
    update_leaderboard,
)
from wine_rec.models.evaluation.evaluator import EvalSample


def _make_samples() -> list[EvalSample]:
    return [
        EvalSample(
            user_id="u1",
            y_true=np.array([1, 0, 1, 0, 0]),
            y_pred=np.array([0.9, 0.2, 0.7, 0.1, 0.3]),
            item_ids=["s1", "s2", "s3", "s4", "s5"],
            metadata={"is_high_end": True, "has_expert_consensus": True},
        ),
        EvalSample(
            user_id="u2",
            y_true=np.array([0, 1, 0]),
            y_pred=np.array([0.3, 0.8, 0.1]),
            item_ids=["s1", "s6", "s7"],
            metadata={"is_high_end": False, "has_expert_consensus": False},
        ),
        EvalSample(
            user_id="u3",
            y_true=np.array([1, 0]),
            y_pred=np.array([0.6, 0.4]),
            item_ids=["s8", "s9"],
            metadata={"is_high_end": True, "has_expert_consensus": True},
        ),
    ]


class TestChallengeSpecs:
    def test_all_tracks_have_specs(self):
        for track in ChallengeTrack:
            assert track in CHALLENGE_SPECS

    def test_high_end_spec(self):
        spec = CHALLENGE_SPECS[ChallengeTrack.HIGH_END]
        assert spec.primary_metric == "ndcg@10"
        assert "ips" in spec.secondary_metrics

    def test_cold_start_spec(self):
        spec = CHALLENGE_SPECS[ChallengeTrack.COLD_START]
        assert spec.primary_metric == "recall@10"

    def test_expert_aware_spec(self):
        spec = CHALLENGE_SPECS[ChallengeTrack.EXPERT_AWARE]
        assert "expert_agreement_pct" in spec.required_metadata_fields


class TestFilterChallengeSamples:
    def test_filter_high_end(self):
        samples = _make_samples()
        filtered = filter_challenge_samples(samples, ChallengeTrack.HIGH_END)
        assert len(filtered) == 2  # u1, u3
        assert all(s.metadata.get("is_high_end") for s in filtered)

    def test_filter_cold_start(self):
        samples = _make_samples()
        filtered = filter_challenge_samples(samples, ChallengeTrack.COLD_START)
        # u2 has 3 items, u3 has 2 items → both < 5
        assert len(filtered) == 2

    def test_filter_expert_aware(self):
        samples = _make_samples()
        filtered = filter_challenge_samples(samples, ChallengeTrack.EXPERT_AWARE)
        assert len(filtered) == 2  # u1, u3
        assert all(s.metadata.get("has_expert_consensus") for s in filtered)

    def test_filter_returns_empty_when_no_match(self):
        samples = [
            EvalSample(
                user_id="u1",
                y_true=np.array([1]),
                y_pred=np.array([0.5]),
                metadata={"is_high_end": False, "has_expert_consensus": False},
            ),
        ]
        filtered = filter_challenge_samples(samples, ChallengeTrack.HIGH_END)
        assert len(filtered) == 0


class TestEvaluateChallengeTrack:
    def test_returns_leaderboard_entry(self):
        samples = _make_samples()
        entry = evaluate_challenge_track(
            samples,
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert isinstance(entry, LeaderboardEntry)
        assert entry.track == ChallengeTrack.HIGH_END
        assert entry.model_name == "bpr"

    def test_primary_score_set(self):
        samples = _make_samples()
        entry = evaluate_challenge_track(
            samples,
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert entry.primary_score >= 0.0

    def test_empty_track_returns_zero_score(self):
        samples = [
            EvalSample(
                user_id="u1",
                y_true=np.array([1]),
                y_pred=np.array([0.5]),
                metadata={},  # no flags → empty for all tracks
            ),
        ]
        entry = evaluate_challenge_track(
            samples,
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert entry.primary_score == 0.0

    def test_all_metrics_populated(self):
        samples = _make_samples()
        entry = evaluate_challenge_track(
            samples,
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert "ndcg@10" in entry.all_metrics
        assert "n_users" in entry.all_metrics

    def test_submitted_at_set(self):
        samples = _make_samples()
        entry = evaluate_challenge_track(
            samples,
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert entry.submitted_at != ""


class TestRunChallengeSuite:
    def test_returns_three_entries(self):
        samples = _make_samples()
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

    def test_all_entries_have_model_info(self):
        samples = _make_samples()
        entries = run_challenge_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        for entry in entries:
            assert entry.model_name == "bpr"
            assert entry.model_version == "v1"


class TestLeaderboard:
    def test_empty_leaderboard(self):
        store = InMemoryObjectStore()
        lb = get_leaderboard(
            object_store=store,
            track=ChallengeTrack.HIGH_END,
        )
        assert isinstance(lb, Leaderboard)
        assert len(lb.entries) == 0

    def test_update_creates_leaderboard(self):
        store = InMemoryObjectStore()
        entry = LeaderboardEntry(
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            primary_score=0.85,
            submitted_at="2026-01-15T00:00:00Z",
        )
        lb = update_leaderboard(object_store=store, entry=entry)
        assert len(lb.entries) == 1
        assert lb.entries[0].primary_score == 0.85

    def test_leaderboard_sorted_descending(self):
        store = InMemoryObjectStore()
        e1 = LeaderboardEntry(
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            primary_score=0.75,
            submitted_at="2026-01-15T00:00:00Z",
        )
        e2 = LeaderboardEntry(
            track=ChallengeTrack.HIGH_END,
            model_name="two_tower",
            model_version="v1",
            dataset_version="ds_v1",
            primary_score=0.90,
            submitted_at="2026-01-16T00:00:00Z",
        )
        update_leaderboard(object_store=store, entry=e1)
        lb = update_leaderboard(object_store=store, entry=e2)
        assert len(lb.entries) == 2
        assert lb.entries[0].primary_score == 0.90
        assert lb.entries[1].primary_score == 0.75

    def test_roundtrip_persistence(self):
        store = InMemoryObjectStore()
        entry = LeaderboardEntry(
            track=ChallengeTrack.COLD_START,
            model_name="lightgcn",
            model_version="v2",
            dataset_version="ds_v1",
            primary_score=0.65,
            all_metrics={"recall@10": 0.65, "ndcg@10": 0.42},
            submitted_at="2026-01-15T00:00:00Z",
        )
        update_leaderboard(object_store=store, entry=entry)
        lb = get_leaderboard(
            object_store=store,
            track=ChallengeTrack.COLD_START,
        )
        assert len(lb.entries) == 1
        assert lb.entries[0].model_name == "lightgcn"
        assert lb.entries[0].all_metrics["recall@10"] == 0.65

    def test_different_tracks_independent(self):
        store = InMemoryObjectStore()
        e1 = LeaderboardEntry(
            track=ChallengeTrack.HIGH_END,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            primary_score=0.80,
        )
        e2 = LeaderboardEntry(
            track=ChallengeTrack.COLD_START,
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            primary_score=0.60,
        )
        update_leaderboard(object_store=store, entry=e1)
        update_leaderboard(object_store=store, entry=e2)

        lb_he = get_leaderboard(object_store=store, track=ChallengeTrack.HIGH_END)
        lb_cs = get_leaderboard(object_store=store, track=ChallengeTrack.COLD_START)
        assert len(lb_he.entries) == 1
        assert len(lb_cs.entries) == 1
        assert lb_he.entries[0].primary_score == 0.80
        assert lb_cs.entries[0].primary_score == 0.60
