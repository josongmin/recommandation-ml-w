"""Tests for Two-Tower (DSSM) model."""

from __future__ import annotations

import torch

from wine_rec.models.baselines.two_tower import TwoTowerModel


class TestTwoTowerModel:
    def test_encode_user_shape(self):
        model = TwoTowerModel(n_users=10, n_items=20, embedding_dim=32, hidden_dims=(64, 32))
        users = torch.tensor([0, 1, 2])
        emb = model.encode_user(users)
        assert emb.shape == (3, 32)

    def test_encode_item_shape(self):
        model = TwoTowerModel(n_users=10, n_items=20, embedding_dim=32, hidden_dims=(64, 32))
        items = torch.tensor([5, 10, 15])
        emb = model.encode_item(items)
        assert emb.shape == (3, 32)

    def test_l2_normalized(self):
        """Embeddings should be L2 normalized."""
        model = TwoTowerModel(n_users=10, n_items=20, embedding_dim=32, hidden_dims=(64, 32))
        users = torch.tensor([0, 1, 2])
        emb = model.encode_user(users)
        norms = emb.norm(dim=1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    def test_forward_scores(self):
        model = TwoTowerModel(n_users=10, n_items=20, embedding_dim=32, hidden_dims=(64, 32))
        users = torch.tensor([0, 1])
        items = torch.tensor([5, 10])
        scores = model(users, items)
        assert scores.shape == (2,)
        # cosine similarity should be in [-1, 1]
        assert (scores >= -1.0).all()
        assert (scores <= 1.0).all()

    def test_predict_all_shape(self):
        model = TwoTowerModel(n_users=10, n_items=20, embedding_dim=32, hidden_dims=(64, 32))
        users = torch.tensor([0, 1])
        scores = model.predict_all(users)
        assert scores.shape == (2, 20)

    def test_training_step(self):
        """In-batch negative loss should be computable and backprop-able."""
        model = TwoTowerModel(n_users=10, n_items=20, embedding_dim=16, hidden_dims=(32, 16))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

        users = torch.tensor([0, 1, 2, 3])
        items = torch.tensor([5, 10, 15, 3])

        u_emb = model.encode_user(users)
        i_emb = model.encode_item(items)
        logits = u_emb @ i_emb.T / 0.1
        labels = torch.arange(4)
        loss = torch.nn.functional.cross_entropy(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        assert loss.item() > 0
