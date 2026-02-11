"""Tests for evaluation metrics."""

import numpy as np

from wine_rec.models.evaluation.metrics import (
    catalog_coverage,
    hit_at_k,
    intra_list_diversity,
    map_at_k,
    mrr,
    ndcg_at_k,
    recall_at_k,
)


class TestRecallAtK:
    def test_perfect_recall(self):
        y_true = np.array([1, 1, 0, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.1, 0.2, 0.3])
        assert recall_at_k(y_true=y_true, y_pred=y_pred, k=2) == 1.0

    def test_zero_recall(self):
        y_true = np.array([0, 0, 1, 1, 0])
        y_pred = np.array([0.9, 0.8, 0.1, 0.2, 0.3])
        assert recall_at_k(y_true=y_true, y_pred=y_pred, k=2) == 0.0

    def test_no_relevant_items(self):
        y_true = np.array([0, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.7])
        assert recall_at_k(y_true=y_true, y_pred=y_pred, k=2) == 0.0

    def test_partial_recall(self):
        y_true = np.array([1, 0, 1, 0])
        y_pred = np.array([0.9, 0.8, 0.1, 0.2])
        assert recall_at_k(y_true=y_true, y_pred=y_pred, k=2) == 0.5


class TestNDCGAtK:
    def test_perfect_ndcg(self):
        y_true = np.array([1, 1, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.1, 0.2])
        assert ndcg_at_k(y_true=y_true, y_pred=y_pred, k=2) == 1.0

    def test_no_relevant_items(self):
        y_true = np.array([0, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.7])
        assert ndcg_at_k(y_true=y_true, y_pred=y_pred, k=2) == 0.0


class TestHitAtK:
    def test_hit(self):
        y_true = np.array([1, 0, 0, 0])
        y_pred = np.array([0.9, 0.1, 0.2, 0.3])
        assert hit_at_k(y_true=y_true, y_pred=y_pred, k=1) == 1.0

    def test_miss(self):
        y_true = np.array([0, 0, 0, 1])
        y_pred = np.array([0.9, 0.8, 0.7, 0.1])
        assert hit_at_k(y_true=y_true, y_pred=y_pred, k=2) == 0.0


class TestMAPAtK:
    def test_perfect_map(self):
        y_true = np.array([1, 1, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.1, 0.2])
        # both relevant at positions 1 and 2
        # P@1 = 1/1 * 1 = 1.0, P@2 = 2/2 * 1 = 1.0
        # MAP = (1.0 + 1.0) / min(2, 2) = 1.0
        assert map_at_k(y_true=y_true, y_pred=y_pred, k=2) == 1.0

    def test_no_relevant(self):
        y_true = np.array([0, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.7])
        assert map_at_k(y_true=y_true, y_pred=y_pred, k=3) == 0.0

    def test_partial_map(self):
        y_true = np.array([1, 0, 1, 0])
        y_pred = np.array([0.9, 0.8, 0.7, 0.1])
        # top-3: idx 0 (rel=1), idx 1 (rel=0), idx 2 (rel=1)
        # P@1 = 1/1 * 1 = 1.0, P@2 = 1/2 * 0 = 0, P@3 = 2/3 * 1 = 0.667
        # MAP@3 = (1.0 + 0.667) / min(2, 3) = 1.667 / 2 ≈ 0.8333
        result = map_at_k(y_true=y_true, y_pred=y_pred, k=3)
        assert abs(result - 0.8333) < 0.01


class TestMRR:
    def test_first_item_relevant(self):
        y_true = np.array([1, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.7])
        assert mrr(y_true=y_true, y_pred=y_pred) == 1.0

    def test_second_item_relevant(self):
        y_true = np.array([0, 1, 0])
        y_pred = np.array([0.9, 0.8, 0.7])
        # top item (idx 0) is irrelevant, second (idx 1) is relevant → RR = 1/2
        assert mrr(y_true=y_true, y_pred=y_pred) == 0.5

    def test_no_relevant(self):
        y_true = np.array([0, 0, 0])
        y_pred = np.array([0.9, 0.8, 0.7])
        assert mrr(y_true=y_true, y_pred=y_pred) == 0.0


class TestCatalogCoverage:
    def test_full_coverage(self):
        result = catalog_coverage(
            recommended_items={"a", "b", "c"},
            catalog_items={"a", "b", "c"},
        )
        assert result == 1.0

    def test_partial_coverage(self):
        result = catalog_coverage(
            recommended_items={"a", "b"},
            catalog_items={"a", "b", "c", "d"},
        )
        assert result == 0.5

    def test_empty_catalog(self):
        result = catalog_coverage(
            recommended_items={"a"},
            catalog_items=set(),
        )
        assert result == 0.0

    def test_no_overlap(self):
        result = catalog_coverage(
            recommended_items={"x", "y"},
            catalog_items={"a", "b"},
        )
        assert result == 0.0


class TestIntraListDiversity:
    def test_identical_items_zero_diversity(self):
        # all same embedding → cosine sim = 1.0 → diversity = 0.0
        emb = np.array([[1.0, 0.0, 0.0]] * 3)
        assert intra_list_diversity(embeddings=emb) == 0.0

    def test_orthogonal_items_high_diversity(self):
        # orthogonal embeddings → cosine sim = 0.0 → diversity = 1.0
        emb = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        assert intra_list_diversity(embeddings=emb) == 1.0

    def test_single_item_zero(self):
        emb = np.array([[1.0, 2.0, 3.0]])
        assert intra_list_diversity(embeddings=emb) == 0.0

    def test_returns_between_zero_and_one(self):
        rng = np.random.default_rng(42)
        emb = rng.random((5, 10))
        result = intra_list_diversity(embeddings=emb)
        assert 0.0 <= result <= 1.0
