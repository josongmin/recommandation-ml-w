"""A/B Testing Framework for model variants.

Industry SOTA practices from Meta/Netflix/Uber.
- Traffic splitting (hash-based stable assignment)
- Guardrail metrics (latency, error rate)
- Statistical significance testing (t-test, Mann-Whitney U)
- Bandit-based allocation (Thompson Sampling for variant selection)
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

from wine_rec.common.logging import get_logger


log = get_logger(__name__)


class VariantStatus(StrEnum):
    """A/B test variant status."""

    ACTIVE = "active"
    PAUSED = "paused"
    WINNER = "winner"
    LOSER = "loser"


@dataclass
class Variant:
    """Model variant configuration."""

    variant_id: str
    model_name: str
    model_version: str
    traffic_weight: float
    status: VariantStatus = VariantStatus.ACTIVE
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Metric:
    """Metric accumulator for a variant."""

    variant_id: str
    n_requests: int = 0
    sum_value: float = 0.0
    sum_squared: float = 0.0
    values: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        """Sample mean."""
        if self.n_requests == 0:
            return 0.0
        return self.sum_value / self.n_requests

    @property
    def variance(self) -> float:
        """Sample variance (Bessel's correction)."""
        if self.n_requests < 2:
            return 0.0
        return (self.sum_squared - (self.sum_value**2 / self.n_requests)) / (self.n_requests - 1)

    @property
    def std(self) -> float:
        """Sample standard deviation."""
        return math.sqrt(self.variance)

    def record(self, value: float) -> None:
        """Record a new metric value."""
        self.n_requests += 1
        self.sum_value += value
        self.sum_squared += value**2
        self.values.append(value)


@dataclass
class ABTestResult:
    """A/B test comparison result."""

    variant_a: str
    variant_b: str
    metric_name: str
    mean_a: float
    mean_b: float
    delta: float
    delta_pct: float
    p_value: float
    is_significant: bool
    confidence_level: float


class ABTest:
    """A/B testing framework with traffic splitting and statistical testing.

    Production workflow:
    1. Define variants (baseline + challengers)
    2. Split traffic via stable hash (user_id → variant)
    3. Record metrics (CTR, revenue, latency)
    4. Check guardrails (p95 latency < 100ms)
    5. Compute statistical significance (t-test, Mann-Whitney U)
    6. Promote winner if Δ metric > MDE (minimum detectable effect)
    """

    def __init__(
        self,
        *,
        experiment_id: str,
        variants: list[Variant],
        primary_metric: str = "ctr",
        guardrail_metrics: dict[str, tuple[str, float]] | None = None,
        min_sample_size: int = 1000,
        confidence_level: float = 0.95,
    ) -> None:
        """Initialize A/B test.

        Args:
            experiment_id: Unique experiment identifier
            variants: List of model variants (must sum to 1.0 traffic weight)
            primary_metric: Main decision metric (e.g., "ctr", "revenue")
            guardrail_metrics: Safety checks {"latency_p95": ("<=", 100.0)}
            min_sample_size: Minimum samples per variant before testing
            confidence_level: Statistical confidence (0.95 = 95%)
        """
        self.experiment_id = experiment_id
        self.variants = {v.variant_id: v for v in variants}
        self.primary_metric = primary_metric
        self.guardrail_metrics = guardrail_metrics or {}
        self.min_sample_size = min_sample_size
        self.confidence_level = confidence_level

        # Validate traffic weights
        total_weight = sum(v.traffic_weight for v in variants)
        if not math.isclose(total_weight, 1.0, abs_tol=1e-6):
            msg = f"Traffic weights must sum to 1.0, got {total_weight}"
            raise ValueError(msg)

        # Metric accumulators: {variant_id: {metric_name: Metric}}
        self._metrics: dict[str, dict[str, Metric]] = {vid: {} for vid in self.variants}

        log.info(
            "ab_test_init",
            experiment_id=experiment_id,
            n_variants=len(variants),
            primary_metric=primary_metric,
        )

    def assign_variant(self, *, user_id: str) -> Variant:
        """Assign user to a variant via stable hash-based splitting.

        Hash-based assignment ensures:
        - Stability: same user_id → same variant
        - Balance: uniform distribution across variants
        - Independence: no temporal bias
        """
        hash_value = int(hashlib.md5(f"{self.experiment_id}:{user_id}".encode()).hexdigest(), 16)
        normalized = (hash_value % 10000) / 10000.0

        cumulative = 0.0
        for variant in self.variants.values():
            if variant.status != VariantStatus.ACTIVE:
                continue
            cumulative += variant.traffic_weight
            if normalized < cumulative:
                return variant

        # Fallback to first active variant
        return next(v for v in self.variants.values() if v.status == VariantStatus.ACTIVE)

    def record_metric(self, *, variant_id: str, metric_name: str, value: float) -> None:
        """Record a metric observation for a variant."""
        if variant_id not in self._metrics:
            msg = f"Unknown variant: {variant_id}"
            raise ValueError(msg)

        if metric_name not in self._metrics[variant_id]:
            self._metrics[variant_id][metric_name] = Metric(variant_id=variant_id)

        self._metrics[variant_id][metric_name].record(value)

    def get_metric(self, *, variant_id: str, metric_name: str) -> Metric:
        """Get accumulated metric for a variant."""
        return self._metrics.get(variant_id, {}).get(
            metric_name,
            Metric(variant_id=variant_id),
        )

    def compare_variants(
        self,
        *,
        variant_a_id: str,
        variant_b_id: str,
        metric_name: str,
        test_type: str = "t_test",
    ) -> ABTestResult:
        """Compare two variants using statistical testing.

        Args:
            variant_a_id: Baseline variant
            variant_b_id: Challenger variant
            metric_name: Metric to compare
            test_type: "t_test" (parametric) or "mann_whitney" (non-parametric)

        Returns:
            ABTestResult with means, delta, p-value, significance
        """
        metric_a = self.get_metric(variant_id=variant_a_id, metric_name=metric_name)
        metric_b = self.get_metric(variant_id=variant_b_id, metric_name=metric_name)

        if metric_a.n_requests < self.min_sample_size or metric_b.n_requests < self.min_sample_size:
            log.warning(
                "ab_test_insufficient_samples",
                variant_a=variant_a_id,
                variant_b=variant_b_id,
                n_a=metric_a.n_requests,
                n_b=metric_b.n_requests,
                min_required=self.min_sample_size,
            )

        mean_a, mean_b = metric_a.mean, metric_b.mean
        delta = mean_b - mean_a
        delta_pct = (delta / mean_a * 100) if mean_a != 0 else 0.0

        if test_type == "t_test":
            p_value = self._welch_t_test(metric_a, metric_b)
        elif test_type == "mann_whitney":
            p_value = self._mann_whitney_u_test(metric_a, metric_b)
        else:
            msg = f"Unknown test_type: {test_type}"
            raise ValueError(msg)

        alpha = 1 - self.confidence_level
        is_significant = p_value < alpha

        return ABTestResult(
            variant_a=variant_a_id,
            variant_b=variant_b_id,
            metric_name=metric_name,
            mean_a=mean_a,
            mean_b=mean_b,
            delta=delta,
            delta_pct=delta_pct,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=self.confidence_level,
        )

    def check_guardrails(self, *, variant_id: str) -> dict[str, bool]:
        """Check if variant violates guardrail metrics.

        Returns:
            {metric_name: is_safe} for each guardrail
        """
        results: dict[str, bool] = {}

        for metric_name, (operator, threshold) in self.guardrail_metrics.items():
            metric = self.get_metric(variant_id=variant_id, metric_name=metric_name)
            value = metric.mean

            if operator == "<=":
                is_safe = value <= threshold
            elif operator == ">=":
                is_safe = value >= threshold
            elif operator == "<":
                is_safe = value < threshold
            elif operator == ">":
                is_safe = value > threshold
            else:
                msg = f"Unknown operator: {operator}"
                raise ValueError(msg)

            results[metric_name] = is_safe

            if not is_safe:
                log.warning(
                    "guardrail_violation",
                    variant_id=variant_id,
                    metric_name=metric_name,
                    value=value,
                    threshold=threshold,
                    operator=operator,
                )

        return results

    @staticmethod
    def _welch_t_test(metric_a: Metric, metric_b: Metric) -> float:
        """Welch's t-test for unequal variances (two-tailed).

        More robust than Student's t-test when variances differ.
        """
        if metric_a.n_requests < 2 or metric_b.n_requests < 2:
            return 1.0

        mean_a, mean_b = metric_a.mean, metric_b.mean
        var_a, var_b = metric_a.variance, metric_b.variance
        n_a, n_b = metric_a.n_requests, metric_b.n_requests

        # Welch-Satterthwaite degrees of freedom
        numerator = (var_a / n_a + var_b / n_b) ** 2
        denominator = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        df = numerator / denominator if denominator > 0 else 1.0

        # t-statistic
        pooled_se = math.sqrt(var_a / n_a + var_b / n_b)
        if pooled_se == 0:
            return 1.0
        t_stat = abs((mean_a - mean_b) / pooled_se)

        # Two-tailed p-value (approximation via normal CDF for large df)
        from scipy.stats import t as t_dist  # type: ignore[import-untyped]

        p_value = 2 * (1 - t_dist.cdf(t_stat, df))
        return float(p_value)

    @staticmethod
    def _mann_whitney_u_test(metric_a: Metric, metric_b: Metric) -> float:
        """Mann-Whitney U test (non-parametric, two-tailed).

        Better for non-normal distributions or small samples.
        """
        from scipy.stats import mannwhitneyu  # type: ignore[import-untyped]

        if not metric_a.values or not metric_b.values:
            return 1.0

        u_stat, p_value = mannwhitneyu(
            metric_a.values,
            metric_b.values,
            alternative="two-sided",
        )
        return float(p_value)

    def get_summary(self) -> dict[str, dict[str, float]]:
        """Get summary statistics for all variants and metrics."""
        summary: dict[str, dict[str, float]] = {}

        for variant_id, metrics in self._metrics.items():
            summary[variant_id] = {}
            for metric_name, metric in metrics.items():
                summary[variant_id][f"{metric_name}_mean"] = metric.mean
                summary[variant_id][f"{metric_name}_std"] = metric.std
                summary[variant_id][f"{metric_name}_n"] = float(metric.n_requests)

        return summary


@dataclass
class BanditVariant:
    """Variant for Thompson Sampling bandit allocation."""

    variant_id: str
    model_name: str
    model_version: str
    successes: int = 0
    failures: int = 0

    @property
    def alpha(self) -> int:
        """Beta distribution alpha parameter (successes + 1)."""
        return self.successes + 1

    @property
    def beta(self) -> int:
        """Beta distribution beta parameter (failures + 1)."""
        return self.failures + 1


class ThompsonSamplingBandit:
    """Thompson Sampling for dynamic variant allocation.

    Industry use case (Netflix/Spotify):
    - Start with uniform allocation (20/20/20/20/20%)
    - Update Beta(successes, failures) after each request
    - Sample from posterior → allocate to best variant
    - Converges to optimal variant over time
    """

    def __init__(self, *, experiment_id: str, variants: list[BanditVariant]) -> None:
        """Initialize Thompson Sampling bandit.

        Args:
            experiment_id: Unique experiment identifier
            variants: List of model variants with Beta priors
        """
        self.experiment_id = experiment_id
        self.variants = {v.variant_id: v for v in variants}

        log.info(
            "thompson_bandit_init",
            experiment_id=experiment_id,
            n_variants=len(variants),
        )

    def select_variant(self, *, rng: np.random.Generator | None = None) -> BanditVariant:
        """Sample from Beta posterior and select variant with highest draw.

        Args:
            rng: Random number generator (for reproducibility)

        Returns:
            Selected variant
        """
        if rng is None:
            rng = np.random.default_rng()

        samples: dict[str, float] = {}
        for variant in self.variants.values():
            samples[variant.variant_id] = rng.beta(variant.alpha, variant.beta)

        best_variant_id = max(samples, key=samples.get)  # type: ignore[arg-type]
        return self.variants[best_variant_id]

    def update(self, *, variant_id: str, success: bool) -> None:
        """Update Beta posterior after observing reward.

        Args:
            variant_id: Variant that was shown
            success: Whether user engaged (clicked, purchased, etc.)
        """
        variant = self.variants[variant_id]
        if success:
            variant.successes += 1
        else:
            variant.failures += 1

    def get_statistics(self) -> dict[str, dict[str, float]]:
        """Get posterior statistics for all variants."""
        stats: dict[str, dict[str, float]] = {}

        for variant_id, variant in self.variants.items():
            mean = variant.alpha / (variant.alpha + variant.beta)
            variance = (variant.alpha * variant.beta) / (
                (variant.alpha + variant.beta) ** 2 * (variant.alpha + variant.beta + 1)
            )
            stats[variant_id] = {
                "mean": mean,
                "std": math.sqrt(variance),
                "successes": float(variant.successes),
                "failures": float(variant.failures),
                "n": float(variant.successes + variant.failures),
            }

        return stats
