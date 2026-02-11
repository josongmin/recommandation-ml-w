"""Challenge track definitions and leaderboard infrastructure (C1-C3).

External validation tracks per RFC-SOTA-ROADMAP-012 §5-2:
- C1: High-end slice leaderboard
- C2: Cold-start only track
- C3: Expert-aware track
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from wine_rec.common.logging import get_logger
from wine_rec.models.evaluation.evaluator import evaluate_track


if TYPE_CHECKING:
    from wine_rec.contracts.object_store import ObjectStore
    from wine_rec.models.evaluation.evaluator import EvalSample

log = get_logger(__name__)


class ChallengeTrack(StrEnum):
    """Challenge track identifiers."""

    HIGH_END = "C1_high_end"
    COLD_START = "C2_cold_start"
    EXPERT_AWARE = "C3_expert_aware"


@dataclass(frozen=True)
class ChallengeSpec:
    """Specification for a single challenge track."""

    track: ChallengeTrack
    description: str
    dataset_filter: str
    primary_metric: str
    secondary_metrics: tuple[str, ...]
    required_metadata_fields: tuple[str, ...]


@dataclass(frozen=True)
class LeaderboardEntry:
    """A single entry on the leaderboard."""

    track: ChallengeTrack
    model_name: str
    model_version: str
    dataset_version: str
    primary_score: float
    all_metrics: dict[str, float] = field(default_factory=dict)
    submitted_at: str = ""


@dataclass(frozen=True)
class Leaderboard:
    """Sorted leaderboard for a single challenge track."""

    track: ChallengeTrack
    entries: tuple[LeaderboardEntry, ...]
    generated_at: str = ""


# ── Challenge specifications (frozen constants) ──

CHALLENGE_SPECS: dict[ChallengeTrack, ChallengeSpec] = {
    ChallengeTrack.HIGH_END: ChallengeSpec(
        track=ChallengeTrack.HIGH_END,
        description="High-end wine recommendation: top price percentile + low production",
        dataset_filter="is_high_end",
        primary_metric="ndcg@10",
        secondary_metrics=("recall@10", "map@10", "mrr@10", "ips", "snips", "dr"),
        required_metadata_fields=("is_high_end",),
    ),
    ChallengeTrack.COLD_START: ChallengeSpec(
        track=ChallengeTrack.COLD_START,
        description="Cold-start recommendation: users/items with < 5 interactions",
        dataset_filter="is_cold_start",
        primary_metric="recall@10",
        secondary_metrics=("ndcg@10", "hit@10", "ips", "snips", "dr"),
        required_metadata_fields=(),
    ),
    ChallengeTrack.EXPERT_AWARE: ChallengeSpec(
        track=ChallengeTrack.EXPERT_AWARE,
        description="Expert-aware: models must use expert signals",
        dataset_filter="has_expert_consensus",
        primary_metric="ndcg@10",
        secondary_metrics=("recall@10", "ips", "snips", "dr"),
        required_metadata_fields=("expert_agreement_pct", "consensus_category"),
    ),
}


# ── Filters ──


def _filter_high_end(samples: list[EvalSample]) -> list[EvalSample]:
    return [s for s in samples if s.metadata.get("is_high_end", False)]


def _filter_cold_start(samples: list[EvalSample], *, threshold: int = 5) -> list[EvalSample]:
    return [s for s in samples if len(s.y_true) < threshold]


def _filter_expert_aware(samples: list[EvalSample]) -> list[EvalSample]:
    return [s for s in samples if s.metadata.get("has_expert_consensus", False)]


_TRACK_FILTERS: dict[ChallengeTrack, Any] = {
    ChallengeTrack.HIGH_END: _filter_high_end,
    ChallengeTrack.COLD_START: _filter_cold_start,
    ChallengeTrack.EXPERT_AWARE: _filter_expert_aware,
}


# ── Evaluation ──


def filter_challenge_samples(
    samples: list[EvalSample],
    track: ChallengeTrack,
) -> list[EvalSample]:
    """Filter samples for a specific challenge track."""
    filter_fn = _TRACK_FILTERS[track]
    return filter_fn(samples)


def evaluate_challenge_track(
    samples: list[EvalSample],
    *,
    track: ChallengeTrack,
    model_name: str,
    model_version: str,
    dataset_version: str,
    k_values: tuple[int, ...] = (5, 10, 20),
) -> LeaderboardEntry:
    """Evaluate a model on a single challenge track.

    Filters samples, runs standard evaluation, returns leaderboard entry.
    """
    spec = CHALLENGE_SPECS[track]
    filtered = filter_challenge_samples(samples, track)

    if not filtered:
        log.warning("challenge_empty_track", track=track.value)
        return LeaderboardEntry(
            track=track,
            model_name=model_name,
            model_version=model_version,
            dataset_version=dataset_version,
            primary_score=0.0,
            all_metrics={"n_users": 0.0},
            submitted_at=datetime.now(UTC).isoformat(),
        )

    result = evaluate_track(
        filtered,
        track_name=track.value,
        model_name=model_name,
        model_version=model_version,
        dataset_version=dataset_version,
        k_values=k_values,
    )

    primary_score = result.metrics.get(spec.primary_metric, 0.0)

    return LeaderboardEntry(
        track=track,
        model_name=model_name,
        model_version=model_version,
        dataset_version=dataset_version,
        primary_score=primary_score,
        all_metrics=result.metrics,
        submitted_at=datetime.now(UTC).isoformat(),
    )


def run_challenge_suite(
    *,
    model_name: str,
    model_version: str,
    dataset_version: str,
    samples: list[EvalSample],
    k_values: tuple[int, ...] = (5, 10, 20),
) -> list[LeaderboardEntry]:
    """Run all challenge tracks and produce leaderboard entries."""
    entries: list[LeaderboardEntry] = []

    for track in ChallengeTrack:
        entry = evaluate_challenge_track(
            samples,
            track=track,
            model_name=model_name,
            model_version=model_version,
            dataset_version=dataset_version,
            k_values=k_values,
        )
        entries.append(entry)

    log.info("challenge_suite_complete", model_name=model_name, n_tracks=len(entries))
    return entries


# ── Leaderboard storage ──


def update_leaderboard(
    *,
    object_store: ObjectStore,
    entry: LeaderboardEntry,
    bucket: str = "leaderboard",
) -> Leaderboard:
    """Add entry to leaderboard, maintain sorted order by primary_score descending."""
    import json  # noqa: PLC0415

    key = f"{entry.track.value}/leaderboard.json"
    existing = get_leaderboard(object_store=object_store, track=entry.track, bucket=bucket)

    entries = [*list(existing.entries), entry]
    entries.sort(key=lambda e: e.primary_score, reverse=True)

    leaderboard = Leaderboard(
        track=entry.track,
        entries=tuple(entries),
        generated_at=datetime.now(UTC).isoformat(),
    )

    # Serialize
    data: dict[str, object] = {
        "track": leaderboard.track.value,
        "generated_at": leaderboard.generated_at,
        "entries": [
            {
                "track": e.track.value,
                "model_name": e.model_name,
                "model_version": e.model_version,
                "dataset_version": e.dataset_version,
                "primary_score": e.primary_score,
                "all_metrics": e.all_metrics,
                "submitted_at": e.submitted_at,
            }
            for e in leaderboard.entries
        ],
    }
    object_store.put_bytes(
        bucket=bucket,
        key=key,
        data=json.dumps(data).encode(),
    )

    log.info("leaderboard_updated", track=entry.track.value, n_entries=len(entries))
    return leaderboard


def get_leaderboard(
    *,
    object_store: ObjectStore,
    track: ChallengeTrack,
    bucket: str = "leaderboard",
) -> Leaderboard:
    """Retrieve current leaderboard for a track."""
    import json  # noqa: PLC0415

    key = f"{track.value}/leaderboard.json"

    try:
        raw = object_store.get_bytes(bucket=bucket, key=key)
    except (KeyError, FileNotFoundError):
        return Leaderboard(track=track, entries=())

    data = json.loads(raw)
    entries = tuple(
        LeaderboardEntry(
            track=ChallengeTrack(e["track"]),
            model_name=e["model_name"],
            model_version=e["model_version"],
            dataset_version=e["dataset_version"],
            primary_score=e["primary_score"],
            all_metrics=e.get("all_metrics", {}),
            submitted_at=e.get("submitted_at", ""),
        )
        for e in data.get("entries", [])
    )

    return Leaderboard(
        track=track,
        entries=entries,
        generated_at=data.get("generated_at", ""),
    )
