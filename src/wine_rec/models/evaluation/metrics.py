"""Evaluation metrics (RFC-DATASET-BENCH-005 §5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np


if TYPE_CHECKING:
    from numpy.typing import NDArray


def recall_at_k(*, y_true: NDArray[np.int_], y_pred: NDArray[np.float64], k: int) -> float:
    """Recall@K — fraction of relevant items in top-K."""
    top_k_idx = np.argsort(y_pred)[::-1][:k]
    hits = np.sum(y_true[top_k_idx])
    total_relevant = np.sum(y_true)
    if total_relevant == 0:
        return 0.0
    return float(hits / total_relevant)


def ndcg_at_k(*, y_true: NDArray[np.int_], y_pred: NDArray[np.float64], k: int) -> float:
    """NDCG@K — normalized discounted cumulative gain."""
    top_k_idx = np.argsort(y_pred)[::-1][:k]
    actual_k = len(top_k_idx)
    discounts = np.log2(np.arange(2, actual_k + 2))
    dcg = np.sum(y_true[top_k_idx] / discounts)
    ideal_idx = np.argsort(y_true)[::-1][:k]
    ideal_k = len(ideal_idx)
    idiscounts = np.log2(np.arange(2, ideal_k + 2))
    idcg = np.sum(y_true[ideal_idx] / idiscounts)
    if idcg == 0:
        return 0.0
    return float(dcg / idcg)


def hit_at_k(*, y_true: NDArray[np.int_], y_pred: NDArray[np.float64], k: int) -> float:
    """Hit@K — 1 if any relevant item in top-K, else 0."""
    top_k_idx = np.argsort(y_pred)[::-1][:k]
    return float(np.any(y_true[top_k_idx] > 0))


def map_at_k(*, y_true: NDArray[np.int_], y_pred: NDArray[np.float64], k: int) -> float:
    """MAP@K — mean average precision at K.

    For a single query: average of Precision@i for each relevant item i in top-K.
    """
    top_k_idx = np.argsort(y_pred)[::-1][:k]
    relevance = y_true[top_k_idx]

    total_relevant = np.sum(y_true)
    if total_relevant == 0:
        return 0.0

    actual_k = len(relevance)
    cum_relevant = np.cumsum(relevance)
    precision_at_i = cum_relevant / np.arange(1, actual_k + 1)
    return float(np.sum(precision_at_i * relevance) / min(total_relevant, k))


def mrr(*, y_true: NDArray[np.int_], y_pred: NDArray[np.float64]) -> float:
    """MRR — mean reciprocal rank (reciprocal of first relevant item's rank)."""
    ranked_idx = np.argsort(y_pred)[::-1]
    relevance = y_true[ranked_idx]
    relevant_positions = np.where(relevance > 0)[0]
    if len(relevant_positions) == 0:
        return 0.0
    return float(1.0 / (relevant_positions[0] + 1))


def catalog_coverage(*, recommended_items: set[str], catalog_items: set[str]) -> float:
    """Catalog coverage — fraction of catalog items ever recommended."""
    if len(catalog_items) == 0:
        return 0.0
    return len(recommended_items & catalog_items) / len(catalog_items)


def intra_list_diversity(*, embeddings: NDArray[np.float64]) -> float:
    """Intra-list diversity — average pairwise distance among recommended items.

    Args:
        embeddings: (K, D) array of item embeddings for a recommendation list.

    Returns:
        Average cosine distance (1 - cosine_similarity) between all pairs.
    """
    k = len(embeddings)
    if k < 2:
        return 0.0

    # normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-8, None)
    normed = embeddings / norms

    sim_matrix = normed @ normed.T
    # extract upper triangle (excluding diagonal)
    n_pairs = k * (k - 1) / 2
    upper_sum = float((np.sum(sim_matrix) - np.trace(sim_matrix)) / 2)
    avg_similarity = upper_sum / n_pairs
    return float(1.0 - avg_similarity)
