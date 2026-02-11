"""Tests for LightGCN graph-based CF model."""

from __future__ import annotations

import torch

from wine_rec.models.baselines.lightgcn import LightGCNModel


def _make_adj(n_users: int, n_items: int) -> torch.Tensor:
    """Create a simple normalized adjacency for testing."""
    n = n_users + n_items
    # connect user 0 -> item 0, user 1 -> item 1
    rows = []
    cols = []
    for u in range(min(n_users, n_items)):
        item_idx = n_users + u
        rows.extend([u, item_idx])
        cols.extend([item_idx, u])

    row = torch.tensor(rows, dtype=torch.int64)
    col = torch.tensor(cols, dtype=torch.int64)
    values = torch.ones(len(rows), dtype=torch.float32) * 0.5  # simplified norm

    return torch.sparse_coo_tensor(torch.stack([row, col]), values, size=(n, n)).coalesce()


class TestLightGCNModel:
    def test_forward_shapes(self):
        model = LightGCNModel(n_users=5, n_items=10, embedding_dim=16, num_layers=2)
        adj = _make_adj(5, 10)
        user_emb, item_emb = model(adj)

        assert user_emb.shape == (5, 16)
        assert item_emb.shape == (10, 16)

    def test_predict_scores(self):
        model = LightGCNModel(n_users=5, n_items=10, embedding_dim=16, num_layers=2)
        adj = _make_adj(5, 10)
        user_emb, item_emb = model(adj)

        users = torch.tensor([0, 1])
        items = torch.tensor([3, 7])
        scores = model.predict(users, items, user_emb, item_emb)
        assert scores.shape == (2,)

    def test_num_layers_effect(self):
        """More layers should propagate info further."""
        adj = _make_adj(5, 10)

        model_1 = LightGCNModel(n_users=5, n_items=10, embedding_dim=16, num_layers=1)
        model_3 = LightGCNModel(n_users=5, n_items=10, embedding_dim=16, num_layers=3)

        # share initial embeddings
        model_3.user_embedding.weight.data = model_1.user_embedding.weight.data.clone()
        model_3.item_embedding.weight.data = model_1.item_embedding.weight.data.clone()

        u1, _ = model_1(adj)
        u3, _ = model_3(adj)

        # embeddings should differ due to different layer counts
        assert not torch.allclose(u1, u3)

    def test_bpr_loss_positive(self):
        model = LightGCNModel(n_users=5, n_items=10, embedding_dim=16, num_layers=2)
        adj = _make_adj(5, 10)
        user_emb, item_emb = model(adj)

        users = torch.tensor([0, 1, 2])
        pos = torch.tensor([3, 5, 7])
        neg = torch.tensor([4, 6, 8])

        loss = LightGCNModel.bpr_loss(user_emb, item_emb, users, pos, neg)
        assert loss.item() > 0

    def test_training_step(self):
        """Single optimization step should be computable."""
        model = LightGCNModel(n_users=5, n_items=10, embedding_dim=16, num_layers=2)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        adj = _make_adj(5, 10)

        user_emb, item_emb = model(adj)
        users = torch.tensor([0, 1])
        pos = torch.tensor([3, 5])
        neg = torch.tensor([4, 6])

        loss = LightGCNModel.bpr_loss(user_emb, item_emb, users, pos, neg)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        assert loss.item() > 0
