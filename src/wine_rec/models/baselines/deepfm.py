"""DeepFM ranking model.

Guo et al., IJCAI 2017: "DeepFM: A Factorization-Machine based Neural Network
for CTR Prediction."

Pure PyTorch implementation. Used as 2-stage ranker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from sklearn.metrics import log_loss, roc_auc_score
from torch import nn

from wine_rec.common.logging import get_logger
from wine_rec.models.evaluation.metrics import ndcg_at_k, recall_at_k
from wine_rec.models.training.data_adapter import (
    FeatureData,
    load_feature_data,
    save_id_maps,
)


if TYPE_CHECKING:
    from numpy.typing import NDArray

log = get_logger(__name__)


class _FMLayer(nn.Module):
    """2nd-order Factorization Machine interaction layer."""

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Compute FM interactions. embeddings: [B, n_fields, D]."""
        square_of_sum = embeddings.sum(dim=1).pow(2)
        sum_of_square = embeddings.pow(2).sum(dim=1)
        return 0.5 * (square_of_sum - sum_of_square).sum(dim=1, keepdim=True)


class _DNNLayer(nn.Module):
    """Deep MLP branch."""

    def __init__(self, input_dim: int, hidden_dims: tuple[int, ...], dropout: float = 0.1) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        in_dim = input_dim
        for out_dim in hidden_dims:
            layers.append(nn.Linear(in_dim, out_dim))
            layers.append(nn.BatchNorm1d(out_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            in_dim = out_dim
        layers.append(nn.Linear(in_dim, 1))
        self.mlp = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, n_fields * D] -> [B, 1]."""
        return self.mlp(x)


class DeepFMModel(nn.Module):
    """DeepFM for CTR prediction / ranking.

    Architecture:
        - Linear: 1st-order features -> scalar
        - FM: 2nd-order cross features -> scalar
        - DNN: high-order feature interactions -> scalar
        Output: sigmoid(linear + fm + dnn)
    """

    def __init__(
        self,
        *,
        field_dims: list[int],
        embedding_dim: int = 16,
        mlp_dims: tuple[int, ...] = (256, 128),
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.field_dims = field_dims
        self.embedding_dim = embedding_dim
        self.n_fields = len(field_dims)

        offsets = [0, *list(np.cumsum(field_dims)[:-1])]
        self.offsets: torch.Tensor
        self.register_buffer("offsets", torch.tensor(offsets, dtype=torch.long))

        total_dim = sum(field_dims)
        self.linear = nn.Embedding(total_dim, 1)
        self.embedding = nn.Embedding(total_dim, embedding_dim)
        self.bias = nn.Parameter(torch.zeros(1))

        self.fm = _FMLayer()
        self.dnn = _DNNLayer(self.n_fields * embedding_dim, mlp_dims, dropout)

        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.xavier_uniform_(self.embedding.weight)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Predict click/purchase probability.

        Args:
            features: [B, n_fields] integer tensor of field indices.

        Returns:
            [B] probability scores.
        """
        x = features.long() + self.offsets.unsqueeze(0)

        linear_out = self.linear(x).sum(dim=1) + self.bias
        emb = self.embedding(x)
        fm_out = self.fm(emb)
        dnn_input = emb.view(emb.size(0), -1)
        dnn_out = self.dnn(dnn_input)

        logit = (linear_out + fm_out + dnn_out).squeeze(1)
        return torch.sigmoid(logit)

    def predict_scores(self, features: torch.Tensor) -> torch.Tensor:
        """Score items (no grad). Returns [B] probabilities."""
        self.eval()
        with torch.no_grad():
            return self.forward(features)


def train_deepfm(
    *,
    dataset_path: str,
    feature_path: str | None = None,
    epochs: int = 30,
    learning_rate: float = 0.001,
    embedding_dim: int = 16,
    mlp_dims: tuple[int, ...] = (256, 128),
    dropout: float = 0.1,
    batch_size: int = 256,
    seed: int = 42,
    output_dir: str | None = None,
) -> dict[str, float]:
    """Train DeepFM model with BCE loss.

    Returns:
        Evaluation metrics dict.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_data = load_feature_data(dataset_path, split="train", feature_path=feature_path)
    val_data = load_feature_data(dataset_path, split="val", feature_path=feature_path)

    model = DeepFMModel(
        field_dims=train_data.field_dims,
        embedding_dim=embedding_dim,
        mlp_dims=mlp_dims,
        dropout=dropout,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.BCELoss()

    best_auc = 0.0
    best_state: dict[str, torch.Tensor] | None = None

    binary_labels = (train_data.labels > 0).float()
    n_samples = len(binary_labels)

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n_samples)
        epoch_loss = 0.0
        n_batches = 0

        for start in range(0, n_samples, batch_size):
            idx = perm[start : start + batch_size]
            batch_features = train_data.features[idx]
            batch_labels = binary_labels[idx]

            preds = model(batch_features)
            loss = criterion(preds, batch_labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += float(loss)
            n_batches += 1

        if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
            val_metrics = _evaluate_deepfm(model, val_data)
            log.info(
                "deepfm_epoch",
                epoch=epoch + 1,
                loss=epoch_loss / max(n_batches, 1),
                val_auc=val_metrics.get("auc", 0.0),
            )
            if val_metrics.get("auc", 0.0) > best_auc:
                best_auc = val_metrics.get("auc", 0.0)
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    test_data = load_feature_data(dataset_path, split="test", feature_path=feature_path)
    test_metrics = _evaluate_deepfm(model, test_data)

    if output_dir is not None:
        _save_deepfm(
            model, output_dir, train_data.field_dims, embedding_dim, mlp_dims, test_metrics, seed
        )
        save_id_maps(train_data.user_id_map, train_data.item_id_map, output_dir)

    return test_metrics


def _evaluate_deepfm(model: DeepFMModel, data: FeatureData) -> dict[str, float]:
    """Evaluate DeepFM on AUC, logloss, and ranking metrics."""
    model.eval()
    with torch.no_grad():
        preds = model(data.features).numpy()

    binary = (data.labels > 0).numpy().astype(np.int_)

    metrics: dict[str, float] = {}

    if len(np.unique(binary)) > 1:
        metrics["auc"] = float(roc_auc_score(binary, preds))
        metrics["logloss"] = float(log_loss(binary, np.clip(preds, 1e-7, 1 - 1e-7)))

    unique_users = data.user_ids.unique()
    recalls: list[float] = []
    ndcgs: list[float] = []

    for uid in unique_users:
        mask = data.user_ids == uid
        u_labels = data.labels[mask]
        u_preds_t = torch.from_numpy(preds)[mask]

        if u_labels.sum() == 0:
            continue

        y_true: NDArray[np.int_] = (u_labels > 0).numpy().astype(np.int_)
        y_pred: NDArray[np.float64] = u_preds_t.numpy().astype(np.float64)

        recalls.append(recall_at_k(y_true=y_true, y_pred=y_pred, k=10))
        ndcgs.append(ndcg_at_k(y_true=y_true, y_pred=y_pred, k=10))

    metrics["recall@10"] = float(np.mean(recalls)) if recalls else 0.0
    metrics["ndcg@10"] = float(np.mean(ndcgs)) if ndcgs else 0.0

    return metrics


def _save_deepfm(
    model: DeepFMModel,
    output_dir: str,
    field_dims: list[int],
    embedding_dim: int,
    mlp_dims: tuple[int, ...],
    metrics: dict[str, float],
    seed: int,
) -> None:
    """Save DeepFM model artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")

    config = {
        "model_name": "deepfm",
        "field_dims": field_dims,
        "embedding_dim": embedding_dim,
        "mlp_dims": list(mlp_dims),
        "seed": seed,
    }
    with (out / "config.json").open("w") as f:
        json.dump(config, f, indent=2)
    with (out / "metrics.json").open("w") as f:
        json.dump(metrics, f, indent=2)

    log.info("deepfm_saved", output_dir=output_dir, metrics=metrics)


def load_deepfm(model_dir: str) -> DeepFMModel:
    """Load a trained DeepFM model from disk."""
    d = Path(model_dir)
    with (d / "config.json").open() as f:
        config = json.load(f)

    model = DeepFMModel(
        field_dims=list(config["field_dims"]),
        embedding_dim=int(config["embedding_dim"]),
        mlp_dims=tuple(int(x) for x in config["mlp_dims"]),
    )
    state = torch.load(d / "model.pt", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model
