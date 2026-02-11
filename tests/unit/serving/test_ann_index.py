"""Tests for ANN index module.

NOTE: FAISS tests may fail on Python 3.13+ due to segfault issues.
Production should use Python 3.11 with faiss-cpu/faiss-gpu.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

from wine_rec.serving.ann_index import ANNBackend, ANNIndex


if TYPE_CHECKING:
    from numpy.typing import NDArray


pytestmark = pytest.mark.skip(reason="FAISS segfault on Python 3.13, requires Python 3.11")


@pytest.fixture
def sample_embeddings() -> dict[str, NDArray[np.float32]]:
    """Generate 100 sample item embeddings (128-dim, normalized)."""
    np.random.seed(42)
    embeddings = {}
    for i in range(100):
        vec = np.random.randn(128).astype(np.float32)
        vec = vec / np.linalg.norm(vec)  # L2 normalize for cosine similarity
        embeddings[f"item_{i}"] = vec
    return embeddings


def test_ann_index_init() -> None:
    """Test ANN index initialization."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    assert index._backend == ANNBackend.FAISS
    assert index._embedding_dim == 128
    assert index._index is None


def test_faiss_flat_index_build_search(sample_embeddings: dict[str, NDArray[np.float32]]) -> None:
    """Test FAISS Flat index (exact search baseline)."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    index.build(item_embeddings=sample_embeddings, index_type="Flat")

    # Search with first item's embedding (should return itself as top-1)
    query = sample_embeddings["item_0"]
    result = index.search(query_embedding=query, k=10)

    assert len(result.item_ids) == 10
    assert result.item_ids[0] == "item_0"  # Top-1 should be itself
    assert result.scores[0] > 0.99  # Cosine similarity ~1.0
    assert result.latency_ms > 0


def test_faiss_ivf_index_build_search(sample_embeddings: dict[str, NDArray[np.float32]]) -> None:
    """Test FAISS IVF index (production config)."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    index.build(item_embeddings=sample_embeddings, index_type="IVF10,Flat", nprobe=5)

    query = sample_embeddings["item_0"]
    result = index.search(query_embedding=query, k=10)

    assert len(result.item_ids) == 10
    assert result.item_ids[0] == "item_0"
    assert result.latency_ms > 0


def test_faiss_hnsw_index_build_search(sample_embeddings: dict[str, NDArray[np.float32]]) -> None:
    """Test FAISS HNSW index (SOTA for medium datasets)."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    index.build(item_embeddings=sample_embeddings, index_type="HNSW32")

    query = sample_embeddings["item_0"]
    result = index.search(query_embedding=query, k=10)

    assert len(result.item_ids) == 10
    assert result.item_ids[0] == "item_0"
    assert result.scores[0] > 0.99


def test_ann_index_search_k_limit(sample_embeddings: dict[str, NDArray[np.float32]]) -> None:
    """Test search with k > n_items (should return all items)."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    index.build(item_embeddings=sample_embeddings, index_type="Flat")

    query = sample_embeddings["item_0"]
    result = index.search(query_embedding=query, k=1000)  # k > 100

    assert len(result.item_ids) == 100  # Should return all 100 items


def test_ann_index_save_load_roundtrip(
    sample_embeddings: dict[str, NDArray[np.float32]], tmp_path: Path
) -> None:
    """Test save/load roundtrip for FAISS index."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    index.build(item_embeddings=sample_embeddings, index_type="Flat")

    # Save
    index_dir = tmp_path / "test_index"
    index_dir.mkdir()
    index.save(path=index_dir)

    assert (index_dir / "faiss_index.bin").exists()
    assert (index_dir / "item_ids.pkl").exists()

    # Load
    index2 = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    index2.load(path=index_dir)

    # Search should work identically
    query = sample_embeddings["item_0"]
    result = index2.search(query_embedding=query, k=10)

    assert len(result.item_ids) == 10
    assert result.item_ids[0] == "item_0"


def test_ann_index_search_before_build() -> None:
    """Test search fails if index not built."""
    index = ANNIndex(backend=ANNBackend.FAISS, embedding_dim=128)
    query = np.random.randn(128).astype(np.float32)

    with pytest.raises(RuntimeError, match="Index not built"):
        index.search(query_embedding=query, k=10)


def test_ann_index_unsupported_backend() -> None:
    """Test unsupported backend raises error."""
    with pytest.raises(ValueError, match="Unsupported backend"):
        index = ANNIndex(backend="invalid_backend", embedding_dim=128)  # type: ignore[arg-type]
        index.build(item_embeddings={}, index_type="Flat")
