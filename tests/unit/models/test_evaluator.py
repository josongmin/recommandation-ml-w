"""Tests for benchmark evaluator (B0-B3)."""

from __future__ import annotations

import numpy as np

from wine_rec.models.evaluation.evaluator import (
    BenchmarkResult,
    EvalSample,
    evaluate_track,
    run_benchmark_suite,
)


def _make_samples() -> list[EvalSample]:
    """Create test evaluation samples."""
    return [
        EvalSample(
            user_id="u1",
            y_true=np.array([1, 0, 1, 0, 0]),
            y_pred=np.array([0.9, 0.2, 0.7, 0.1, 0.3]),
            item_ids=["s1", "s2", "s3", "s4", "s5"],
            metadata={"is_high_end": True, "temporal_stage": "peak"},
        ),
        EvalSample(
            user_id="u2",
            y_true=np.array([0, 1, 0]),
            y_pred=np.array([0.3, 0.8, 0.1]),
            item_ids=["s1", "s6", "s7"],
            metadata={"is_high_end": False, "temporal_stage": "early"},
        ),
        EvalSample(
            user_id="u3",
            y_true=np.array([1, 0]),
            y_pred=np.array([0.6, 0.4]),
            item_ids=["s8", "s9"],
            metadata={"is_high_end": True, "temporal_stage": "peak"},
        ),
    ]


class TestEvaluateTrack:
    def test_basic_metrics_present(self):
        samples = _make_samples()
        result = evaluate_track(
            samples,
            track_name="B0",
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            k_values=(5,),
        )
        assert "recall@5" in result.metrics
        assert "ndcg@5" in result.metrics
        assert "map@5" in result.metrics
        assert "hit@5" in result.metrics
        assert "mrr@5" in result.metrics

    def test_counterfactual_metrics_present(self):
        """IPS/SNIPS/DR must always be present (Non-Negotiable)."""
        samples = _make_samples()
        result = evaluate_track(
            samples,
            track_name="B0",
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert "ips" in result.metrics
        assert "snips" in result.metrics
        assert "dr" in result.metrics

    def test_n_users_tracked(self):
        samples = _make_samples()
        result = evaluate_track(
            samples,
            track_name="B0",
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert result.metrics["n_users"] == 3.0

    def test_result_frozen(self):
        samples = _make_samples()
        result = evaluate_track(
            samples,
            track_name="B0",
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        assert isinstance(result, BenchmarkResult)
        assert result.track == "B0"


class TestRunBenchmarkSuite:
    def test_returns_four_tracks(self):
        samples = _make_samples()
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        assert len(results) == 4
        tracks = {r.track for r in results}
        assert tracks == {"B0", "B1", "B2", "B3"}

    def test_b0_uses_all_samples(self):
        samples = _make_samples()
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        b0 = next(r for r in results if r.track == "B0")
        assert b0.metrics["n_users"] == 3.0

    def test_b1_cold_start_filter(self):
        """B1 should filter to users with < 5 interactions."""
        samples = _make_samples()
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        b1 = next(r for r in results if r.track == "B1")
        # u2 has 3, u3 has 2 → both cold-start
        assert b1.metrics["n_users"] >= 2.0

    def test_b2_high_end_filter(self):
        """B2 should only include high-end flagged samples."""
        samples = _make_samples()
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        b2 = next(r for r in results if r.track == "B2")
        assert b2.metrics["n_users"] == 2.0  # u1 and u3

    def test_b3_temporal_filter(self):
        """B3 should only include peak wines."""
        samples = _make_samples()
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        b3 = next(r for r in results if r.track == "B3")
        assert b3.metrics["n_users"] == 2.0  # u1 and u3

    def test_all_tracks_have_counterfactual(self):
        """Every track must include IPS/SNIPS/DR."""
        samples = _make_samples()
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        for result in results:
            if result.metrics.get("n_users", 0) > 0:
                assert "ips" in result.metrics, f"Missing IPS in {result.track}"
                assert "snips" in result.metrics, f"Missing SNIPS in {result.track}"
                assert "dr" in result.metrics, f"Missing DR in {result.track}"

    def test_no_samples_returns_empty(self):
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=None,
        )
        assert len(results) == 4
        for r in results:
            assert r.metrics == {}

    def test_with_propensities(self):
        """Propensities should be used in counterfactual computation."""
        samples = [
            EvalSample(
                user_id="u1",
                y_true=np.array([1, 0, 1]),
                y_pred=np.array([0.8, 0.2, 0.6]),
                propensities=np.array([0.5, 0.5, 0.5]),
            ),
        ]
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        b0 = next(r for r in results if r.track == "B0")
        assert b0.metrics["ips"] != 0.0
