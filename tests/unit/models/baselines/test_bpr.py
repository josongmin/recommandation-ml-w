"""Tests for BPR baseline model."""

from __future__ import annotations

import torch

from wine_rec.models.baselines.bpr import BPRModel


class TestBPRModel:
    def test_forward_shapes(self):
        model = BPRModel(n_users=10, n_items=20, embedding_dim=32)
        users = torch.tensor([0, 1, 2])
        pos = torch.tensor([3, 5, 7])
        neg = torch.tensor([4, 6, 8])

        pos_scores, neg_scores = model(users, pos, neg)
        assert pos_scores.shape == (3,)
        assert neg_scores.shape == (3,)

    def test_predict_shapes(self):
        model = BPRModel(n_users=10, n_items=20, embedding_dim=32)
        users = torch.tensor([0, 1])
        items = torch.tensor([5, 10])
        scores = model.predict(users, items)
        assert scores.shape == (2,)

    def test_predict_all_shapes(self):
        model = BPRModel(n_users=10, n_items=20, embedding_dim=32)
        users = torch.tensor([0, 1, 2])
        scores = model.predict_all(users)
        assert scores.shape == (3, 20)

    def test_bpr_loss_positive(self):
        pos_scores = torch.tensor([2.0, 3.0])
        neg_scores = torch.tensor([0.5, 0.5])
        loss = BPRModel.bpr_loss(pos_scores, neg_scores)
        assert loss.item() > 0

    def test_bpr_loss_decreases_with_margin(self):
        """Larger margin -> lower loss."""
        pos1 = torch.tensor([2.0])
        neg1 = torch.tensor([1.0])
        loss_small = BPRModel.bpr_loss(pos1, neg1)

        pos2 = torch.tensor([5.0])
        neg2 = torch.tensor([1.0])
        loss_large = BPRModel.bpr_loss(pos2, neg2)

        assert loss_large < loss_small

    def test_training_step_reduces_loss(self):
        """A single optimization step should reduce loss."""
        model = BPRModel(n_users=5, n_items=10, embedding_dim=16)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

        users = torch.tensor([0, 1, 2])
        pos = torch.tensor([3, 5, 7])
        neg = torch.tensor([4, 6, 8])

        # initial loss
        pos_s, neg_s = model(users, pos, neg)
        loss0 = BPRModel.bpr_loss(pos_s, neg_s)

        # step
        optimizer.zero_grad()
        loss0.backward()
        optimizer.step()

        # new loss
        pos_s2, neg_s2 = model(users, pos, neg)
        loss1 = BPRModel.bpr_loss(pos_s2, neg_s2)

        assert loss1.item() < loss0.item()

    def test_embedding_init_nonzero(self):
        model = BPRModel(n_users=10, n_items=20, embedding_dim=32)
        assert model.user_embedding.weight.abs().sum() > 0
        assert model.item_embedding.weight.abs().sum() > 0
