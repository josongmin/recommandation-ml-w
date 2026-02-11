"""Tests for benchmark report export."""

from __future__ import annotations

import json
from pathlib import Path

from wine_rec.models.evaluation.evaluator import BenchmarkResult
from wine_rec.models.evaluation.long_horizon import judge_winner
from wine_rec.models.evaluation.report import (
    BenchmarkReport,
    PropensityStats,
    build_report,
    export_report,
)
from wine_rec.pipeline.quality_gates import check_propensity_gate


class TestBuildReport:
    def test_basic_report_structure(self):
        results = [
            BenchmarkResult(
                track="B0",
                model_name="bpr",
                model_version="v1",
                dataset_version="ds_v1",
                metrics={"recall@5": 0.8, "ndcg@5": 0.6, "ips": 0.5, "snips": 0.4, "dr": 0.45},
            ),
        ]
        report = build_report(benchmark_results=results)
        assert report.model_name == "bpr"
        assert "B0" in report.offline_metrics
        assert "recall@5" in report.offline_metrics["B0"]
        assert "ips" not in report.offline_metrics["B0"]
        assert "B0" in report.counterfactual_metrics
        assert "ips" in report.counterfactual_metrics["B0"]

    def test_empty_results(self):
        report = build_report(benchmark_results=[])
        assert report.model_name == ""
        assert report.offline_metrics == {}

    def test_with_winner_verdict(self):
        results = [
            BenchmarkResult(
                track="B0",
                model_name="bpr",
                model_version="v1",
                dataset_version="ds_v1",
                metrics={"recall@5": 0.8},
            ),
        ]
        verdict = judge_winner(
            repurchase_7d_decline=0.0,
            repurchase_30d_decline=0.0,
        )
        report = build_report(benchmark_results=results, winner_verdict=verdict)
        assert report.long_horizon_metrics["is_winner"] is True

    def test_with_propensity_stats(self):
        results = [
            BenchmarkResult(
                track="B0",
                model_name="bpr",
                model_version="v1",
                dataset_version="ds_v1",
                metrics={"recall@5": 0.8},
            ),
        ]
        stats = PropensityStats(
            total_samples=1000, missing_count=10, missing_rate=0.01, gate_passed=True
        )
        report = build_report(benchmark_results=results, propensity_stats=stats)
        assert report.propensity_stats["missing_rate"] == 0.01

    def test_with_quality_gates(self):
        results = [
            BenchmarkResult(
                track="B0",
                model_name="bpr",
                model_version="v1",
                dataset_version="ds_v1",
                metrics={"recall@5": 0.8},
            ),
        ]
        gate = check_propensity_gate(missing_rate=0.02)
        report = build_report(benchmark_results=results, quality_gate_results=[gate])
        assert len(report.quality_gates) == 1
        assert report.quality_gates[0]["passed"] is True


class TestExportReport:
    def test_writes_json_file(self, tmp_path: Path):
        report = BenchmarkReport(
            model_name="bpr",
            model_version="v1",
            dataset_version="ds_v1",
        )
        path = export_report(report, output_dir=str(tmp_path))
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["model_name"] == "bpr"
        assert data["report_version"] == "benchmark_report_v1"

    def test_creates_output_dir(self, tmp_path: Path):
        nested = tmp_path / "deep" / "nested"
        report = BenchmarkReport(model_name="test", model_version="v1")
        path = export_report(report, output_dir=str(nested))
        assert path.exists()
