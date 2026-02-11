"""Online feature materializer (RFC-FEATURE-MANIFEST-010 §3).

Lambda → DynamoDB real-time feature updates.
Dispatches on event_type, merge-on-write so partial events
do not erase existing features.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from wine_rec.common.logging import get_logger


if TYPE_CHECKING:
    from wine_rec.contracts.feature_store import FeatureStore

log = get_logger(__name__)

# Fields each handler may extract from the event payload.
_WINE_CORE_FIELDS = frozenset(
    {
        "item_core_variety",
        "item_core_region",
        "item_core_producer",
        "canonical_name",
        "wine_type",
        "country",
    }
)

_STRUCT_FIELDS = frozenset(
    {
        "item_core_temporal_stage",
        "item_core_peak_proximity",
        "item_core_weighted_rating_mean",
        "item_core_critic_consensus",
    }
)

_PRICE_FIELDS = frozenset(
    {
        "item_sku_median_price",
        "item_sku_in_stock",
        "item_sku_rarity_score",
    }
)

# Phase H: Expert-aware v2 fields
_EXPERT_AWARE_FIELDS = frozenset(
    {
        "item_core_decay_weighted_rating_mean",
        "item_core_authority_decay_score",
        "item_core_consensus_category",
        "item_core_expert_agreement_pct",
        "item_core_inter_expert_variance",
        "item_core_intra_expert_variance",
    }
)

# Phase H: Temporal v2 fields
_TEMPORAL_V2_FIELDS = frozenset(
    {
        "item_core_days_to_peak",
        "item_core_peak_trajectory",
        "item_core_merged_confidence",
        "item_core_vintage_effect",
    }
)


class OnlineMaterializer:
    """Materialize features from events into online store.

    Supports seven event types:
    - WineCoreUpdated
    - TextUnitAdded
    - StructUnitAdded
    - PriceSnapshotAdded
    - EmbeddingEncoderRolled
    - ExpertAggregateUpdated  (Phase H)
    - TemporalV2Updated       (Phase H)
    """

    def __init__(self, *, feature_store: FeatureStore) -> None:
        self._store = feature_store

    def process_event(
        self,
        *,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Update online features from a new event.

        Dispatches on ``event["event_type"]``.  Unknown event types are
        logged as warnings and silently ignored.
        """
        event_type = event.get("event_type", "")

        if event_type == "WineCoreUpdated":
            self._handle_wine_core_updated(entity_type, entity_id, event)
        elif event_type == "TextUnitAdded":
            self._handle_text_unit_added(entity_type, entity_id, event)
        elif event_type == "StructUnitAdded":
            self._handle_struct_unit_added(entity_type, entity_id, event)
        elif event_type == "PriceSnapshotAdded":
            self._handle_price_snapshot_added(entity_type, entity_id, event)
        elif event_type == "EmbeddingEncoderRolled":
            self._handle_embedding_encoder_rolled(entity_type, entity_id, event)
        elif event_type == "ExpertAggregateUpdated":
            self._handle_expert_aggregate_updated(entity_type, entity_id, event)
        elif event_type == "TemporalV2Updated":
            self._handle_temporal_v2_updated(entity_type, entity_id, event)
        else:
            log.warning(
                "unknown_event_type",
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
            )

    # ------------------------------------------------------------------
    # Handlers (merge-on-write: get → overlay → put)
    # ------------------------------------------------------------------

    def _handle_wine_core_updated(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Upsert wine_core fields: variety, region, producer, etc."""
        updated = self._merge(entity_type, entity_id, event, _WINE_CORE_FIELDS)
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("wine_core_updated", entity_id=entity_id)

    def _handle_text_unit_added(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Update text embedding feature."""
        existing = self._store.get_features(
            entity_type=entity_type,
            entity_id=entity_id,
        )
        updated = {**existing}
        if "text_embedding" in event:
            updated["item_core_text_embedding"] = event["text_embedding"]
        if "embedding_version" in event:
            updated["_text_embedding_version"] = event["embedding_version"]
        updated["_updated_at"] = _now_iso()
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("text_unit_added", entity_id=entity_id)

    def _handle_struct_unit_added(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Update structured IR features (temporal stage, consensus, etc.)."""
        updated = self._merge(entity_type, entity_id, event, _STRUCT_FIELDS)
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("struct_unit_added", entity_id=entity_id)

    def _handle_price_snapshot_added(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Update price/stock features for wine_sku."""
        updated = self._merge(entity_type, entity_id, event, _PRICE_FIELDS)
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("price_snapshot_added", entity_id=entity_id)

    def _handle_embedding_encoder_rolled(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Handle encoder version rollover — update cached embeddings."""
        existing = self._store.get_features(
            entity_type=entity_type,
            entity_id=entity_id,
        )
        updated = {**existing}
        if "new_embedding" in event:
            updated["item_core_text_embedding"] = event["new_embedding"]
        updated["_embedding_encoder_version"] = event.get("encoder_version", "unknown")
        updated["_updated_at"] = _now_iso()
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("embedding_encoder_rolled", entity_id=entity_id)

    # ------------------------------------------------------------------
    # Phase H: v2 handlers
    # ------------------------------------------------------------------

    def _handle_expert_aggregate_updated(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Update expert-aware v2 features (decay-weighted, consensus, etc.)."""
        updated = self._merge(entity_type, entity_id, event, _EXPERT_AWARE_FIELDS)
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("expert_aggregate_updated", entity_id=entity_id)

    def _handle_temporal_v2_updated(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
    ) -> None:
        """Update temporal v2 features (trajectory, days-to-peak, etc.)."""
        updated = self._merge(entity_type, entity_id, event, _TEMPORAL_V2_FIELDS)
        self._store.put_features(
            entity_type=entity_type,
            entity_id=entity_id,
            features=updated,
        )
        log.info("temporal_v2_updated", entity_id=entity_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge(
        self,
        entity_type: str,
        entity_id: str,
        event: dict[str, Any],
        allowed_fields: frozenset[str],
    ) -> dict[str, Any]:
        """Get existing features, overlay matching event fields, stamp _updated_at."""
        existing = self._store.get_features(
            entity_type=entity_type,
            entity_id=entity_id,
        )
        updated: dict[str, Any] = {**existing}
        for field in allowed_fields:
            if field in event:
                updated[field] = event[field]
        updated["_updated_at"] = _now_iso()
        return updated


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
