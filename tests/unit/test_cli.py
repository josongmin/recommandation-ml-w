"""Tests for CLI entry point."""

from __future__ import annotations

from wine_rec.cli import _build_parser


class TestBuildParser:
    def test_train_command_parses(self):
        parser = _build_parser()
        args = parser.parse_args(["train", "--model", "bpr", "--dataset-path", "./data/train"])
        assert args.command == "train"
        assert args.model == "bpr"
        assert args.dataset_path == "./data/train"
        assert args.epochs == 50
        assert args.seed == 42

    def test_evaluate_command_parses(self):
        parser = _build_parser()
        args = parser.parse_args(["evaluate", "--model", "bpr"])
        assert args.command == "evaluate"
        assert args.model == "bpr"
        assert args.model_version == "v1"

    def test_serve_command_parses(self):
        parser = _build_parser()
        args = parser.parse_args(["serve", "--port", "9000"])
        assert args.command == "serve"
        assert args.port == 9000

    def test_no_command_returns_none(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.command is None
