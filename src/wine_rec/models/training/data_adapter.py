"""Data adapter: Polars training data → PyTorch tensors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl
import torch

from wine_rec.common.logging import get_logger


log = get_logger(__name__)


@dataclass
class InteractionData:
    """Sparse user-item interactions for CF models (BPR, LightGCN)."""

    user_ids: torch.Tensor  # [N] int64
    item_ids: torch.Tensor  # [N] int64
    labels: torch.Tensor  # [N] float32
    timestamps: torch.Tensor  # [N] int64
    n_users: int
    n_items: int
    user_id_map: dict[str, int]
    item_id_map: dict[str, int]


@dataclass
class FeatureData:
    """Feature-enriched data for DeepFM / ranking models."""

    user_ids: torch.Tensor  # [N] int64
    item_ids: torch.Tensor  # [N] int64
    labels: torch.Tensor  # [N] float32
    features: torch.Tensor  # [N, D] float32
    field_dims: list[int]
    n_users: int
    n_items: int
    user_id_map: dict[str, int]
    item_id_map: dict[str, int]


def build_id_maps(df: pl.DataFrame) -> tuple[dict[str, int], dict[str, int]]:
    """Build contiguous 0-based ID maps for users and items."""
    user_ids = sorted(df["user_id"].unique().to_list())
    item_ids = sorted(df["wine_sku_id"].unique().to_list())
    user_map: dict[str, int] = {uid: i for i, uid in enumerate(user_ids)}
    item_map: dict[str, int] = {iid: i for i, iid in enumerate(item_ids)}
    return user_map, item_map


def _read_parquet(path: str) -> pl.DataFrame:
    """Read a parquet file or first parquet in a directory."""
    p = Path(path)
    if p.is_file():
        return pl.read_parquet(p)
    parquet_files = list(p.rglob("*.parquet"))
    if not parquet_files:
        msg = f"No parquet files found in {path}"
        raise FileNotFoundError(msg)
    return pl.read_parquet(parquet_files[0])


def load_interaction_data(path: str, split: str = "train") -> InteractionData:
    """Load training examples into InteractionData tensors.

    Args:
        path: Path to training_examples parquet (file or directory).
        split: One of "train", "val", "test".
    """
    full_df = _read_parquet(path)
    df = full_df.filter(pl.col("split") == split)
    user_map, item_map = build_id_maps(full_df)

    user_idx = [user_map[u] for u in df["user_id"].to_list()]
    item_idx = [item_map[i] for i in df["wine_sku_id"].to_list()]
    labels = df["label"].to_list()

    ts_col: list[int] = (
        df["shown_ts"].cast(pl.Int64).to_list() if "shown_ts" in df.columns else [0] * len(df)
    )

    log.info(
        "loaded_interaction_data",
        split=split,
        n_interactions=len(df),
        n_users=len(user_map),
        n_items=len(item_map),
    )

    return InteractionData(
        user_ids=torch.tensor(user_idx, dtype=torch.int64),
        item_ids=torch.tensor(item_idx, dtype=torch.int64),
        labels=torch.tensor(labels, dtype=torch.float32),
        timestamps=torch.tensor(ts_col, dtype=torch.int64),
        n_users=len(user_map),
        n_items=len(item_map),
        user_id_map=user_map,
        item_id_map=item_map,
    )


def build_bpr_triplets(
    data: InteractionData, *, n_neg: int = 1, seed: int = 42
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Generate (user, pos_item, neg_item) triplets for BPR training.

    For each positive interaction, sample n_neg random negative items.
    """
    rng = np.random.default_rng(seed)

    pos_mask = data.labels > 0
    pos_users = data.user_ids[pos_mask]
    pos_items = data.item_ids[pos_mask]

    if len(pos_users) == 0:
        return (
            torch.zeros(0, dtype=torch.int64),
            torch.zeros(0, dtype=torch.int64),
            torch.zeros(0, dtype=torch.int64),
        )

    user_pos: dict[int, set[int]] = {}
    for u, i in zip(pos_users.tolist(), pos_items.tolist(), strict=True):
        user_pos.setdefault(u, set()).add(i)

    users_out: list[int] = []
    pos_out: list[int] = []
    neg_out: list[int] = []

    for u, p in zip(pos_users.tolist(), pos_items.tolist(), strict=True):
        pos_set = user_pos.get(u, set())
        for _ in range(n_neg):
            neg = int(rng.integers(0, data.n_items))
            while neg in pos_set:
                neg = int(rng.integers(0, data.n_items))
            users_out.append(u)
            pos_out.append(p)
            neg_out.append(neg)

    return (
        torch.tensor(users_out, dtype=torch.int64),
        torch.tensor(pos_out, dtype=torch.int64),
        torch.tensor(neg_out, dtype=torch.int64),
    )


def build_adjacency_sparse(data: InteractionData) -> torch.Tensor:
    """Build normalized adjacency matrix for LightGCN.

    Constructs (n_users + n_items) x (n_users + n_items) bipartite adjacency
    with symmetric normalization D^{-1/2} A D^{-1/2}.
    """
    n = data.n_users + data.n_items
    pos_mask = data.labels > 0
    users = data.user_ids[pos_mask]
    items = data.item_ids[pos_mask] + data.n_users

    row = torch.cat([users, items])
    col = torch.cat([items, users])
    values = torch.ones(len(row), dtype=torch.float32)

    adj = torch.sparse_coo_tensor(torch.stack([row, col]), values, size=(n, n)).coalesce()

    degree = torch.sparse.sum(adj, dim=1).to_dense()
    d_inv_sqrt = torch.where(degree > 0, degree.pow(-0.5), torch.zeros_like(degree))

    row_idx = adj.indices()[0]
    col_idx = adj.indices()[1]
    norm_values = d_inv_sqrt[row_idx] * adj.values() * d_inv_sqrt[col_idx]

    return torch.sparse_coo_tensor(adj.indices(), norm_values, size=(n, n)).coalesce()


def load_feature_data(
    path: str,
    split: str = "train",
    feature_path: str | None = None,  # noqa: ARG001
) -> FeatureData:
    """Load training examples + features into FeatureData tensors.

    If feature_path is None, constructs minimal features (user_id, item_id).
    """
    full_df = _read_parquet(path)
    df = full_df.filter(pl.col("split") == split)
    user_map, item_map = build_id_maps(full_df)

    user_idx = [user_map[u] for u in df["user_id"].to_list()]
    item_idx = [item_map[i] for i in df["wine_sku_id"].to_list()]
    labels = df["label"].to_list()

    field_dims = [len(user_map), len(item_map)]
    features_np = np.column_stack([user_idx, item_idx]).astype(np.int64)

    log.info(
        "loaded_feature_data",
        split=split,
        n_rows=len(df),
        n_fields=len(field_dims),
    )

    return FeatureData(
        user_ids=torch.tensor(user_idx, dtype=torch.int64),
        item_ids=torch.tensor(item_idx, dtype=torch.int64),
        labels=torch.tensor(labels, dtype=torch.float32),
        features=torch.from_numpy(features_np).float(),
        field_dims=field_dims,
        n_users=len(user_map),
        n_items=len(item_map),
        user_id_map=user_map,
        item_id_map=item_map,
    )


def save_id_maps(
    user_map: dict[str, int],
    item_map: dict[str, int],
    output_dir: str,
) -> None:
    """Save ID maps as JSON for inference."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "user_id_map.json").open("w") as f:
        json.dump(user_map, f)
    with (out / "item_id_map.json").open("w") as f:
        json.dump(item_map, f)


def load_id_maps(model_dir: str) -> tuple[dict[str, int], dict[str, int]]:
    """Load ID maps from a trained model directory."""
    d = Path(model_dir)
    with (d / "user_id_map.json").open() as f:
        user_map: dict[str, int] = json.load(f)
    with (d / "item_id_map.json").open() as f:
        item_map: dict[str, int] = json.load(f)
    return user_map, item_map
