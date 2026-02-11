"""Hyperparameter tuning with Optuna.

SOTA 프랙티스: Bayesian optimization for hyperparameter search.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import optuna

from wine_rec.common.logging import get_logger
from wine_rec.models.baselines.bpr import train_bpr
from wine_rec.models.baselines.lightgcn import train_lightgcn
from wine_rec.models.baselines.two_tower import train_two_tower


if TYPE_CHECKING:
    from optuna import Trial

log = get_logger(__name__)


def objective_bpr(
    trial: Trial,
    *,
    dataset_path: str,
    device: str = "cpu",
    epochs: int = 20,
) -> float:
    """Optuna objective for BPR hyperparameter tuning.

    Args:
        trial: Optuna trial
        dataset_path: Path to training_examples_v1
        device: cpu or cuda
        epochs: Number of training epochs (fixed)

    Returns:
        Validation NDCG@10 (maximize)
    """
    # Suggest hyperparameters
    embedding_dim = trial.suggest_categorical("embedding_dim", [32, 64, 128, 256])
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
    weight_decay = trial.suggest_float("weight_decay", 1e-7, 1e-3, log=True)
    batch_size = trial.suggest_categorical("batch_size", [256, 512, 1024, 2048])

    # Train model
    log.info(
        "trial_start",
        trial_number=trial.number,
        embedding_dim=embedding_dim,
        lr=learning_rate,
        weight_decay=weight_decay,
    )

    metrics = train_bpr(
        dataset_path=dataset_path,
        epochs=epochs,
        learning_rate=learning_rate,
        embedding_dim=embedding_dim,
        weight_decay=weight_decay,
        batch_size=batch_size,
        device=device,
        output_dir=None,  # Don't save intermediate checkpoints
    )

    val_ndcg = metrics["val_ndcg@10"]
    log.info("trial_complete", trial_number=trial.number, val_ndcg=val_ndcg)

    return val_ndcg


def objective_lightgcn(
    trial: Trial,
    *,
    dataset_path: str,
    device: str = "cpu",
    epochs: int = 20,
) -> float:
    """Optuna objective for LightGCN hyperparameter tuning."""
    # Suggest hyperparameters
    embedding_dim = trial.suggest_categorical("embedding_dim", [64, 128, 256])
    n_layers = trial.suggest_int("n_layers", 2, 5)
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
    weight_decay = trial.suggest_float("weight_decay", 1e-7, 1e-3, log=True)
    batch_size = trial.suggest_categorical("batch_size", [512, 1024, 2048])

    log.info(
        "trial_start",
        trial_number=trial.number,
        n_layers=n_layers,
        embedding_dim=embedding_dim,
    )

    metrics = train_lightgcn(
        dataset_path=dataset_path,
        epochs=epochs,
        learning_rate=learning_rate,
        embedding_dim=embedding_dim,
        n_layers=n_layers,
        weight_decay=weight_decay,
        batch_size=batch_size,
        device=device,
        output_dir=None,
    )

    val_ndcg = metrics["val_ndcg@10"]
    log.info("trial_complete", trial_number=trial.number, val_ndcg=val_ndcg)

    return val_ndcg


def objective_two_tower(
    trial: Trial,
    *,
    dataset_path: str,
    device: str = "cpu",
    epochs: int = 20,
) -> float:
    """Optuna objective for Two-Tower hyperparameter tuning."""
    # Suggest hyperparameters
    embedding_dim = trial.suggest_categorical("embedding_dim", [64, 128, 256])
    hidden_dim1 = trial.suggest_categorical("hidden_dim1", [128, 256, 512])
    hidden_dim2 = trial.suggest_categorical("hidden_dim2", [64, 128, 256])
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
    weight_decay = trial.suggest_float("weight_decay", 1e-7, 1e-3, log=True)
    temperature = trial.suggest_float("temperature", 0.05, 0.2)

    hidden_dims = (hidden_dim1, hidden_dim2)

    log.info(
        "trial_start",
        trial_number=trial.number,
        embedding_dim=embedding_dim,
        hidden_dims=hidden_dims,
    )

    metrics = train_two_tower(
        dataset_path=dataset_path,
        epochs=epochs,
        learning_rate=learning_rate,
        embedding_dim=embedding_dim,
        hidden_dims=hidden_dims,
        weight_decay=weight_decay,
        temperature=temperature,
        device=device,
        output_dir=None,
    )

    val_ndcg = metrics["val_ndcg@10"]
    log.info("trial_complete", trial_number=trial.number, val_ndcg=val_ndcg)

    return val_ndcg


def run_tuning(
    *,
    model_type: str,
    dataset_path: str,
    n_trials: int = 50,
    device: str = "cpu",
    study_name: str | None = None,
    storage: str | None = None,
) -> dict[str, Any]:
    """Run hyperparameter tuning with Optuna.

    Args:
        model_type: bpr|lightgcn|two_tower
        dataset_path: Path to training_examples_v1
        n_trials: Number of trials
        device: cpu or cuda
        study_name: Optuna study name (for persistence)
        storage: Optuna storage URL (sqlite:///optuna.db)

    Returns:
        dict with best_params, best_value, study
    """
    # Select objective function
    if model_type == "bpr":
        objective_fn = objective_bpr
    elif model_type == "lightgcn":
        objective_fn = objective_lightgcn
    elif model_type == "two_tower":
        objective_fn = objective_two_tower
    else:
        msg = f"Unknown model_type: {model_type}"
        raise ValueError(msg)

    # Create study
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",  # Maximize NDCG@10
        load_if_exists=True,
    )

    # Optimize
    log.info("tuning_start", model_type=model_type, n_trials=n_trials)

    study.optimize(
        lambda trial: objective_fn(trial, dataset_path=dataset_path, device=device),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    log.info(
        "tuning_complete",
        best_params=study.best_params,
        best_value=study.best_value,
    )

    return {
        "best_params": study.best_params,
        "best_value": study.best_value,
        "study": study,
    }


def visualize_optimization_history(study: optuna.Study, output_path: str) -> None:
    """Plot optimization history (requires matplotlib)."""
    try:
        import matplotlib.pyplot as plt
        from optuna.visualization.matplotlib import (
            plot_optimization_history,
            plot_param_importances,
        )
    except ImportError:
        log.warning("matplotlib_not_installed", msg="Skipping visualization")
        return

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Optimization history
    fig = plot_optimization_history(study)
    fig.savefig(output_dir / "optimization_history.png")
    plt.close(fig)

    # Parameter importances
    fig = plot_param_importances(study)
    fig.savefig(output_dir / "param_importances.png")
    plt.close(fig)

    log.info("visualization_saved", output_dir=str(output_dir))
