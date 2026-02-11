"""Tests for data adapter (Polars -> PyTorch bridge)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import torch

from wine_rec.models.training.data_adapter import (
    build_adjacency_sparse,
    build_bpr_triplets,
    build_id_maps,
    load_feature_data,
    load_id_maps,
    load_interaction_data,
    save_id_maps,
)


def _make_training_data(tmp_path: Path) -> Path:
    """Create a minimal training parquet for testing."""
    df = pl.DataFrame(
        {
            "impression_id": [f"imp_{i}" for i in range(10)],
            "user_id": ["u1", "u1", "u1", "u2", "u2", "u2", "u3", "u3", "u3", "u3"],
            "wine_sku_id": [
                "s1",
                "s2",
                "s3",
                "s1",
                "s4",
                "s5",
                "s2",
                "s3",
                "s4",
                "s5",
            ],
            "label": [5, 2, 0, 3, 0, 1, 0, 4, 0, 0],
            "split": [
                "train",
                "train",
                "train",
                "train",
                "train",
                "val",
                "val",
                "test",
                "test",
                "test",
            ],
            "shown_ts": list(range(1000, 1010)),
        }
    )
    out = tmp_path / "training.parquet"
    df.write_parquet(out)
    return out


class TestBuildIdMaps:
    def test_contiguous_ids(self):
        df = pl.DataFrame(
            {
                "user_id": ["u2", "u1", "u2"],
                "wine_sku_id": ["s3", "s1", "s2"],
            }
        )
        user_map, item_map = build_id_maps(df)
        assert user_map == {"u1": 0, "u2": 1}
        assert item_map == {"s1": 0, "s2": 1, "s3": 2}


class TestLoadInteractionData:
    def test_loads_train_split(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="train")

        assert data.n_users == 3
        assert data.n_items == 5
        assert len(data.user_ids) == 5  # 5 train rows
        assert data.user_ids.dtype == torch.int64
        assert data.labels.dtype == torch.float32

    def test_loads_val_split(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="val")
        assert len(data.user_ids) == 2  # 2 val rows

    def test_id_maps_shared(self, tmp_path: Path):
        """ID maps should cover all users/items across all splits."""
        path = _make_training_data(tmp_path)
        train = load_interaction_data(str(path), split="train")
        test = load_interaction_data(str(path), split="test")
        assert train.n_users == test.n_users
        assert train.n_items == test.n_items

    def test_directory_input(self, tmp_path: Path):
        """Should find parquet files in directories."""
        subdir = tmp_path / "data"
        subdir.mkdir()
        path = _make_training_data(tmp_path)
        path.rename(subdir / "data.parquet")
        data = load_interaction_data(str(subdir), split="train")
        assert len(data.user_ids) > 0


class TestBuildBprTriplets:
    def test_generates_triplets(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="train")
        users, pos, neg = build_bpr_triplets(data, n_neg=1, seed=42)

        # should have one neg per positive
        n_pos = (data.labels > 0).sum().item()
        assert len(users) == n_pos
        assert len(pos) == n_pos
        assert len(neg) == n_pos

    def test_deterministic(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="train")
        u1, p1, n1 = build_bpr_triplets(data, seed=42)
        u2, p2, n2 = build_bpr_triplets(data, seed=42)
        assert torch.equal(u1, u2)
        assert torch.equal(p1, p2)
        assert torch.equal(n1, n2)

    def test_negatives_not_positive(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="train")
        _users, pos, neg = build_bpr_triplets(data, seed=42)
        # negatives should not equal positives
        assert not torch.equal(pos, neg)


class TestBuildAdjacencySparse:
    def test_shape(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="train")
        adj = build_adjacency_sparse(data)

        n = data.n_users + data.n_items
        assert adj.shape == (n, n)
        assert adj.is_sparse

    def test_symmetric(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_interaction_data(str(path), split="train")
        adj = build_adjacency_sparse(data)

        dense = adj.to_dense()
        assert torch.allclose(dense, dense.T, atol=1e-6)


class TestLoadFeatureData:
    def test_loads_minimal_features(self, tmp_path: Path):
        path = _make_training_data(tmp_path)
        data = load_feature_data(str(path), split="train")

        assert data.features.shape[1] == 2  # user_id + item_id
        assert data.field_dims == [data.n_users, data.n_items]
        assert len(data.labels) == 5


class TestSaveLoadIdMaps:
    def test_roundtrip(self, tmp_path: Path):
        user_map = {"u1": 0, "u2": 1}
        item_map = {"s1": 0, "s2": 1, "s3": 2}
        save_id_maps(user_map, item_map, str(tmp_path / "model"))
        loaded_user, loaded_item = load_id_maps(str(tmp_path / "model"))
        assert loaded_user == user_map
        assert loaded_item == item_map
