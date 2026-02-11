"""Tests for A/B testing framework."""

from __future__ import annotations

import numpy as np
import pytest

from wine_rec.monitoring.ab_test import (
    ABTest,
    BanditVariant,
    ThompsonSamplingBandit,
    Variant,
)


def test_variant_assignment_stable() -> None:
    """Test hash-based variant assignment is stable for same user."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=0.5),
        Variant(
            variant_id="challenger", model_name="lightgcn", model_version="v2", traffic_weight=0.5
        ),
    ]
    test = ABTest(experiment_id="exp_001", variants=variants)

    # Same user should always get same variant
    variant1 = test.assign_variant(user_id="user_123")
    variant2 = test.assign_variant(user_id="user_123")
    assert variant1.variant_id == variant2.variant_id


def test_variant_assignment_distribution() -> None:
    """Test traffic split matches configured weights."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=0.7),
        Variant(
            variant_id="challenger", model_name="lightgcn", model_version="v2", traffic_weight=0.3
        ),
    ]
    test = ABTest(experiment_id="exp_002", variants=variants)

    # Assign 10000 users
    counts = {"baseline": 0, "challenger": 0}
    for i in range(10000):
        variant = test.assign_variant(user_id=f"user_{i}")
        counts[variant.variant_id] += 1

    # Check distribution (allow ±5% tolerance)
    assert 0.65 < counts["baseline"] / 10000 < 0.75
    assert 0.25 < counts["challenger"] / 10000 < 0.35


def test_record_and_get_metric() -> None:
    """Test metric recording and retrieval."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=1.0),
    ]
    test = ABTest(experiment_id="exp_003", variants=variants)

    test.record_metric(variant_id="baseline", metric_name="ctr", value=0.05)
    test.record_metric(variant_id="baseline", metric_name="ctr", value=0.07)
    test.record_metric(variant_id="baseline", metric_name="ctr", value=0.06)

    metric = test.get_metric(variant_id="baseline", metric_name="ctr")
    assert metric.n_requests == 3
    assert metric.mean == pytest.approx(0.06, abs=1e-6)


def test_metric_variance() -> None:
    """Test metric variance calculation."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=1.0),
    ]
    test = ABTest(experiment_id="exp_004", variants=variants)

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    for v in values:
        test.record_metric(variant_id="baseline", metric_name="revenue", value=v)

    metric = test.get_metric(variant_id="baseline", metric_name="revenue")
    assert metric.mean == 3.0
    # Sample variance: sum((x - mean)^2) / (n - 1) = 10 / 4 = 2.5
    assert metric.variance == pytest.approx(2.5, abs=1e-6)
    assert metric.std == pytest.approx(1.5811, abs=1e-3)


def test_compare_variants_significant_difference() -> None:
    """Test t-test detects significant difference."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=0.5),
        Variant(
            variant_id="challenger", model_name="lightgcn", model_version="v2", traffic_weight=0.5
        ),
    ]
    test = ABTest(experiment_id="exp_005", variants=variants, min_sample_size=10)

    # Baseline: mean=0.05, challenger: mean=0.10 (2x improvement)
    rng = np.random.default_rng(42)
    for _ in range(1000):
        test.record_metric(variant_id="baseline", metric_name="ctr", value=rng.normal(0.05, 0.01))
        test.record_metric(variant_id="challenger", metric_name="ctr", value=rng.normal(0.10, 0.01))

    result = test.compare_variants(
        variant_a_id="baseline",
        variant_b_id="challenger",
        metric_name="ctr",
        test_type="t_test",
    )

    assert result.mean_a == pytest.approx(0.05, abs=0.01)
    assert result.mean_b == pytest.approx(0.10, abs=0.01)
    assert result.delta > 0
    assert result.delta_pct == pytest.approx(100, abs=10)
    assert result.p_value < 0.05  # Statistically significant
    assert result.is_significant is True


def test_compare_variants_no_difference() -> None:
    """Test t-test does not detect difference when none exists."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=0.5),
        Variant(
            variant_id="challenger", model_name="bpr", model_version="v1.1", traffic_weight=0.5
        ),
    ]
    test = ABTest(experiment_id="exp_006", variants=variants, min_sample_size=10)

    # Both variants have same mean
    rng = np.random.default_rng(42)
    for _ in range(1000):
        test.record_metric(variant_id="baseline", metric_name="ctr", value=rng.normal(0.05, 0.01))
        test.record_metric(variant_id="challenger", metric_name="ctr", value=rng.normal(0.05, 0.01))

    result = test.compare_variants(
        variant_a_id="baseline",
        variant_b_id="challenger",
        metric_name="ctr",
        test_type="t_test",
    )

    assert result.p_value > 0.05  # Not statistically significant
    assert result.is_significant is False


def test_guardrail_violation() -> None:
    """Test guardrail metric enforcement."""
    variants = [
        Variant(
            variant_id="challenger", model_name="lightgcn", model_version="v2", traffic_weight=1.0
        ),
    ]
    test = ABTest(
        experiment_id="exp_007",
        variants=variants,
        guardrail_metrics={"latency_p95": ("<=", 100.0)},
    )

    # Record high latencies (violates guardrail)
    for _ in range(10):
        test.record_metric(variant_id="challenger", metric_name="latency_p95", value=150.0)

    results = test.check_guardrails(variant_id="challenger")
    assert results["latency_p95"] is False  # Violation


def test_guardrail_pass() -> None:
    """Test guardrail metric passes."""
    variants = [
        Variant(
            variant_id="challenger", model_name="lightgcn", model_version="v2", traffic_weight=1.0
        ),
    ]
    test = ABTest(
        experiment_id="exp_008",
        variants=variants,
        guardrail_metrics={"latency_p95": ("<=", 100.0)},
    )

    # Record low latencies (passes guardrail)
    for _ in range(10):
        test.record_metric(variant_id="challenger", metric_name="latency_p95", value=50.0)

    results = test.check_guardrails(variant_id="challenger")
    assert results["latency_p95"] is True  # Pass


def test_thompson_sampling_select_variant() -> None:
    """Test Thompson Sampling variant selection."""
    variants = [
        BanditVariant(variant_id="baseline", model_name="bpr", model_version="v1"),
        BanditVariant(variant_id="challenger", model_name="lightgcn", model_version="v2"),
    ]
    bandit = ThompsonSamplingBandit(experiment_id="exp_009", variants=variants)

    rng = np.random.default_rng(42)
    variant = bandit.select_variant(rng=rng)

    assert variant.variant_id in ["baseline", "challenger"]


def test_thompson_sampling_update() -> None:
    """Test Thompson Sampling updates Beta posterior."""
    variants = [
        BanditVariant(variant_id="baseline", model_name="bpr", model_version="v1"),
    ]
    bandit = ThompsonSamplingBandit(experiment_id="exp_010", variants=variants)

    # Record successes
    bandit.update(variant_id="baseline", success=True)
    bandit.update(variant_id="baseline", success=True)
    bandit.update(variant_id="baseline", success=False)

    variant = bandit.variants["baseline"]
    assert variant.successes == 2
    assert variant.failures == 1
    assert variant.alpha == 3  # successes + 1
    assert variant.beta == 2  # failures + 1


def test_thompson_sampling_convergence() -> None:
    """Test Thompson Sampling converges to better variant."""
    variants = [
        BanditVariant(variant_id="good", model_name="lightgcn", model_version="v2"),
        BanditVariant(variant_id="bad", model_name="bpr", model_version="v1"),
    ]
    bandit = ThompsonSamplingBandit(experiment_id="exp_011", variants=variants)

    rng = np.random.default_rng(42)

    # Simulate 1000 rounds: "good" has 80% success, "bad" has 20%
    for _ in range(1000):
        variant = bandit.select_variant(rng=rng)
        if variant.variant_id == "good":
            success = rng.random() < 0.8
        else:
            success = rng.random() < 0.2
        bandit.update(variant_id=variant.variant_id, success=success)

    stats = bandit.get_statistics()

    # "good" should have higher mean than "bad"
    assert stats["good"]["mean"] > stats["bad"]["mean"]
    # "good" should have more selections (convergence)
    assert stats["good"]["n"] > stats["bad"]["n"]


def test_ab_test_invalid_weights() -> None:
    """Test A/B test rejects invalid traffic weights."""
    variants = [
        Variant(variant_id="baseline", model_name="bpr", model_version="v1", traffic_weight=0.3),
        Variant(
            variant_id="challenger", model_name="lightgcn", model_version="v2", traffic_weight=0.5
        ),
    ]

    with pytest.raises(ValueError, match="Traffic weights must sum to 1.0"):
        ABTest(experiment_id="exp_012", variants=variants)
