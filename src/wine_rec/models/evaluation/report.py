"""Benchmark report export (RFC-DATASET-BENCH-005 §7-2).

Full JSON report with offline_metrics, counterfactual_metrics,
long_horizon_metrics, propensity_stats.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wine_rec.common.logging import get_logger


if TYPE_CHECKING:
    from wine_rec.models.evaluation.evaluator import BenchmarkResult
    from wine_rec.models.evaluation.long_horizon import WinnerVerdict
    from wine_rec.pipeline.quality_gates import GateResult


log = get_logger(__name__)

_CF_KEYS = frozenset({"ips", "snips", "dr"})


@dataclass(frozen=True)
class PropensityStats:
    """Propensity completeness statistics for the report."""

    total_samples: int
    missing_count: int
    missing_rate: float
    gate_passed: bool


@dataclass(frozen=True)
class BenchmarkReport:
    """Full benchmark report (RFC-DATASET-BENCH-005 §7-2)."""

    report_version: str = "benchmark_report_v1"
    model_name: str = ""
    model_version: str = ""
    dataset_version: str = ""
    generated_at: str = ""
    offline_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    counterfactual_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    long_horizon_metrics: dict[str, Any] = field(default_factory=dict)
    propensity_stats: dict[str, Any] = field(default_factory=dict)
    quality_gates: list[dict[str, Any]] = field(default_factory=list)


def build_report(
    *,
    benchmark_results: list[BenchmarkResult],
    winner_verdict: WinnerVerdict | None = None,
    propensity_stats: PropensityStats | None = None,
    quality_gate_results: list[GateResult] | None = None,
) -> BenchmarkReport:
    """Build a full benchmark report from evaluation outputs.

    Separates offline metrics from counterfactual metrics (ips/snips/dr)
    for each benchmark track.
    """
    if not benchmark_results:
        return BenchmarkReport()

    first = benchmark_results[0]
    now = datetime.now(tz=UTC).isoformat()

    offline: dict[str, dict[str, float]] = {}
    counterfactual: dict[str, dict[str, float]] = {}

    for result in benchmark_results:
        track_offline = {k: v for k, v in result.metrics.items() if k not in _CF_KEYS}
        track_cf = {k: v for k, v in result.metrics.items() if k in _CF_KEYS}
        offline[result.track] = track_offline
        if track_cf:
            counterfactual[result.track] = track_cf

    long_horizon: dict[str, Any] = {}
    if winner_verdict is not None:
        long_horizon = {
            "is_winner": winner_verdict.is_winner,
            "tags": list(winner_verdict.tags),
            "judgments": [asdict(j) for j in winner_verdict.judgments],
        }

    prop_dict: dict[str, Any] = {}
    if propensity_stats is not None:
        prop_dict = asdict(propensity_stats)

    gates: list[dict[str, Any]] = []
    if quality_gate_results:
        gates = [asdict(g) for g in quality_gate_results]

    return BenchmarkReport(
        model_name=first.model_name,
        model_version=first.model_version,
        dataset_version=first.dataset_version,
        generated_at=now,
        offline_metrics=offline,
        counterfactual_metrics=counterfactual,
        long_horizon_metrics=long_horizon,
        propensity_stats=prop_dict,
        quality_gates=gates,
    )


def export_report(report: BenchmarkReport, *, output_dir: str) -> Path:
    """Serialize report to JSON and write to output directory.

    Returns the path to the written file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"benchmark_report_{report.model_name}_{report.model_version}.json"
    filepath = out / filename
    with filepath.open("w") as f:
        json.dump(asdict(report), f, indent=2, default=str)
    log.info("report_exported", path=str(filepath))
    return filepath
