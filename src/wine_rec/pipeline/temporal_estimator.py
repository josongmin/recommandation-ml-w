"""Model-aware temporal drinking window estimation (RFC-SOTA-ROADMAP-012 R3).

Provides rule-based, model-based, and expert-based estimation with
confidence-weighted merging.  Falls back gracefully when a method
is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

from wine_rec.common.logging import get_logger


log = get_logger(__name__)

# Wine type → (min_age, max_age) drinking windows
_DRINKING_WINDOWS: dict[str, tuple[int, int]] = {
    "red": (3, 12),
    "white": (1, 5),
    "sparkling": (1, 8),
    "rosé": (1, 3),
    "fortified": (5, 30),
    "dessert": (3, 20),
}

_DEFAULT_WINDOW: tuple[int, int] = (2, 8)


@dataclass(frozen=True)
class TemporalEstimate:
    """Single wine temporal estimate from a specific method."""

    drink_from_year: int
    drink_to_year: int
    confidence: float
    method: str  # "rule" | "model" | "expert"


def estimate_rule_based(
    *,
    wine_type: str,
    vintage_year: int,
    reference_year: int,
) -> TemporalEstimate:
    """Rule-based drinking window estimate.

    Uses wine type to determine age window, then derives current stage.
    Confidence is assigned heuristically based on stage certainty.
    """
    min_age, max_age = _DRINKING_WINDOWS.get(wine_type, _DEFAULT_WINDOW)
    drink_from = vintage_year + min_age
    drink_to = vintage_year + max_age

    if reference_year < drink_from:
        confidence = 0.7
    elif reference_year <= drink_to:
        mid = (drink_from + drink_to) / 2
        confidence = 0.6 if reference_year < mid else 0.8
    else:
        confidence = 0.5

    return TemporalEstimate(
        drink_from_year=drink_from,
        drink_to_year=drink_to,
        confidence=confidence,
        method="rule",
    )


def estimate_model_based(
    *,
    wine_type: str,
    variety: str,  # noqa: ARG001 - reserved for future ML model
    region: str,
    vintage_year: int,
    review_signals: dict[str, float],
    reference_year: int,  # noqa: ARG001 - reserved for future ML model
) -> TemporalEstimate | None:
    """Model-based estimate using review signals.

    Uses heuristic scoring based on review signals until ML model is trained.
    This is the extension point for Phase H+ ML-based temporal estimation.

    Heuristic approach (current):
    - High scores (90+) + old vintage → extended window
    - Low scores (<80) → shortened window
    - Premium regions → extended window

    Future ML features:
    - tannin_mentions / acidity_mentions / fruit_condition from reviews
    - critic avg rating (higher-rated reds often age better)
    - region-specific aging curves
    """
    # Extract review signals
    avg_score = review_signals.get("avg_score", 85.0)
    score_variance = review_signals.get("score_variance", 10.0)
    n_reviews = review_signals.get("n_reviews", 0)

    # Get base window from wine type
    min_age, max_age = _DRINKING_WINDOWS.get(wine_type.lower(), _DEFAULT_WINDOW)

    # Adjust window based on review signals
    score_multiplier = 1.0
    if avg_score >= 90:
        score_multiplier = 1.3  # Extend window for high-quality wines
    elif avg_score >= 85:
        score_multiplier = 1.1
    elif avg_score < 80:
        score_multiplier = 0.8  # Shorten window for lower-quality wines

    # Premium regions get extended windows
    premium_regions = {"bordeaux", "burgundy", "napa", "piedmont", "tuscany"}
    if region.lower() in premium_regions:
        score_multiplier *= 1.2

    # Apply multiplier
    adjusted_min = int(min_age * score_multiplier)
    adjusted_max = int(max_age * score_multiplier)

    # Compute drink window
    drink_from = vintage_year + adjusted_min
    drink_to = vintage_year + adjusted_max

    # Confidence based on review count and variance
    confidence = 0.6  # Base confidence for model-based
    if n_reviews > 50:
        confidence += 0.15
    if score_variance < 5:
        confidence += 0.1
    confidence = min(confidence, 0.9)

    log.debug(
        "temporal_model_estimate",
        wine_type=wine_type,
        avg_score=avg_score,
        multiplier=score_multiplier,
        window=(adjusted_min, adjusted_max),
        confidence=confidence,
    )

    return TemporalEstimate(
        drink_from_year=drink_from,
        drink_to_year=drink_to,
        confidence=confidence,
        method="model",
    )


def estimate_expert_based(
    *,
    expert_drink_from: int | None,
    expert_drink_to: int | None,
) -> TemporalEstimate | None:
    """Expert-provided estimate (when available in reviews/profiles).

    Returns None if no expert window data is available.
    """
    if expert_drink_from is None or expert_drink_to is None:
        return None

    if expert_drink_to < expert_drink_from:
        return None

    return TemporalEstimate(
        drink_from_year=expert_drink_from,
        drink_to_year=expert_drink_to,
        confidence=0.9,
        method="expert",
    )


def merge_estimates(
    estimates: list[TemporalEstimate],
) -> TemporalEstimate:
    """Merge multiple estimates with confidence-weighted averaging.

    Strategy:
    1. If expert estimate exists with confidence > 0.8, prefer it.
    2. Otherwise, weighted average by confidence.
    3. method = "ensemble" if multiple sources, else single source name.

    Raises:
        ValueError: If estimates list is empty.
    """
    if not estimates:
        msg = "At least one estimate is required"
        raise ValueError(msg)

    if len(estimates) == 1:
        return estimates[0]

    # Prefer high-confidence expert estimate
    for est in estimates:
        if est.method == "expert" and est.confidence > 0.8:
            return TemporalEstimate(
                drink_from_year=est.drink_from_year,
                drink_to_year=est.drink_to_year,
                confidence=est.confidence,
                method="ensemble",
            )

    # Confidence-weighted average
    total_weight = sum(e.confidence for e in estimates)
    if total_weight == 0:
        return estimates[0]

    avg_from = sum(e.drink_from_year * e.confidence for e in estimates) / total_weight
    avg_to = sum(e.drink_to_year * e.confidence for e in estimates) / total_weight
    max_conf = max(e.confidence for e in estimates)

    return TemporalEstimate(
        drink_from_year=round(avg_from),
        drink_to_year=round(avg_to),
        confidence=round(max_conf, 2),
        method="ensemble",
    )


def compute_current_stage(
    *,
    drink_from_year: int,
    drink_to_year: int,
    reference_year: int,
) -> str:
    """Compute current drinking stage from window bounds."""
    if reference_year < drink_from_year:
        return "too_young"
    if reference_year <= drink_to_year:
        mid = (drink_from_year + drink_to_year) / 2
        if reference_year < mid:
            return "early"
        return "peak"
    return "past"


def compute_peak_trajectory(
    *,
    drink_from_year: int,
    drink_to_year: int,
    reference_year: int,
) -> tuple[str, int | None]:
    """Compute peak trajectory and days-to-peak.

    Returns (trajectory, days_to_peak) where days_to_peak is:
    - positive = days until peak midpoint
    - negative = days past peak midpoint
    - None = unknown
    """
    mid = (drink_from_year + drink_to_year) / 2

    if reference_year < drink_from_year:
        days = int((mid - reference_year) * 365)
        return "approaching", days

    if reference_year <= drink_to_year:
        if reference_year <= mid:
            days = int((mid - reference_year) * 365)
            return "approaching" if days > 180 else "at_peak", max(days, 0)
        days = int((reference_year - mid) * -365)
        return "at_peak" if abs(days) < 365 else "declining", days

    days = int((reference_year - mid) * -365)
    return "declining", days
