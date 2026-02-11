"""Tests for multi-recall recommender."""

from __future__ import annotations

from typing import Any

from wine_rec.serving.recommender import Candidate, RecallSource, Recommender


class _FakeFeatureStore:
    """Test double for FeatureStore protocol."""

    def __init__(self, features: dict[str, dict[str, Any]] | None = None) -> None:
        self._features = features or {}

    def get_features(self, *, entity_type: str, entity_id: str) -> dict[str, Any]:
        return self._features.get(f"{entity_type}:{entity_id}", {})

    def put_features(self, *, entity_type: str, entity_id: str, features: dict[str, Any]) -> None:
        self._features[f"{entity_type}:{entity_id}"] = features

    def batch_get_features(
        self, *, entity_type: str, entity_ids: list[str]
    ) -> list[dict[str, Any]]:
        return [self.get_features(entity_type=entity_type, entity_id=eid) for eid in entity_ids]


class _FakeModelArtifact:
    """Test double for ModelArtifact protocol."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        return {"items": self._items}

    @property
    def version(self) -> str:
        return "v1"


class _FakeModelRegistry:
    """Test double for ModelRegistry protocol."""

    def __init__(self, models: dict[str, _FakeModelArtifact]) -> None:
        self._models = models

    def load_model(self, *, model_name: str, version: str) -> _FakeModelArtifact:
        return self._models[model_name]

    def get_latest_version(self, *, model_name: str) -> str:
        return "v1"


class TestRecommender:
    def test_recommend_basic(self):
        items = [
            {"wine_sku_id": "s1", "score": 0.9},
            {"wine_sku_id": "s2", "score": 0.7},
            {"wine_sku_id": "s3", "score": 0.5},
        ]
        model = _FakeModelArtifact(items)
        registry = _FakeModelRegistry({"bpr_v1": model})
        store = _FakeFeatureStore()

        rec = Recommender(
            feature_store=store,
            model_registry=registry,
            recall_sources=[RecallSource(name="collab", model_name="bpr_v1", quota=10)],
        )
        results = rec.recommend(user_id="u1", n_items=3)

        assert len(results) == 3
        assert results[0]["wine_sku_id"] == "s1"
        assert results[0]["rank"] == 1
        assert results[0]["score"] == 0.9

    def test_empty_recall(self):
        """No models available → empty results."""
        store = _FakeFeatureStore()
        rec = Recommender(feature_store=store, model_registry=None, recall_sources=[])
        results = rec.recommend(user_id="u1", n_items=5)
        assert results == []

    def test_dedup_keeps_highest(self):
        """Duplicate items from different sources should keep highest score."""
        items1 = [{"wine_sku_id": "s1", "score": 0.6}]
        items2 = [{"wine_sku_id": "s1", "score": 0.9}]
        model1 = _FakeModelArtifact(items1)
        model2 = _FakeModelArtifact(items2)
        registry = _FakeModelRegistry({"m1": model1, "m2": model2})
        store = _FakeFeatureStore()

        rec = Recommender(
            feature_store=store,
            model_registry=registry,
            recall_sources=[
                RecallSource(name="a", model_name="m1", quota=10),
                RecallSource(name="b", model_name="m2", quota=10),
            ],
        )
        results = rec.recommend(user_id="u1", n_items=5)

        assert len(results) == 1
        assert results[0]["score"] == 0.9

    def test_n_items_respected(self):
        items = [{"wine_sku_id": f"s{i}", "score": 1.0 - i * 0.1} for i in range(20)]
        model = _FakeModelArtifact(items)
        registry = _FakeModelRegistry({"bpr_v1": model})
        store = _FakeFeatureStore()

        rec = Recommender(
            feature_store=store,
            model_registry=registry,
            recall_sources=[RecallSource(name="collab", model_name="bpr_v1", quota=50)],
        )
        results = rec.recommend(user_id="u1", n_items=5)
        assert len(results) == 5

    def test_rank_ordering(self):
        """Results should be in descending score order."""
        items = [
            {"wine_sku_id": "s1", "score": 0.3},
            {"wine_sku_id": "s2", "score": 0.9},
            {"wine_sku_id": "s3", "score": 0.6},
        ]
        model = _FakeModelArtifact(items)
        registry = _FakeModelRegistry({"bpr_v1": model})
        store = _FakeFeatureStore()

        rec = Recommender(
            feature_store=store,
            model_registry=registry,
            recall_sources=[RecallSource(name="collab", model_name="bpr_v1", quota=10)],
        )
        results = rec.recommend(user_id="u1", n_items=3)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestMergeDedup:
    def test_keeps_unique(self):
        candidates = [
            Candidate(wine_sku_id="s1", score=0.5, recall_source="a"),
            Candidate(wine_sku_id="s2", score=0.3, recall_source="b"),
        ]
        result = Recommender._merge_dedup(candidates)
        assert len(result) == 2

    def test_dedup_higher_wins(self):
        candidates = [
            Candidate(wine_sku_id="s1", score=0.5, recall_source="a"),
            Candidate(wine_sku_id="s1", score=0.8, recall_source="b"),
        ]
        result = Recommender._merge_dedup(candidates)
        assert len(result) == 1
        assert result[0].score == 0.8


class TestPostRank:
    def test_diversity_reranking(self):
        """Post-rank should mix sources for diversity."""
        store = _FakeFeatureStore()
        rec = Recommender(feature_store=store, diversity_weight=10.0)

        candidates = [
            Candidate(wine_sku_id=f"s{i}", score=1.0 - i * 0.01, recall_source="a")
            for i in range(5)
        ] + [
            Candidate(wine_sku_id=f"t{i}", score=0.8 - i * 0.01, recall_source="b")
            for i in range(5)
        ]

        result = rec._post_rank(candidates, n_items=4, _context={})
        sources = [c.recall_source for c in result]
        # with high diversity weight, should mix sources
        assert "a" in sources
        assert "b" in sources
