"""Two-Tower (DSSM) retrieval model.

Dual-encoder for candidate retrieval: User tower + Item tower → dot product.
Pure PyTorch implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F  # noqa: N812

from wine_rec.common.logging import get_logger
from wine_rec.models.evaluation.metrics import ndcg_at_k, recall_at_k
from wine_rec.models.training.data_adapter import (
    InteractionData,
    load_interaction_data,
    save_id_maps,
)


if TYPE_CHECKING:
    from numpy.typing import NDArray

log = get_logger(__name__)


class _Tower(nn.Module):
    """MLP tower for encoding user or item."""

    def __init__(self, n_entities: int, embedding_dim: int, hidden_dims: tuple[int, ...]) -> None:
        super().__init__()
        self.embedding = nn.Embedding(n_entities, hidden_dims[0] if hidden_dims else embedding_dim)
        nn.init.xavier_uniform_(self.embedding.weight)

        layers: list[nn.Module] = []
        in_dim = hidden_dims[0] if hidden_dims else embedding_dim
        for out_dim in hidden_dims[1:]:
            layers.append(nn.Linear(in_dim, out_dim))
            layers.append(nn.ReLU())
            in_dim = out_dim
        layers.append(nn.Linear(in_dim, embedding_dim))
        self.mlp = nn.Sequential(*layers)

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        """Encode IDs → L2-normalized embeddings [B, D]."""
        x = self.embedding(ids)
        x = self.mlp(x)
        return F.normalize(x, p=2, dim=1)


class TwoTowerModel(nn.Module):
    """Dual-encoder for candidate retrieval + ANN index.

    User tower + Item tower → cosine similarity (via L2-normalized dot product).
    """

    def __init__(
        self,
        *,
        n_users: int,
        n_items: int,
        embedding_dim: int = 128,
        hidden_dims: tuple[int, ...] = (256, 128),
    ) -> None:
        super().__init__()
        self.n_users = n_users
        self.n_items = n_items
        self.embedding_dim = embedding_dim

        self.user_tower = _Tower(n_users, embedding_dim, hidden_dims)
        self.item_tower = _Tower(n_items, embedding_dim, hidden_dims)

    def encode_user(self, user_ids: torch.Tensor) -> torch.Tensor:
        """Encode users → L2-normalized embeddings [B, D]."""
        return self.user_tower(user_ids)

    def encode_item(self, item_ids: torch.Tensor) -> torch.Tensor:
        """Encode items → L2-normalized embeddings [B, D]."""
        return self.item_tower(item_ids)

    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """Compute cosine similarity scores [B]."""
        u_emb = self.encode_user(user_ids)
        i_emb = self.encode_item(item_ids)
        return (u_emb * i_emb).sum(dim=1)

    def predict_all(self, user_ids: torch.Tensor) -> torch.Tensor:
        """Score all items for given users. Returns [B, n_items]."""
        u_emb = self.encode_user(user_ids)
        all_items = torch.arange(self.n_items, device=u_emb.device)
        i_emb = self.encode_item(all_items)
        return u_emb @ i_emb.T


def train_two_tower(
    *,
    dataset_path: str,
    epochs: int = 30,
    learning_rate: float = 0.001,
    embedding_dim: int = 128,
    hidden_dims: tuple[int, ...] = (256, 128),
    temperature: float = 0.1,
    seed: int = 42,
    output_dir: str | None = None,
) -> dict[str, float]:
    """Train Two-Tower model with sampled softmax loss.

    Returns:
        Evaluation metrics dict.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_data = load_interaction_data(dataset_path, split="train")
    val_data = load_interaction_data(dataset_path, split="val")

    model = TwoTowerModel(
        n_users=train_data.n_users,
        n_items=train_data.n_items,
        embedding_dim=embedding_dim,
        hidden_dims=hidden_dims,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    best_recall = 0.0
    best_state: dict[str, torch.Tensor] | None = None

    pos_mask = train_data.labels > 0
    pos_users = train_data.user_ids[pos_mask]
    pos_items = train_data.item_ids[pos_mask]

    for epoch in range(epochs):
        model.train()

        u_emb = model.encode_user(pos_users)
        i_emb = model.encode_item(pos_items)

        # in-batch negatives: similarity matrix [B, B]
        logits = u_emb @ i_emb.T / temperature
        labels = torch.arange(len(pos_users), device=logits.device)
        loss = F.cross_entropy(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
            val_metrics = _evaluate_two_tower(model, val_data, k=10)
            log.info(
                "two_tower_epoch",
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
    test_metrics = _evaluate_two_tower(model, test_data, k=10)

    if output_dir is not None:
        _save_two_tower(model, output_dir, embedding_dim, hidden_dims, test_metrics, seed)
        save_id_maps(train_data.user_id_map, train_data.item_id_map, output_dir)

    return test_metrics


def _evaluate_two_tower(
    model: TwoTowerModel, data: InteractionData, *, k: int = 10
) -> dict[str, float]:
    """Evaluate Two-Tower on Recall@K and NDCG@K per user."""
    model.eval()
    unique_users = data.user_ids.unique()

    recalls: list[float] = []
    ndcgs: list[float] = []

    with torch.no_grad():
        for uid in unique_users:
            mask = data.user_ids == uid
            items = data.item_ids[mask]
            labels = data.labels[mask]

            if labels.sum() == 0:
                continue

            scores = model(uid.expand(len(items)), items)

            y_true: NDArray[np.int_] = (labels > 0).numpy().astype(np.int_)
            y_pred: NDArray[np.float64] = scores.numpy().astype(np.float64)

            recalls.append(recall_at_k(y_true=y_true, y_pred=y_pred, k=k))
            ndcgs.append(ndcg_at_k(y_true=y_true, y_pred=y_pred, k=k))

    return {
        f"recall@{k}": float(np.mean(recalls)) if recalls else 0.0,
        f"ndcg@{k}": float(np.mean(ndcgs)) if ndcgs else 0.0,
    }


def _save_two_tower(
    model: TwoTowerModel,
    output_dir: str,
    embedding_dim: int,
    hidden_dims: tuple[int, ...],
    metrics: dict[str, float],
    seed: int,
) -> None:
    """Save Two-Tower model artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")

    config = {
        "model_name": "two_tower",
        "n_users": model.n_users,
        "n_items": model.n_items,
        "embedding_dim": embedding_dim,
        "hidden_dims": list(hidden_dims),
        "seed": seed,
    }
    with (out / "config.json").open("w") as f:
        json.dump(config, f, indent=2)
    with (out / "metrics.json").open("w") as f:
        json.dump(metrics, f, indent=2)

    log.info("two_tower_saved", output_dir=output_dir, metrics=metrics)


def load_two_tower(model_dir: str) -> TwoTowerModel:
    """Load a trained Two-Tower model from disk."""
    d = Path(model_dir)
    with (d / "config.json").open() as f:
        config = json.load(f)

    model = TwoTowerModel(
        n_users=int(config["n_users"]),
        n_items=int(config["n_items"]),
        embedding_dim=int(config["embedding_dim"]),
        hidden_dims=tuple(int(x) for x in config["hidden_dims"]),
    )
    state = torch.load(d / "model.pt", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model
