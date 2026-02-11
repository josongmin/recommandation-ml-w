"""Business metrics tracking for recommendation systems.

Industry SOTA metrics from Meta/Netflix/Spotify:
- Engagement: CTR, session time, items per session
- Revenue: GMV, AOV, conversion rate
- Retention: DAU, WAU, MAU, churn rate
- Quality: diversity, novelty, serendipity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from wine_rec.common.logging import get_logger


log = get_logger(__name__)


class MetricType(StrEnum):
    """Business metric categories."""

    ENGAGEMENT = "engagement"
    REVENUE = "revenue"
    RETENTION = "retention"
    QUALITY = "quality"


@dataclass
class MetricSnapshot:
    """Single metric observation at a point in time."""

    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    dimensions: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SessionMetrics:
    """User session-level metrics."""

    session_id: str
    user_id: str
    n_recommendations_shown: int = 0
    n_recommendations_clicked: int = 0
    n_items_purchased: int = 0
    total_revenue: float = 0.0
    session_duration_sec: float = 0.0
    items_viewed: list[str] = field(default_factory=list)
    items_clicked: list[str] = field(default_factory=list)
    items_purchased: list[str] = field(default_factory=list)

    @property
    def ctr(self) -> float:
        """Click-through rate."""
        if self.n_recommendations_shown == 0:
            return 0.0
        return self.n_recommendations_clicked / self.n_recommendations_shown

    @property
    def conversion_rate(self) -> float:
        """Purchase conversion rate."""
        if self.n_recommendations_shown == 0:
            return 0.0
        return self.n_items_purchased / self.n_recommendations_shown

    @property
    def aov(self) -> float:
        """Average order value."""
        if self.n_items_purchased == 0:
            return 0.0
        return self.total_revenue / self.n_items_purchased

    @property
    def items_per_session(self) -> float:
        """Average items viewed per session."""
        return float(len(self.items_viewed))


class BusinessMetricsTracker:
    """Real-time business metrics aggregator.

    Production usage:
    1. Track session-level events (shown, clicked, purchased)
    2. Aggregate to daily/hourly metrics
    3. Export to CloudWatch/Grafana/Datadog
    4. Alert on anomalies (sudden CTR drop, revenue dip)
    """

    def __init__(self) -> None:
        """Initialize metrics tracker."""
        self._sessions: dict[str, SessionMetrics] = {}
        self._snapshots: list[MetricSnapshot] = []

        log.info("business_metrics_tracker_init")

    def start_session(self, *, session_id: str, user_id: str) -> None:
        """Start tracking a new user session."""
        self._sessions[session_id] = SessionMetrics(session_id=session_id, user_id=user_id)
        log.debug("session_started", session_id=session_id, user_id=user_id)

    def record_recommendation_shown(
        self,
        *,
        session_id: str,
        item_ids: list[str],
    ) -> None:
        """Record recommendation impressions."""
        if session_id not in self._sessions:
            log.warning("session_not_found", session_id=session_id)
            return

        session = self._sessions[session_id]
        session.n_recommendations_shown += len(item_ids)

    def record_click(self, *, session_id: str, item_id: str) -> None:
        """Record item click."""
        if session_id not in self._sessions:
            log.warning("session_not_found", session_id=session_id)
            return

        session = self._sessions[session_id]
        session.n_recommendations_clicked += 1
        session.items_clicked.append(item_id)

        if item_id not in session.items_viewed:
            session.items_viewed.append(item_id)

    def record_purchase(
        self,
        *,
        session_id: str,
        item_id: str,
        price: float,
    ) -> None:
        """Record item purchase."""
        if session_id not in self._sessions:
            log.warning("session_not_found", session_id=session_id)
            return

        session = self._sessions[session_id]
        session.n_items_purchased += 1
        session.total_revenue += price
        session.items_purchased.append(item_id)

    def end_session(self, *, session_id: str, duration_sec: float) -> SessionMetrics:
        """End session and compute final metrics."""
        if session_id not in self._sessions:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)

        session = self._sessions[session_id]
        session.session_duration_sec = duration_sec

        # Record session-level snapshots
        now = datetime.now()
        self._record_snapshot(
            metric_name="ctr",
            metric_type=MetricType.ENGAGEMENT,
            value=session.ctr,
            timestamp=now,
            dimensions={"session_id": session_id, "user_id": session.user_id},
        )
        self._record_snapshot(
            metric_name="conversion_rate",
            metric_type=MetricType.REVENUE,
            value=session.conversion_rate,
            timestamp=now,
            dimensions={"session_id": session_id, "user_id": session.user_id},
        )
        self._record_snapshot(
            metric_name="aov",
            metric_type=MetricType.REVENUE,
            value=session.aov,
            timestamp=now,
            dimensions={"session_id": session_id, "user_id": session.user_id},
        )
        self._record_snapshot(
            metric_name="session_duration_sec",
            metric_type=MetricType.ENGAGEMENT,
            value=session.session_duration_sec,
            timestamp=now,
            dimensions={"session_id": session_id, "user_id": session.user_id},
        )

        log.info(
            "session_ended",
            session_id=session_id,
            ctr=session.ctr,
            conversion_rate=session.conversion_rate,
            revenue=session.total_revenue,
        )

        return session

    def _record_snapshot(
        self,
        *,
        metric_name: str,
        metric_type: MetricType,
        value: float,
        timestamp: datetime,
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """Record a metric snapshot."""
        snapshot = MetricSnapshot(
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            timestamp=timestamp,
            dimensions=dimensions or {},
        )
        self._snapshots.append(snapshot)

    def get_snapshots(
        self,
        *,
        metric_type: MetricType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[MetricSnapshot]:
        """Get filtered metric snapshots."""
        snapshots = self._snapshots

        if metric_type is not None:
            snapshots = [s for s in snapshots if s.metric_type == metric_type]

        if start_time is not None:
            snapshots = [s for s in snapshots if s.timestamp >= start_time]

        if end_time is not None:
            snapshots = [s for s in snapshots if s.timestamp <= end_time]

        return snapshots

    def compute_aggregates(
        self,
        *,
        metric_type: MetricType | None = None,
    ) -> dict[str, float]:
        """Compute aggregate statistics across all sessions.

        Returns:
            {metric_name: mean_value} for each metric
        """
        snapshots = self.get_snapshots(metric_type=metric_type)

        # Group by metric name
        by_metric: dict[str, list[float]] = {}
        for snapshot in snapshots:
            if snapshot.metric_name not in by_metric:
                by_metric[snapshot.metric_name] = []
            by_metric[snapshot.metric_name].append(snapshot.value)

        # Compute means
        aggregates: dict[str, float] = {}
        for metric_name, values in by_metric.items():
            if values:
                aggregates[f"{metric_name}_mean"] = sum(values) / len(values)
                aggregates[f"{metric_name}_count"] = float(len(values))
            else:
                aggregates[f"{metric_name}_mean"] = 0.0
                aggregates[f"{metric_name}_count"] = 0.0

        return aggregates


@dataclass
class DiversityMetrics:
    """Recommendation diversity and novelty metrics.

    Industry SOTA (Spotify/Netflix):
    - Intra-list diversity: avg pairwise distance within a recommendation list
    - Coverage: fraction of catalog items ever recommended
    - Novelty: avg popularity rank of recommended items (higher = more novel)
    - Serendipity: recommendations outside user's historical genres
    """

    intra_list_diversity: float
    catalog_coverage: float
    novelty_score: float
    serendipity_score: float


def compute_diversity_metrics(
    *,
    recommended_items: list[str],
    all_catalog_items: set[str],
    item_popularity: dict[str, int],
    user_historical_genres: set[str],
    item_genres: dict[str, set[str]],
    item_embeddings: dict[str, list[float]] | None = None,
) -> DiversityMetrics:
    """Compute diversity and novelty metrics for recommendations.

    Args:
        recommended_items: List of recommended item IDs
        all_catalog_items: Full catalog of available items
        item_popularity: {item_id: view_count} for popularity ranking
        user_historical_genres: Genres user has interacted with
        item_genres: {item_id: {genre1, genre2}} mapping
        item_embeddings: Optional {item_id: embedding_vector} for ILS computation

    Returns:
        DiversityMetrics with ILS, coverage, novelty, serendipity
    """
    # Intra-list diversity (compute with embeddings if available)
    if item_embeddings is not None and recommended_items:
        import numpy as np

        from wine_rec.models.evaluation.metrics import intra_list_diversity as compute_ils

        # Get embeddings for recommended items
        embeddings_list = []
        for item_id in recommended_items:
            if item_id in item_embeddings:
                embeddings_list.append(item_embeddings[item_id])

        if embeddings_list:
            embeddings_array = np.array(embeddings_list, dtype=np.float64)
            intra_list_diversity = float(compute_ils(embeddings=embeddings_array))
        else:
            intra_list_diversity = 0.5  # Fallback if embeddings missing
    else:
        intra_list_diversity = 0.5  # Fallback if no embeddings provided

    # Catalog coverage
    recommended_set = set(recommended_items)
    catalog_coverage = len(recommended_set & all_catalog_items) / len(all_catalog_items)

    # Novelty (avg popularity rank, normalized 0-1)
    sorted_items = sorted(item_popularity.items(), key=lambda x: x[1], reverse=True)
    rank_map = {item_id: rank for rank, (item_id, _) in enumerate(sorted_items, 1)}
    novelty_scores = [
        rank_map.get(item_id, len(sorted_items)) / len(sorted_items)
        for item_id in recommended_items
    ]
    novelty_score = sum(novelty_scores) / len(novelty_scores) if novelty_scores else 0.0

    # Serendipity (fraction of recommendations outside user's genres)
    serendipitous = 0
    for item_id in recommended_items:
        item_genres_set = item_genres.get(item_id, set())
        if not item_genres_set & user_historical_genres:
            serendipitous += 1
    serendipity_score = serendipitous / len(recommended_items) if recommended_items else 0.0

    return DiversityMetrics(
        intra_list_diversity=intra_list_diversity,
        catalog_coverage=catalog_coverage,
        novelty_score=novelty_score,
        serendipity_score=serendipity_score,
    )
