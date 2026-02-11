"""LightGCN graph-based collaborative filtering.

He et al., SIGIR 2020: "LightGCN: Simplifying and Powering Graph Convolution Network
for Recommendation."

Pure PyTorch implementation using torch.sparse — no torch-geometric dependency.
Designed for RFC-REC-EXT-004 §3 heterogeneous wine graph.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from torch import nn

from wine_rec.common.logging import get_logger
from wine_rec.models.evaluation.metrics import ndcg_at_k, recall_at_k
from wine_rec.models.training.data_adapter import (
    InteractionData,
    build_adjacency_sparse,
    build_bpr_triplets,
    load_interaction_data,
    save_id_maps,
)


if TYPE_CHECKING:
    from numpy.typing import NDArray

log = get_logger(__name__)


class LightGCNModel(nn.Module):
    """LightGCN for graph-based recommendation.

    Architecture: User/item embeddings → K-layer graph convolution
    (no activation, no transform) → mean pooling across layers → BPR loss.
    """

    def __init__(
        self,
        *,
        n_users: int,
        n_items: int,
        embedding_dim: int = 64,
        num_layers: int = 3,
    ) -> None:
        super().__init__()
        self.n_users = n_users
        self.n_items = n_items
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers

        self.user_embedding = nn.Embedding(n_users, embedding_dim)
        self.item_embedding = nn.Embedding(n_items, embedding_dim)

        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)

    def forward(self, adj: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """K-layer graph convolution → mean-pooled user/item embeddings.

        Args:
            adj: Normalized adjacency (n_users + n_items, n_users + n_items) sparse.

        Returns:
            (user_embeddings [n_users, D], item_embeddings [n_items, D])
        """
        e0 = torch.cat([self.user_embedding.weight, self.item_embedding.weight], dim=0)
        layer_embeds = [e0]

        x = e0
        for _layer in range(self.num_layers):
            x = torch.sparse.mm(adj, x)
            layer_embeds.append(x)

        # mean pooling across layers (including layer 0)
        stacked = torch.stack(layer_embeds, dim=0)
        final = stacked.mean(dim=0)

        user_embeds = final[: self.n_users]
        item_embeds = final[self.n_users :]
        return user_embeds, item_embeds

    def predict(
        self,
        user_ids: torch.Tensor,
        item_ids: torch.Tensor,
        user_embeds: torch.Tensor,
        item_embeds: torch.Tensor,
    ) -> torch.Tensor:
        """Score user-item pairs using pre-computed embeddings."""
        u = user_embeds[user_ids]
        i = item_embeds[item_ids]
        return (u * i).sum(dim=1)

    @staticmethod
    def bpr_loss(
        user_embeds: torch.Tensor,
        item_embeds: torch.Tensor,
        users: torch.Tensor,
        pos_items: torch.Tensor,
        neg_items: torch.Tensor,
        reg_weight: float = 1e-5,
    ) -> torch.Tensor:
        """BPR loss with L2 regularization on embeddings."""
        u = user_embeds[users]
        p = item_embeds[pos_items]
        n = item_embeds[neg_items]

        pos_scores = (u * p).sum(dim=1)
        neg_scores = (u * n).sum(dim=1)
        bpr = -torch.log(torch.sigmoid(pos_scores - neg_scores) + 1e-8).mean()

        reg = reg_weight * (u.norm(2).pow(2) + p.norm(2).pow(2) + n.norm(2).pow(2)) / len(users)
        return bpr + reg


def train_lightgcn(
    *,
    dataset_path: str,
    epochs: int = 100,
    learning_rate: float = 0.001,
    embedding_dim: int = 64,
    num_layers: int = 3,
    reg_weight: float = 1e-5,
    n_neg: int = 1,
    seed: int = 42,
    output_dir: str | None = None,
) -> dict[str, float]:
    """Train LightGCN model end-to-end.

    Returns:
        Evaluation metrics dict.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_data = load_interaction_data(dataset_path, split="train")
    val_data = load_interaction_data(dataset_path, split="val")

    adj = build_adjacency_sparse(train_data)

    model = LightGCNModel(
        n_users=train_data.n_users,
        n_items=train_data.n_items,
        embedding_dim=embedding_dim,
        num_layers=num_layers,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    best_recall = 0.0
    best_state: dict[str, torch.Tensor] | None = None

    for epoch in range(epochs):
        model.train()
        users, pos_items, neg_items = build_bpr_triplets(train_data, n_neg=n_neg, seed=seed + epoch)

        user_embeds, item_embeds = model(adj)
        loss = LightGCNModel.bpr_loss(
            user_embeds, item_embeds, users, pos_items, neg_items, reg_weight
        )

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 10 == 0 or epoch == epochs - 1:
            val_metrics = _evaluate_lightgcn(model, adj, val_data, k=10)
            log.info(
                "lightgcn_epoch",
                epoch=epoch + 1,
                loss=float(loss),
                val_recall_10=val_metrics["recall@10"],
            )
            if val_metrics["recall@10"] > best_recall:
                best_recall = val_metrics["recall@10"]
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    test_data = load_interaction_data(dataset_path, split="test")
    test_metrics = _evaluate_lightgcn(model, adj, test_data, k=10)

    if output_dir is not None:
        _save_lightgcn(model, output_dir, embedding_dim, num_layers, test_metrics, seed)
        save_id_maps(train_data.user_id_map, train_data.item_id_map, output_dir)

    return test_metrics


def _evaluate_lightgcn(
    model: LightGCNModel,
    adj: torch.Tensor,
    data: InteractionData,
    *,
    k: int = 10,
) -> dict[str, float]:
    """Evaluate LightGCN on Recall@K and NDCG@K per user."""
    model.eval()
    unique_users = data.user_ids.unique()

    recalls: list[float] = []
    ndcgs: list[float] = []

    with torch.no_grad():
        user_embeds, item_embeds = model(adj)

        for uid in unique_users:
            mask = data.user_ids == uid
            items = data.item_ids[mask]
            labels = data.labels[mask]

            if labels.sum() == 0:
                continue

            scores = model.predict(uid.expand(len(items)), items, user_embeds, item_embeds)

            y_true: NDArray[np.int_] = (labels > 0).numpy().astype(np.int_)
            y_pred: NDArray[np.float64] = scores.numpy().astype(np.float64)

            recalls.append(recall_at_k(y_true=y_true, y_pred=y_pred, k=k))
            ndcgs.append(ndcg_at_k(y_true=y_true, y_pred=y_pred, k=k))

    return {
        f"recall@{k}": float(np.mean(recalls)) if recalls else 0.0,
        f"ndcg@{k}": float(np.mean(ndcgs)) if ndcgs else 0.0,
    }


def _save_lightgcn(
    model: LightGCNModel,
    output_dir: str,
    embedding_dim: int,
    num_layers: int,
    metrics: dict[str, float],
    seed: int,
) -> None:
    """Save LightGCN model artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")

    config = {
        "model_name": "lightgcn",
        "n_users": model.n_users,
        "n_items": model.n_items,
        "embedding_dim": embedding_dim,
        "num_layers": num_layers,
        "seed": seed,
    }
    with (out / "config.json").open("w") as f:
        json.dump(config, f, indent=2)
    with (out / "metrics.json").open("w") as f:
        json.dump(metrics, f, indent=2)

    log.info("lightgcn_saved", output_dir=output_dir, metrics=metrics)


def load_lightgcn(model_dir: str) -> LightGCNModel:
    """Load a trained LightGCN model from disk."""
    d = Path(model_dir)
    with (d / "config.json").open() as f:
        config = json.load(f)

    model = LightGCNModel(
        n_users=int(config["n_users"]),
        n_items=int(config["n_items"]),
        embedding_dim=int(config["embedding_dim"]),
        num_layers=int(config["num_layers"]),
    )
    state = torch.load(d / "model.pt", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model
