"""BPR (Bayesian Personalized Ranking) baseline.

Matrix Factorization with BPR loss (Rendle et al., UAI 2009).
Pure PyTorch implementation — no RecBole dependency.
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
    build_bpr_triplets,
    load_interaction_data,
    save_id_maps,
)


if TYPE_CHECKING:
    from numpy.typing import NDArray

log = get_logger(__name__)


class BPRModel(nn.Module):
    """Matrix Factorization with BPR loss.

    Architecture: User embedding x Item embedding dot product.
    Loss: -log(sigmoid(pos_score - neg_score)).
    """

    def __init__(
        self,
        *,
        n_users: int,
        n_items: int,
        embedding_dim: int = 64,
    ) -> None:
        super().__init__()
        self.n_users = n_users
        self.n_items = n_items
        self.embedding_dim = embedding_dim

        self.user_embedding = nn.Embedding(n_users, embedding_dim)
        self.item_embedding = nn.Embedding(n_items, embedding_dim)

        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)

    def forward(
        self,
        user_ids: torch.Tensor,
        pos_ids: torch.Tensor,
        neg_ids: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute positive and negative scores.

        Returns:
            (pos_scores, neg_scores) each of shape [B].
        """
        u_emb = self.user_embedding(user_ids)
        p_emb = self.item_embedding(pos_ids)
        n_emb = self.item_embedding(neg_ids)

        pos_scores = (u_emb * p_emb).sum(dim=1)
        neg_scores = (u_emb * n_emb).sum(dim=1)
        return pos_scores, neg_scores

    def predict(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """Score user-item pairs. Returns [B] scores."""
        u_emb = self.user_embedding(user_ids)
        i_emb = self.item_embedding(item_ids)
        return (u_emb * i_emb).sum(dim=1)

    def predict_all(self, user_ids: torch.Tensor) -> torch.Tensor:
        """Score all items for given users. Returns [B, n_items]."""
        u_emb = self.user_embedding(user_ids)
        return u_emb @ self.item_embedding.weight.T

    @staticmethod
    def bpr_loss(pos_scores: torch.Tensor, neg_scores: torch.Tensor) -> torch.Tensor:
        """BPR loss: -log(sigmoid(pos - neg))."""
        return -torch.log(torch.sigmoid(pos_scores - neg_scores) + 1e-8).mean()


def train_bpr(
    *,
    dataset_path: str,
    epochs: int = 50,
    learning_rate: float = 0.001,
    embedding_dim: int = 64,
    weight_decay: float = 1e-5,
    n_neg: int = 1,
    seed: int = 42,
    output_dir: str | None = None,
) -> dict[str, float]:
    """Train BPR model end-to-end.

    Args:
        dataset_path: Path to training_examples parquet.
        epochs: Number of training epochs.
        learning_rate: Adam learning rate.
        embedding_dim: Embedding dimension.
        weight_decay: L2 regularization.
        n_neg: Negatives per positive for BPR triplets.
        seed: Random seed for reproducibility.
        output_dir: Directory to save model artifacts.

    Returns:
        Evaluation metrics dict.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_data = load_interaction_data(dataset_path, split="train")
    val_data = load_interaction_data(dataset_path, split="val")

    model = BPRModel(
        n_users=train_data.n_users,
        n_items=train_data.n_items,
        embedding_dim=embedding_dim,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    best_recall = 0.0
    best_state: dict[str, torch.Tensor] | None = None

    for epoch in range(epochs):
        model.train()
        users, pos_items, neg_items = build_bpr_triplets(train_data, n_neg=n_neg, seed=seed + epoch)

        pos_scores, neg_scores = model(users, pos_items, neg_items)
        loss = BPRModel.bpr_loss(pos_scores, neg_scores)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
            val_metrics = _evaluate_bpr(model, val_data, k=10)
            log.info(
                "bpr_epoch",
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
    test_metrics = _evaluate_bpr(model, test_data, k=10)

    if output_dir is not None:
        _save_bpr(model, output_dir, embedding_dim, test_metrics, seed)
        save_id_maps(train_data.user_id_map, train_data.item_id_map, output_dir)

    return test_metrics


def _evaluate_bpr(model: BPRModel, data: InteractionData, *, k: int = 10) -> dict[str, float]:
    """Evaluate BPR on Recall@K and NDCG@K per user."""
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

            scores = model.predict(uid.expand(len(items)), items)

            y_true: NDArray[np.int_] = (labels > 0).numpy().astype(np.int_)
            y_pred: NDArray[np.float64] = scores.numpy().astype(np.float64)

            recalls.append(recall_at_k(y_true=y_true, y_pred=y_pred, k=k))
            ndcgs.append(ndcg_at_k(y_true=y_true, y_pred=y_pred, k=k))

    return {
        f"recall@{k}": float(np.mean(recalls)) if recalls else 0.0,
        f"ndcg@{k}": float(np.mean(ndcgs)) if ndcgs else 0.0,
    }


def _save_bpr(
    model: BPRModel,
    output_dir: str,
    embedding_dim: int,
    metrics: dict[str, float],
    seed: int,
) -> None:
    """Save BPR model artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")

    config = {
        "model_name": "bpr",
        "n_users": model.n_users,
        "n_items": model.n_items,
        "embedding_dim": embedding_dim,
        "seed": seed,
    }
    with (out / "config.json").open("w") as f:
        json.dump(config, f, indent=2)
    with (out / "metrics.json").open("w") as f:
        json.dump(metrics, f, indent=2)

    log.info("bpr_saved", output_dir=output_dir, metrics=metrics)


def load_bpr(model_dir: str) -> BPRModel:
    """Load a trained BPR model from disk."""
    d = Path(model_dir)
    with (d / "config.json").open() as f:
        config = json.load(f)

    model = BPRModel(
        n_users=int(config["n_users"]),
        n_items=int(config["n_items"]),
        embedding_dim=int(config["embedding_dim"]),
    )
    state = torch.load(d / "model.pt", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model
