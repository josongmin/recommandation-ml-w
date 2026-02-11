"""Tests for training dispatcher."""

from __future__ import annotations

import pytest

from wine_rec.models.training.trainer import _SUPPORTED_MODELS, train


class TestTrainerValidation:
    def test_rejects_unknown_model(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown model"):
            train(
                model_name="unknown",
                dataset_version="ds_v1",
                feature_set_version="fs_v1",
                hyperparams={"dataset_path": str(tmp_path)},
                output_dir=str(tmp_path / "out"),
            )

    def test_rejects_missing_dataset_path(self, tmp_path):
        with pytest.raises(ValueError, match="dataset_path"):
            train(
                model_name="bpr",
                dataset_version="ds_v1",
                feature_set_version="fs_v1",
                hyperparams={},
                output_dir=str(tmp_path / "out"),
            )

    def test_supported_models(self):
        assert "bpr" in _SUPPORTED_MODELS
        assert "two_tower" in _SUPPORTED_MODELS
        assert "lightgcn" in _SUPPORTED_MODELS
        assert "deepfm" in _SUPPORTED_MODELS
