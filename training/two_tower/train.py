"""Two-Tower Recommendation Model Training (SOTA implementation)

Architecture:
- User Tower: MLP encoder (user_id → embedding)
- Item Tower: MLP encoder (item_id → embedding)
- Loss: Contrastive learning (in-batch negatives)
- Optimization: AdamW + Cosine Annealing
"""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset


class TwoTowerModel(nn.Module):
    """SOTA Two-Tower Architecture with deep encoders"""

    def __init__(self, num_users, num_items, embedding_dim=128, hidden_dims=[256, 128]):
        super().__init__()
        self.embedding_dim = embedding_dim

        # User Tower
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        user_layers = []
        input_dim = embedding_dim
        for hidden_dim in hidden_dims:
            user_layers.extend(
                [
                    nn.Linear(input_dim, hidden_dim),
                    nn.BatchNorm1d(hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(0.2),
                ]
            )
            input_dim = hidden_dim
        user_layers.append(nn.Linear(input_dim, embedding_dim))
        self.user_tower = nn.Sequential(*user_layers)

        # Item Tower
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        item_layers = []
        input_dim = embedding_dim
        for hidden_dim in hidden_dims:
            item_layers.extend(
                [
                    nn.Linear(input_dim, hidden_dim),
                    nn.BatchNorm1d(hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(0.2),
                ]
            )
            input_dim = hidden_dim
        item_layers.append(nn.Linear(input_dim, embedding_dim))
        self.item_tower = nn.Sequential(*item_layers)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Xavier initialization for better convergence"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, std=0.01)

    def forward(self, user_ids, item_ids):
        """Forward pass through both towers"""
        user_emb = self.user_embedding(user_ids)
        item_emb = self.item_embedding(item_ids)

        user_vec = self.user_tower(user_emb)
        item_vec = self.item_tower(item_emb)

        # L2 normalize for cosine similarity
        user_vec = F.normalize(user_vec, p=2, dim=1)
        item_vec = F.normalize(item_vec, p=2, dim=1)

        return user_vec, item_vec


class RecommendationDataset(Dataset):
    """Dataset for training with in-batch negatives"""

    def __init__(self, df, user2idx, item2idx):
        self.user_ids = torch.tensor([user2idx[u] for u in df["user_id"].values], dtype=torch.long)
        self.item_ids = torch.tensor([item2idx[i] for i in df["item_id"].values], dtype=torch.long)

    def __len__(self):
        return len(self.user_ids)

    def __getitem__(self, idx):
        return self.user_ids[idx], self.item_ids[idx]


def contrastive_loss(user_vecs, item_vecs, temperature=0.07):
    """InfoNCE loss with in-batch negatives (SOTA contrastive learning)"""
    batch_size = user_vecs.size(0)

    # Compute similarity matrix: (batch_size, batch_size)
    logits = torch.matmul(user_vecs, item_vecs.t()) / temperature

    # Labels: diagonal elements are positives
    labels = torch.arange(batch_size, device=logits.device)

    # Cross entropy loss (treats all off-diagonal as negatives)
    loss = F.cross_entropy(logits, labels)
    return loss


def train_epoch(model, dataloader, optimizer, device, temperature=0.07):
    """Train for one epoch"""
    model.train()
    total_loss = 0

    for user_ids, item_ids in dataloader:
        user_ids = user_ids.to(device)
        item_ids = item_ids.to(device)

        # Forward
        user_vecs, item_vecs = model(user_ids, item_ids)

        # Contrastive loss
        loss = contrastive_loss(user_vecs, item_vecs, temperature)

        # Backward
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)


def main():
    parser = argparse.ArgumentParser()

    # Hyperparameters
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=512)
    parser.add_argument("--learning_rate", type=float, default=0.001)
    parser.add_argument("--embedding_dim", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.07)

    # SageMaker paths
    parser.add_argument(
        "--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
    )
    parser.add_argument(
        "--train",
        type=str,
        default=os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training"),
    )
    parser.add_argument(
        "--output-data-dir",
        type=str,
        default=os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output"),
    )

    args = parser.parse_args()

    print("🚀 Starting Two-Tower Training")
    print(f"   Epochs: {args.epochs}")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Learning Rate: {args.learning_rate}")
    print(f"   Embedding Dim: {args.embedding_dim}")
    print()

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"📱 Device: {device}")

    # Load data
    print("📊 Loading training data...")
    train_path = Path(args.train)
    parquet_files = list(train_path.glob("*.parquet"))

    if not parquet_files:
        raise ValueError(f"No parquet files found in {train_path}")

    df = pd.concat([pd.read_parquet(f) for f in parquet_files], ignore_index=True)
    print(f"   Total examples: {len(df):,}")

    # Build vocabularies
    unique_users = df["user_id"].unique()
    unique_items = df["item_id"].unique()

    user2idx = {u: i for i, u in enumerate(unique_users)}
    item2idx = {it: i for i, it in enumerate(unique_items)}

    print(f"   Unique users: {len(user2idx):,}")
    print(f"   Unique items: {len(item2idx):,}")
    print()

    # Dataset & DataLoader
    dataset = RecommendationDataset(df, user2idx, item2idx)
    dataloader = DataLoader(
        dataset, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True
    )

    # Model
    print("🏗️  Building Two-Tower Model...")
    model = TwoTowerModel(
        num_users=len(user2idx),
        num_items=len(item2idx),
        embedding_dim=args.embedding_dim,
        hidden_dims=[256, 128],
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"   Total parameters: {total_params:,}")
    print()

    # Optimizer & Scheduler
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)

    # Training loop
    print("🎯 Training...")
    best_loss = float("inf")

    for epoch in range(args.epochs):
        avg_loss = train_epoch(model, dataloader, optimizer, device, args.temperature)
        scheduler.step()

        print(
            f"   Epoch {epoch+1}/{args.epochs} - Loss: {avg_loss:.4f} - LR: {scheduler.get_last_lr()[0]:.6f}"
        )

        best_loss = min(avg_loss, best_loss)

    print()
    print(f"✅ Training completed! Best Loss: {best_loss:.4f}")

    # Save model
    print("💾 Saving model...")
    model_path = Path(args.model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    # Save model state
    torch.save(model.state_dict(), model_path / "model.pth")

    # Save vocabularies
    with open(model_path / "user2idx.json", "w") as f:
        json.dump(user2idx, f)
    with open(model_path / "item2idx.json", "w") as f:
        json.dump(item2idx, f)

    # Save config
    config = {
        "num_users": len(user2idx),
        "num_items": len(item2idx),
        "embedding_dim": args.embedding_dim,
        "hidden_dims": [256, 128],
        "best_loss": best_loss,
    }
    with open(model_path / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    print(f"   Model saved to: {model_path}")
    print("🎉 Done!")


if __name__ == "__main__":
    main()
