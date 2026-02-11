"""Long-horizon winner judgment rules (RFC-EXEC-PLAN-014 §7-1).

Enforces: short-term CTR-only improvements cannot be declared winners.
Repurchase decline beyond threshold → deployment blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wine_rec.common.logging import get_logger


log = get_logger(__name__)


class JudgmentAction(StrEnum):
    """Possible actions from winner judgment."""

    PASS = "pass"  # noqa: S105
    BLOCK_DEPLOY = "block_deploy"
    TAG_SHORT_TERM_ONLY = "tag_short_term_only"


@dataclass(frozen=True)
class HorizonJudgment:
    """Result of a single long-horizon judgment rule."""

    rule_name: str
    action: JudgmentAction
    detail: str
    metric_value: float
    threshold: float


@dataclass(frozen=True)
class WinnerVerdict:
    """Aggregate winner verdict after applying all rules."""

    is_winner: bool
    judgments: tuple[HorizonJudgment, ...]
    tags: tuple[str, ...]


def check_repurchase_decline(
    *,
    period_label: str,
    decline_rate: float,
    threshold: float,
) -> HorizonJudgment:
    """Check if repurchase rate declined beyond threshold.

    Args:
        period_label: e.g. ``"7d"`` or ``"30d"``.
        decline_rate: Negative means decline (e.g. -0.06 = 6% decline).
        threshold: e.g. -0.05 for 7d, -0.03 for 30d.
            Blocked when ``decline_rate < threshold`` (strictly less).
    """
    blocked = decline_rate < threshold
    return HorizonJudgment(
        rule_name=f"{period_label}_repurchase_decline",
        action=JudgmentAction.BLOCK_DEPLOY if blocked else JudgmentAction.PASS,
        detail=f"{period_label} repurchase decline {decline_rate:.4f} vs threshold {threshold}",
        metric_value=decline_rate,
        threshold=threshold,
    )


def check_short_term_only(
    *,
    ctr_delta: float,
    repurchase_delta: float,
) -> HorizonJudgment:
    """Detect short-term-only improvement: CTR up but repurchase down."""
    is_short_term_only = ctr_delta > 0 and repurchase_delta < 0
    return HorizonJudgment(
        rule_name="short_term_only_improvement",
        action=JudgmentAction.TAG_SHORT_TERM_ONLY if is_short_term_only else JudgmentAction.PASS,
        detail=f"CTR delta={ctr_delta:.4f}, repurchase delta={repurchase_delta:.4f}",
        metric_value=ctr_delta,
        threshold=0.0,
    )


def judge_winner(
    *,
    repurchase_7d_decline: float,
    repurchase_30d_decline: float,
    ctr_delta: float = 0.0,
    repurchase_delta: float = 0.0,
) -> WinnerVerdict:
    """Apply all long-horizon rules and produce aggregate verdict.

    Returns :class:`WinnerVerdict` with ``is_winner=True`` only if
    no blocking or tagging rules fire.

    Thresholds (non-negotiable per RFC-EXEC-PLAN-014 §7-1):
        - 7d repurchase decline < -0.05 → block
        - 30d repurchase decline < -0.03 → block
        - CTR↑ AND repurchase↓ → tag short_term_only (not winner)
    """
    judgments: list[HorizonJudgment] = [
        check_repurchase_decline(
            period_label="7d",
            decline_rate=repurchase_7d_decline,
            threshold=-0.05,
        ),
        check_repurchase_decline(
            period_label="30d",
            decline_rate=repurchase_30d_decline,
            threshold=-0.03,
        ),
        check_short_term_only(
            ctr_delta=ctr_delta,
            repurchase_delta=repurchase_delta,
        ),
    ]

    tags: list[str] = []
    is_winner = True

    for j in judgments:
        if j.action == JudgmentAction.BLOCK_DEPLOY:
            is_winner = False
        if j.action == JudgmentAction.TAG_SHORT_TERM_ONLY:
            is_winner = False
            tags.append("short_term_only")

    log.info(
        "winner_judgment_complete",
        is_winner=is_winner,
        n_judgments=len(judgments),
        tags=tags,
    )

    return WinnerVerdict(
        is_winner=is_winner,
        judgments=tuple(judgments),
        tags=tuple(tags),
    )
