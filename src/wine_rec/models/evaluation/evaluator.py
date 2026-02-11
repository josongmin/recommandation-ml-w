"""Benchmark suite runner (RFC-DATASET-BENCH-005).

Tracks: B0 General, B1 Cold-start, B2 High-end, B3 Temporal-fit.
Every result includes IPS/SNIPS/DR (Non-Negotiable per §5-4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from wine_rec.common.logging import get_logger
from wine_rec.models.evaluation.counterfactual import (
    doubly_robust_estimate,
    ips_estimate,
    snips_estimate,
)
from wine_rec.models.evaluation.metrics import (
    hit_at_k,
    map_at_k,
    mrr,
    ndcg_at_k,
    recall_at_k,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

log = get_logger(__name__)


@dataclass(frozen=True)
class BenchmarkResult:
    """Evaluation result for a single benchmark track."""

    track: str
    model_name: str
    model_version: str
    dataset_version: str
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class EvalSample:
    """Per-user evaluation data."""

    user_id: str
    y_true: NDArray[np.int_]
    y_pred: NDArray[np.float64]
    propensities: NDArray[np.float64] | None = None
    item_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


def evaluate_track(
    samples: list[EvalSample],
    *,
    track_name: str,
    model_name: str,
    model_version: str,
    dataset_version: str,
    k_values: tuple[int, ...] = (5, 10, 20),
) -> BenchmarkResult:
    """Evaluate a single benchmark track on all metrics.

    Computes per-user Recall@K, NDCG@K, MAP@K, MRR, Hit@K,
    plus counterfactual IPS/SNIPS/DR.
    """
    metrics: dict[str, float] = {}

    for k in k_values:
        recalls: list[float] = []
        ndcgs: list[float] = []
        maps: list[float] = []
        hits: list[float] = []
        mrrs: list[float] = []

        for sample in samples:
            if sample.y_true.sum() == 0:
                continue
            recalls.append(recall_at_k(y_true=sample.y_true, y_pred=sample.y_pred, k=k))
            ndcgs.append(ndcg_at_k(y_true=sample.y_true, y_pred=sample.y_pred, k=k))
            maps.append(map_at_k(y_true=sample.y_true, y_pred=sample.y_pred, k=k))
            hits.append(hit_at_k(y_true=sample.y_true, y_pred=sample.y_pred, k=k))
            mrrs.append(mrr(y_true=sample.y_true, y_pred=sample.y_pred))

        n = len(recalls)
        metrics[f"recall@{k}"] = float(np.mean(recalls)) if n > 0 else 0.0
        metrics[f"ndcg@{k}"] = float(np.mean(ndcgs)) if n > 0 else 0.0
        metrics[f"map@{k}"] = float(np.mean(maps)) if n > 0 else 0.0
        metrics[f"hit@{k}"] = float(np.mean(hits)) if n > 0 else 0.0
        metrics[f"mrr@{k}"] = float(np.mean(mrrs)) if n > 0 else 0.0

    cf_metrics = _compute_counterfactual(samples)
    metrics.update(cf_metrics)
    metrics["n_users"] = float(len(samples))

    log.info("track_evaluated", track=track_name, n_users=len(samples), metrics=metrics)

    return BenchmarkResult(
        track=track_name,
        model_name=model_name,
        model_version=model_version,
        dataset_version=dataset_version,
        metrics=metrics,
    )


def _compute_counterfactual(samples: list[EvalSample]) -> dict[str, float]:
    """Compute IPS/SNIPS/DR across all samples.

    If propensities are not available, returns values with uniform propensities
    and logs a warning.
    """
    all_rewards: list[float] = []
    all_propensities: list[float] = []
    all_new_probs: list[float] = []
    all_model_preds: list[float] = []

    has_propensities = False

    for sample in samples:
        for i in range(len(sample.y_true)):
            reward = float(sample.y_true[i])
            pred = float(sample.y_pred[i])
            all_rewards.append(reward)
            all_new_probs.append(pred)
            all_model_preds.append(pred)

            if sample.propensities is not None and len(sample.propensities) > i:
                all_propensities.append(float(sample.propensities[i]))
                has_propensities = True
            else:
                all_propensities.append(1.0)

    if not all_rewards:
        return {"ips": 0.0, "snips": 0.0, "dr": 0.0}

    if not has_propensities:
        log.warning("counterfactual_no_propensities", msg="Using uniform propensities (1.0)")

    rewards = np.array(all_rewards, dtype=np.float64)
    propensities = np.array(all_propensities, dtype=np.float64)
    new_probs = np.array(all_new_probs, dtype=np.float64)
    model_preds = np.array(all_model_preds, dtype=np.float64)

    return {
        "ips": ips_estimate(rewards=rewards, propensities=propensities, new_policy_probs=new_probs),
        "snips": snips_estimate(
            rewards=rewards, propensities=propensities, new_policy_probs=new_probs
        ),
        "dr": doubly_robust_estimate(
            rewards=rewards,
            propensities=propensities,
            new_policy_probs=new_probs,
            reward_model_preds=model_preds,
        ),
    }


def _filter_cold_start(samples: list[EvalSample], *, threshold: int = 5) -> list[EvalSample]:
    """B1: Keep only users/items with fewer than threshold interactions."""
    return [s for s in samples if len(s.y_true) < threshold]


def _filter_high_end(samples: list[EvalSample]) -> list[EvalSample]:
    """B2: Keep only samples flagged as high-end."""
    return [s for s in samples if s.metadata.get("is_high_end", False)]


def _filter_temporal_fit(samples: list[EvalSample]) -> list[EvalSample]:
    """B3: Keep only samples where temporal stage is 'peak'."""
    return [s for s in samples if s.metadata.get("temporal_stage") == "peak"]


_TRACK_FILTERS: dict[str, Callable[[list[EvalSample]], list[EvalSample]]] = {
    "B0": lambda s: s,
    "B1": _filter_cold_start,
    "B2": _filter_high_end,
    "B3": _filter_temporal_fit,
}


def run_benchmark_suite(
    *,
    model_name: str,
    model_version: str,
    dataset_version: str,
    samples: list[EvalSample] | None = None,
    k_values: tuple[int, ...] = (5, 10, 20),
) -> list[BenchmarkResult]:
    """Run all benchmark tracks (B0~B3) for a model.

    Every result includes IPS/SNIPS/DR (Non-Negotiable).

    Args:
        model_name: Name of the model being evaluated.
        model_version: Version identifier.
        dataset_version: Dataset version for reproducibility.
        samples: Pre-computed per-user evaluation data.
            If None, returns empty results (for compatibility).
        k_values: K values for ranking metrics.

    Returns:
        List of BenchmarkResult, one per track.
    """
    if samples is None:
        log.warning("benchmark_no_samples", msg="No samples provided, returning empty results")
        return [
            BenchmarkResult(
                track=track,
                model_name=model_name,
                model_version=model_version,
                dataset_version=dataset_version,
            )
            for track in _TRACK_FILTERS
        ]

    results: list[BenchmarkResult] = []

    for track_name, filter_fn in _TRACK_FILTERS.items():
        filtered = filter_fn(samples)
        if not filtered:
            log.warning("benchmark_empty_track", track=track_name)
            results.append(
                BenchmarkResult(
                    track=track_name,
                    model_name=model_name,
                    model_version=model_version,
                    dataset_version=dataset_version,
                    metrics={"n_users": 0.0},
                )
            )
            continue

        result = evaluate_track(
            filtered,
            track_name=track_name,
            model_name=model_name,
            model_version=model_version,
            dataset_version=dataset_version,
            k_values=k_values,
        )
        results.append(result)

    log.info(
        "benchmark_suite_complete",
        model_name=model_name,
        n_tracks=len(results),
    )
    return results
