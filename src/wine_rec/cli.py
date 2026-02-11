"""CLI entry point (RFC-EXEC-PLAN-014 §7).

Commands:
    wine-rec train     -- dispatch to trainer
    wine-rec evaluate  -- run benchmark suite and export report
    wine-rec serve     -- start FastAPI dev server
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from wine_rec.common.logging import get_logger, setup_logging


log = get_logger(__name__)


# ------------------------------------------------------------------
# Subcommand handlers (lazy imports for fast startup)
# ------------------------------------------------------------------


def _cmd_train(args: argparse.Namespace) -> None:
    """Handle ``wine-rec train``."""
    from wine_rec.models.training.trainer import train  # noqa: PLC0415

    metrics = train(
        model_name=args.model,
        dataset_version=args.dataset_version,
        feature_set_version=args.feature_set_version,
        hyperparams={
            "dataset_path": args.dataset_path,
            "epochs": args.epochs,
        },
        output_dir=args.output_dir,
        seed=args.seed,
    )
    log.info("train_complete", metrics=metrics)


def _cmd_evaluate(args: argparse.Namespace) -> None:
    """Handle ``wine-rec evaluate``."""
    from wine_rec.models.evaluation.evaluator import run_benchmark_suite  # noqa: PLC0415

    results = run_benchmark_suite(
        model_name=args.model,
        model_version=args.model_version,
        dataset_version=args.dataset_version,
    )
    log.info("evaluate_complete", n_tracks=len(results))

    if args.output_dir:
        from wine_rec.models.evaluation.report import build_report, export_report  # noqa: PLC0415

        report = build_report(benchmark_results=results)
        path = export_report(report, output_dir=args.output_dir)
        log.info("report_saved", path=str(path))


def _cmd_serve(args: argparse.Namespace) -> None:
    """Handle ``wine-rec serve``."""
    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        log.error("uvicorn_not_installed")
        sys.exit(1)

    uvicorn.run(
        "wine_rec.serving.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


# ------------------------------------------------------------------
# Parser
# ------------------------------------------------------------------

_SUPPORTED_MODELS = ("bpr", "two_tower", "lightgcn", "deepfm")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="wine-rec",
        description="High-End Wine Recommendation System CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # -- train --
    train_p = sub.add_parser("train", help="Train a model")
    train_p.add_argument("--model", required=True, choices=_SUPPORTED_MODELS)
    train_p.add_argument("--dataset-path", required=True)
    train_p.add_argument("--dataset-version", default="ds_v1")
    train_p.add_argument("--feature-set-version", default="fs_v1")
    train_p.add_argument("--output-dir", default="output/models")
    train_p.add_argument("--epochs", type=int, default=50)
    train_p.add_argument("--seed", type=int, default=42)

    # -- evaluate --
    eval_p = sub.add_parser("evaluate", help="Run benchmark suite")
    eval_p.add_argument("--model", required=True)
    eval_p.add_argument("--model-version", default="v1")
    eval_p.add_argument("--dataset-version", default="ds_v1")
    eval_p.add_argument("--output-dir", default="")

    # -- serve --
    serve_p = sub.add_parser("serve", help="Start FastAPI dev server")
    serve_p.add_argument("--host", default="0.0.0.0")  # noqa: S104
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--reload", action="store_true", default=True)

    return parser


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "train": _cmd_train,
    "evaluate": _cmd_evaluate,
    "serve": _cmd_serve,
}


def main() -> None:
    """wine-rec CLI entry point."""
    setup_logging(log_format="console")
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)
