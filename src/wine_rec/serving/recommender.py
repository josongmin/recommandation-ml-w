"""Multi-recall + 2-stage ranking recommender (RFC-E2E-PIPELINE-006 §1-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from wine_rec.common.logging import get_logger


if TYPE_CHECKING:
    from wine_rec.contracts.feature_store import FeatureStore
    from wine_rec.contracts.model_registry import ModelArtifact, ModelRegistry

log = get_logger(__name__)


@dataclass
class RecallSource:
    """Configuration for a single recall source."""

    name: str
    model_name: str
    quota: int = 50


@dataclass
class Candidate:
    """Internal candidate representation during ranking."""

    wine_sku_id: str
    score: float = 0.0
    recall_source: str = ""
    features: dict[str, Any] = field(default_factory=dict)


DEFAULT_RECALL_SOURCES = [
    RecallSource(name="collaborative", model_name="bpr_v1", quota=50),
    RecallSource(name="content", model_name="two_tower_v1", quota=50),
    RecallSource(name="graph", model_name="lightgcn_v1", quota=30),
    RecallSource(name="popular", model_name="popularity", quota=20),
]


class Recommender:
    """Main recommendation orchestrator.

    Multi-Recall -> Light Rank -> Heavy Rank -> Post-rank.
    """

    def __init__(
        self,
        *,
        feature_store: FeatureStore,
        model_registry: ModelRegistry | None = None,
        recall_sources: list[RecallSource] | None = None,
        heavy_ranker_name: str = "deepfm_v1",
        diversity_weight: float = 0.1,
    ) -> None:
        self._feature_store = feature_store
        self._model_registry = model_registry
        self._recall_sources = recall_sources or DEFAULT_RECALL_SOURCES
        self._heavy_ranker_name = heavy_ranker_name
        self._diversity_weight = diversity_weight

        self._models: dict[str, ModelArtifact] = {}

    def recommend(
        self,
        *,
        user_id: str,
        n_items: int = 10,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate recommendations.

        Steps:
            1. Fetch user features from feature store
            2. Multi-recall: collaborative + content + graph + popular
            3. Merge & deduplicate candidates
            4. Light rank (fast scoring)
            5. Heavy rank (DeepFM)
            6. Post-rank (diversity, constraints)

        Returns:
            List of recommendation dicts with wine_sku_id, score, rank,
            and recall_source fields.
        """
        ctx = context or {}

        user_features = self._fetch_user_features(user_id)

        candidates = self._multi_recall(user_id, user_features, ctx)
        if not candidates:
            log.warning("recommend_no_candidates", user_id=user_id)
            return []

        candidates = self._merge_dedup(candidates)
        candidates = self._light_rank(candidates, user_features)
        candidates = self._heavy_rank(candidates, user_features, ctx)
        candidates = self._post_rank(candidates, n_items, ctx)

        results: list[dict[str, Any]] = []
        for rank, cand in enumerate(candidates[:n_items], 1):
            results.append(
                {
                    "wine_sku_id": cand.wine_sku_id,
                    "score": round(cand.score, 6),
                    "rank": rank,
                    "recall_source": cand.recall_source,
                }
            )

        log.info(
            "recommend_complete",
            user_id=user_id,
            n_candidates=len(candidates),
            n_returned=len(results),
        )
        return results

    def _fetch_user_features(self, user_id: str) -> dict[str, Any]:
        """Fetch user features from the feature store."""
        try:
            return self._feature_store.get_features(entity_type="user", entity_id=user_id)
        except Exception:
            log.warning("user_features_missing", user_id=user_id)
            return {}

    def _get_model(self, model_name: str) -> ModelArtifact | None:
        """Load and cache a model from the registry."""
        if model_name in self._models:
            return self._models[model_name]

        if self._model_registry is None:
            return None

        try:
            version = self._model_registry.get_latest_version(model_name=model_name)
            model = self._model_registry.load_model(model_name=model_name, version=version)
            self._models[model_name] = model
            return model
        except Exception:
            log.warning("model_load_failed", model_name=model_name)
            return None

    def _multi_recall(
        self,
        user_id: str,
        user_features: dict[str, Any],
        context: dict[str, Any],
    ) -> list[Candidate]:
        """Generate candidates from multiple recall sources."""
        all_candidates: list[Candidate] = []

        for source in self._recall_sources:
            model = self._get_model(source.model_name)
            if model is None:
                continue

            try:
                result = model.predict({"user_id": user_id, **user_features, **context})
                items = result.get("items", [])

                for item in items[: source.quota]:
                    item_id = item if isinstance(item, str) else str(item.get("wine_sku_id", ""))
                    item_score = float(item.get("score", 0.0)) if isinstance(item, dict) else 0.0

                    if item_id:
                        all_candidates.append(
                            Candidate(
                                wine_sku_id=item_id,
                                score=item_score,
                                recall_source=source.name,
                            )
                        )
            except Exception:
                log.warning("recall_source_failed", source=source.name)

        if not all_candidates:
            all_candidates = self._popularity_fallback()

        return all_candidates

    def _popularity_fallback(self) -> list[Candidate]:
        """Return popular items as a last-resort fallback."""
        try:
            popular = self._feature_store.batch_get_features(
                entity_type="popular_items", entity_ids=["global"]
            )
            if popular and "items" in popular[0]:
                return [
                    Candidate(wine_sku_id=str(item_id), score=0.0, recall_source="popular_fallback")
                    for item_id in popular[0]["items"][:20]
                ]
        except Exception:
            log.warning("popularity_fallback_failed")
        return []

    @staticmethod
    def _merge_dedup(candidates: list[Candidate]) -> list[Candidate]:
        """Merge and deduplicate candidates, keeping highest score per item."""
        best: dict[str, Candidate] = {}
        for cand in candidates:
            existing = best.get(cand.wine_sku_id)
            if existing is None or cand.score > existing.score:
                best[cand.wine_sku_id] = cand
        return list(best.values())

    @staticmethod
    def _light_rank(
        candidates: list[Candidate],
        _user_features: dict[str, Any],
    ) -> list[Candidate]:
        """Fast scoring pass: sort by initial recall score, keep top 50."""
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:50]

    def _heavy_rank(
        self,
        candidates: list[Candidate],
        user_features: dict[str, Any],
        context: dict[str, Any],
    ) -> list[Candidate]:
        """Feature-aware re-ranking using DeepFM.

        Fetches item features and scores each candidate with the heavy ranker.
        """
        ranker = self._get_model(self._heavy_ranker_name)
        if ranker is None:
            return candidates

        item_ids = [c.wine_sku_id for c in candidates]
        try:
            item_features_list = self._feature_store.batch_get_features(
                entity_type="wine_sku", entity_ids=item_ids
            )
        except Exception:
            log.warning("item_features_fetch_failed")
            return candidates

        for i, cand in enumerate(candidates):
            item_features = item_features_list[i] if i < len(item_features_list) else {}
            combined = {**user_features, **item_features, **context}
            try:
                result = ranker.predict(combined)
                cand.score = float(result.get("score", cand.score))
            except Exception:
                log.debug("heavy_rank_score_failed", item=cand.wine_sku_id)

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _post_rank(
        self,
        candidates: list[Candidate],
        n_items: int,
        _context: dict[str, Any],
    ) -> list[Candidate]:
        """Apply diversity via MMR-style re-ranking.

        Balances relevance with source diversity to avoid mono-source lists.
        """
        if len(candidates) <= n_items or self._diversity_weight <= 0:
            return candidates[:n_items]

        selected: list[Candidate] = []
        remaining = list(candidates)
        seen_sources: dict[str, int] = {}

        while len(selected) < n_items and remaining:
            best_idx = 0
            best_score = -float("inf")

            for i, cand in enumerate(remaining):
                relevance = cand.score
                source_count = seen_sources.get(cand.recall_source, 0)
                diversity_bonus = 1.0 / (1.0 + source_count)
                combined = relevance + self._diversity_weight * diversity_bonus

                if combined > best_score:
                    best_score = combined
                    best_idx = i

            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            seen_sources[chosen.recall_source] = seen_sources.get(chosen.recall_source, 0) + 1

        return selected
