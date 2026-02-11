"""E2E: evaluation -> long-horizon judgment -> report export."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wine_rec.models.evaluation.evaluator import EvalSample, run_benchmark_suite
from wine_rec.models.evaluation.long_horizon import judge_winner
from wine_rec.models.evaluation.report import build_report, export_report
from wine_rec.pipeline.quality_gates import check_propensity_gate


@pytest.mark.e2e
class TestEvaluateToReportFlow:
    """Test the evaluation -> report pipeline."""

    def test_full_evaluation_to_report(self, tmp_path: Path):
        # 1. Create evaluation samples
        samples = [
            EvalSample(
                user_id="u1",
                y_true=np.array([1, 0, 1, 0]),
                y_pred=np.array([0.9, 0.2, 0.7, 0.1]),
                propensities=np.array([0.5, 0.5, 0.5, 0.5]),
                metadata={"is_high_end": True, "temporal_stage": "peak"},
            ),
            EvalSample(
                user_id="u2",
                y_true=np.array([0, 1]),
                y_pred=np.array([0.3, 0.8]),
                propensities=np.array([0.5, 0.5]),
                metadata={"is_high_end": False, "temporal_stage": "early"},
            ),
        ]

        # 2. Run benchmark suite
        results = run_benchmark_suite(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
            samples=samples,
        )
        assert len(results) == 4  # B0, B1, B2, B3

        # 3. Run long-horizon judgment
        verdict = judge_winner(
            repurchase_7d_decline=0.0,
            repurchase_30d_decline=0.0,
        )
        assert verdict.is_winner

        # 4. Check propensity gate
        gate = check_propensity_gate(missing_rate=0.02)
        assert gate.passed

        # 5. Build and export report
        report = build_report(
            benchmark_results=results,
            winner_verdict=verdict,
            quality_gate_results=[gate],
        )
        path = export_report(report, output_dir=str(tmp_path))

        # 6. Verify report content
        data = json.loads(path.read_text())
        assert data["model_name"] == "bpr"
        assert data["report_version"] == "benchmark_report_v1"
        assert "B0" in data["offline_metrics"]
        assert data["long_horizon_metrics"]["is_winner"] is True
        assert len(data["quality_gates"]) == 1
        assert data["quality_gates"][0]["passed"] is True
