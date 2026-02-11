"""Feature parity checker (RFC-FEATURE-MANIFEST-010 §5).

Online/Offline feature diff = 0 for critical tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wine_rec.schemas.manifest import FeatureTier


@dataclass(frozen=True)
class ParityResult:
    """Parity check result for a single feature."""

    feature_name: str
    tier: FeatureTier
    online_value: Any
    offline_value: Any
    diff: float
    passed: bool


def check_parity(
    *,
    feature_name: str,
    tier: FeatureTier,
    online_value: Any,
    offline_value: Any,
    eps: float = 1e-6,
) -> ParityResult:
    """Compare online vs offline feature value.

    Critical tier: diff == 0 (strict).
    Important tier: diff == 0 (principle, allowlist possible initially).
    Experimental tier: report only.
    """
    if isinstance(online_value, float) and isinstance(offline_value, float):
        diff = abs(online_value - offline_value)
        passed = diff <= eps
    else:
        diff = 0.0 if online_value == offline_value else 1.0
        passed = online_value == offline_value

    if tier == FeatureTier.EXPERIMENTAL:
        passed = True  # report only

    return ParityResult(
        feature_name=feature_name,
        tier=tier,
        online_value=online_value,
        offline_value=offline_value,
        diff=diff,
        passed=passed,
    )
