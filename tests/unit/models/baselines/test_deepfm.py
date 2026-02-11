"""Tests for DeepFM ranking model."""

from __future__ import annotations

import torch

from wine_rec.models.baselines.deepfm import DeepFMModel, _DNNLayer, _FMLayer


class TestDeepFMModel:
    def test_forward_shape(self):
        model = DeepFMModel(field_dims=[10, 20], embedding_dim=8, mlp_dims=(32, 16))
        features = torch.tensor([[0, 5], [3, 15]], dtype=torch.float32)
        out = model(features)
        assert out.shape == (2,)

    def test_output_range(self):
        """Sigmoid output should be in (0, 1)."""
        model = DeepFMModel(field_dims=[10, 20], embedding_dim=8, mlp_dims=(32, 16))
        features = torch.tensor([[0, 5], [3, 15], [9, 19]], dtype=torch.float32)
        out = model(features)
        assert (out > 0).all()
        assert (out < 1).all()

    def test_predict_scores_no_grad(self):
        model = DeepFMModel(field_dims=[10, 20], embedding_dim=8, mlp_dims=(32, 16))
        features = torch.tensor([[0, 5]], dtype=torch.float32)
        scores = model.predict_scores(features)
        assert scores.shape == (1,)
        assert not scores.requires_grad

    def test_multi_field(self):
        """Should work with 3+ fields."""
        model = DeepFMModel(field_dims=[5, 10, 3], embedding_dim=4, mlp_dims=(16, 8))
        features = torch.tensor([[1, 5, 2], [0, 9, 0]], dtype=torch.float32)
        out = model(features)
        assert out.shape == (2,)

    def test_bce_loss_backprop(self):
        """BCE loss should be computable and backprop-able."""
        model = DeepFMModel(field_dims=[10, 20], embedding_dim=8, mlp_dims=(32, 16))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        criterion = torch.nn.BCELoss()

        features = torch.tensor([[0, 5], [3, 15], [7, 10], [2, 8]], dtype=torch.float32)
        labels = torch.tensor([1.0, 0.0, 1.0, 0.0])

        preds = model(features)
        loss = criterion(preds, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        assert loss.item() > 0

    def test_fm_layer_interaction(self):
        """FM layer should capture 2nd-order interactions."""
        fm = _FMLayer()
        # [B=2, n_fields=3, D=4]
        emb = torch.randn(2, 3, 4)
        out = fm(emb)
        assert out.shape == (2, 1)

    def test_dnn_layer_shape(self):
        dnn = _DNNLayer(input_dim=32, hidden_dims=(16, 8))
        x = torch.randn(4, 32)
        out = dnn(x)
        assert out.shape == (4, 1)
