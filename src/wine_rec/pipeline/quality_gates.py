"""Quality gates (RFC-E2E-PIPELINE-006 §10, RFC-DATASET-BUILDER-011 §9)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateResult:
    """Result of a quality gate check."""

    gate_name: str
    passed: bool
    metric_value: float
    threshold: float
    detail: str = ""


def check_leakage_gate(*, violation_rate: float) -> GateResult:
    """Leakage gate: violation_rate must be 0.0 (hard fail)."""
    return GateResult(
        gate_name="leakage",
        passed=violation_rate == 0.0,
        metric_value=violation_rate,
        threshold=0.0,
        detail="as_of_ts <= event_ts and published_at <= event_ts",
    )


def check_join_success_gate(*, success_rate: float, threshold: float = 0.99) -> GateResult:
    """Join success gate: impression→policy join rate >= threshold."""
    return GateResult(
        gate_name="join_success",
        passed=success_rate >= threshold,
        metric_value=success_rate,
        threshold=threshold,
    )


def check_propensity_gate(*, missing_rate: float) -> GateResult:
    """Propensity gate: missing rate >20% blocks counterfactual evaluation.

    RFC-LOG-SCHEMA-009 propensity 강제 규칙.
    """
    return GateResult(
        gate_name="propensity_completeness",
        passed=missing_rate <= 0.20,
        metric_value=missing_rate,
        threshold=0.20,
        detail="block at >20%",
    )


def check_propensity_warning(*, missing_rate: float) -> GateResult:
    """Propensity warning gate: >5% missing rate triggers advisory warning.

    This is the warning tier; :func:`check_propensity_gate` handles blocking.
    """
    return GateResult(
        gate_name="propensity_warning",
        passed=missing_rate <= 0.05,
        metric_value=missing_rate,
        threshold=0.05,
        detail="warn when >5% propensity missing",
    )


@dataclass(frozen=True)
class PropensityCheckResult:
    """Combined propensity check: warn + block levels."""

    warning: GateResult
    blocking: GateResult

    @property
    def should_proceed(self) -> bool:
        """True if blocking gate passes (warning is advisory only)."""
        return self.blocking.passed


def check_propensity_full(*, missing_rate: float) -> PropensityCheckResult:
    """Run both propensity gates (warn >5%, block >20%)."""
    return PropensityCheckResult(
        warning=check_propensity_warning(missing_rate=missing_rate),
        blocking=check_propensity_gate(missing_rate=missing_rate),
    )
