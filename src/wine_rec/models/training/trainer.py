"""Universal training dispatcher (RFC-INFRA-IMPL-013 §1-5).

Dispatches to baseline model-specific training functions.
Saves model artifact + config + metrics to output_dir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from wine_rec.common.logging import get_logger
from wine_rec.models.baselines.bpr import train_bpr
from wine_rec.models.baselines.deepfm import train_deepfm
from wine_rec.models.baselines.lightgcn import train_lightgcn
from wine_rec.models.baselines.two_tower import train_two_tower


log = get_logger(__name__)

_SUPPORTED_MODELS = frozenset({"bpr", "two_tower", "lightgcn", "deepfm"})


def train(
    *,
    model_name: str,
    dataset_version: str,
    feature_set_version: str,
    hyperparams: dict[str, Any],
    output_dir: str,
    seed: int = 42,
) -> dict[str, float]:
    """Universal training entry point.

    Dispatches to the appropriate baseline model.
    Saves model artifact + config to output_dir.

    Args:
        model_name: One of "bpr", "two_tower", "lightgcn", "deepfm".
        dataset_version: Version string for the training dataset.
        feature_set_version: Feature manifest version.
        hyperparams: Model-specific hyperparameters.
            Required: "dataset_path" -- path to training_examples parquet.
            Optional (model-dependent): epochs, learning_rate, embedding_dim, etc.
        output_dir: Directory to save model artifacts.
        seed: Random seed for reproducibility.

    Returns:
        Evaluation metrics dict.
    """
    if model_name not in _SUPPORTED_MODELS:
        msg = f"Unknown model: {model_name}. Supported: {sorted(_SUPPORTED_MODELS)}"
        raise ValueError(msg)

    _set_seeds(seed)

    dataset_path = str(hyperparams.get("dataset_path", ""))
    if not dataset_path:
        msg = "hyperparams must include 'dataset_path'"
        raise ValueError(msg)

    log.info(
        "training_start",
        model_name=model_name,
        dataset_version=dataset_version,
        feature_set_version=feature_set_version,
        seed=seed,
    )

    metrics = _dispatch_train(model_name, dataset_path, hyperparams, output_dir, seed)

    meta = {
        "model_name": model_name,
        "dataset_version": dataset_version,
        "feature_set_version": feature_set_version,
        "seed": seed,
        "metrics": metrics,
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "training_meta.json").open("w") as f:
        json.dump(meta, f, indent=2)

    log.info("training_complete", model_name=model_name, metrics=metrics)
    return metrics


def _set_seeds(seed: int) -> None:
    """Set deterministic seeds for all RNGs."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _dispatch_train(
    model_name: str,
    dataset_path: str,
    hyperparams: dict[str, Any],
    output_dir: str,
    seed: int,
) -> dict[str, float]:
    """Dispatch to model-specific training function."""
    if model_name == "bpr":
        return train_bpr(
            dataset_path=dataset_path,
            epochs=int(hyperparams.get("epochs", 50)),
            learning_rate=float(hyperparams.get("learning_rate", 0.001)),
            embedding_dim=int(hyperparams.get("embedding_dim", 64)),
            weight_decay=float(hyperparams.get("weight_decay", 1e-5)),
            n_neg=int(hyperparams.get("n_neg", 1)),
            seed=seed,
            output_dir=output_dir,
        )

    if model_name == "two_tower":
        hidden_dims_raw = hyperparams.get("hidden_dims", (256, 128))
        hidden_dims = (
            tuple(int(x) for x in hidden_dims_raw)
            if isinstance(hidden_dims_raw, (list, tuple))
            else (256, 128)
        )
        return train_two_tower(
            dataset_path=dataset_path,
            epochs=int(hyperparams.get("epochs", 30)),
            learning_rate=float(hyperparams.get("learning_rate", 0.001)),
            embedding_dim=int(hyperparams.get("embedding_dim", 128)),
            hidden_dims=hidden_dims,
            temperature=float(hyperparams.get("temperature", 0.1)),
            seed=seed,
            output_dir=output_dir,
        )

    if model_name == "lightgcn":
        return train_lightgcn(
            dataset_path=dataset_path,
            epochs=int(hyperparams.get("epochs", 100)),
            learning_rate=float(hyperparams.get("learning_rate", 0.001)),
            embedding_dim=int(hyperparams.get("embedding_dim", 64)),
            num_layers=int(hyperparams.get("num_layers", 3)),
            reg_weight=float(hyperparams.get("reg_weight", 1e-5)),
            n_neg=int(hyperparams.get("n_neg", 1)),
            seed=seed,
            output_dir=output_dir,
        )

    # deepfm
    mlp_dims_raw = hyperparams.get("mlp_dims", (256, 128))
    mlp_dims = (
        tuple(int(x) for x in mlp_dims_raw)
        if isinstance(mlp_dims_raw, (list, tuple))
        else (256, 128)
    )
    return train_deepfm(
        dataset_path=dataset_path,
        feature_path=str(hyperparams["feature_path"]) if "feature_path" in hyperparams else None,
        epochs=int(hyperparams.get("epochs", 30)),
        learning_rate=float(hyperparams.get("learning_rate", 0.001)),
        embedding_dim=int(hyperparams.get("embedding_dim", 16)),
        mlp_dims=mlp_dims,
        dropout=float(hyperparams.get("dropout", 0.1)),
        batch_size=int(hyperparams.get("batch_size", 256)),
        seed=seed,
        output_dir=output_dir,
    )
