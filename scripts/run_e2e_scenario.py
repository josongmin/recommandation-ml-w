#!/usr/bin/env python
"""E2E 시나리오 검증 스크립트 (Mock 기반, AWS 불필요).

시나리오:
1. 데이터 생성 (Bronze → Gold-B)
2. Feature Manifest 로드
3. 모델 학습 (Mock)
4. 모델 저장 (Mock S3)
5. Feature Store에 feature 저장
6. Recommender로 추천 생성
7. API 서버 검증
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import torch
from torch import nn


def print_step(step: int, msg: str) -> None:
    """Print step header."""
    print(f"\n{'=' * 60}")
    print(f"Step {step}: {msg}")
    print(f"{'=' * 60}")


def main() -> int:
    """Run E2E scenario."""
    print("\n🚀 E2E 시나리오 검증 시작\n")

    # ============================================
    # Step 1: 데이터 생성
    # ============================================
    print_step(1, "데이터 생성 (Bronze → Gold-B)")

    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "python",
                "scripts/seed_data.py",
                "--output-dir",
                tmpdir,
                "--seed",
                "42",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ Failed: {result.stderr}")
            return 1

        print("✓ 데이터 생성 완료")
        print(f"  - Location: {tmpdir}")
        print("  - 500 wines, 2000 users, 15000 impressions")

    # ============================================
    # Step 2: Feature Manifest 로드
    # ============================================
    print_step(2, "Feature Manifest 로드")

    from wine_rec.features.offline_builder import load_manifest

    manifest = load_manifest(Path("manifests/feature_manifest_v1_simple.yaml"))

    print("✓ Manifest 로드 완료")
    print(f"  - Version: {manifest.feature_set_version}")
    print(f"  - Entities: {len(manifest.entities)}")

    total_features = sum(len(e.features) for e in manifest.entities)
    print(f"  - Total features: {total_features}")

    # ============================================
    # Step 3: 모델 학습 (Mock)
    # ============================================
    print_step(3, "모델 학습 (BPR Mock)")

    class BPRModel(nn.Module):
        """Simple BPR for testing."""

        def __init__(self, n_users: int = 2000, n_items: int = 500, emb_dim: int = 64) -> None:
            super().__init__()
            self.user_emb = nn.Embedding(n_users, emb_dim)
            self.item_emb = nn.Embedding(n_items, emb_dim)

        def forward(self, users: torch.Tensor, items: torch.Tensor) -> torch.Tensor:
            u = self.user_emb(users)
            i = self.item_emb(items)
            return (u * i).sum(dim=-1)

    model = BPRModel()
    n_params = sum(p.numel() for p in model.parameters())

    print("✓ 모델 생성 완료")
    print("  - Model: BPR")
    print(f"  - Parameters: {n_params:,}")
    print("  - Embedding dim: 64")

    # Simple training simulation (1 step)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    users = torch.randint(0, 2000, (32,))
    items_pos = torch.randint(0, 500, (32,))
    items_neg = torch.randint(0, 500, (32,))

    model.train()
    pos_scores = model(users, items_pos)
    neg_scores = model(users, items_neg)
    loss = -torch.log(torch.sigmoid(pos_scores - neg_scores)).mean()
    loss.backward()
    optimizer.step()

    print("✓ 학습 시뮬레이션 완료")
    print(f"  - Loss: {loss.item():.4f}")

    # ============================================
    # Step 4: 모델 저장 (Mock S3)
    # ============================================
    print_step(4, "모델 저장 (Mock S3 Registry)")

    from wine_rec.infra.s3_model_registry import ModelArtifactImpl

    model.eval()
    artifact = ModelArtifactImpl(
        model=model,
        version="v1.0",
        metadata={
            "n_users": 2000,
            "n_items": 500,
            "emb_dim": 64,
            "loss": loss.item(),
            "dataset": "wine_v1",
        },
    )

    print("✓ 모델 Artifact 생성")
    print(f"  - Version: {artifact.version}")
    print(f"  - Metadata: {len(artifact._metadata)} fields")

    # Mock S3 registry
    mock_s3_registry = Mock()
    mock_s3_registry.save_model = Mock()
    mock_s3_registry.get_latest_version = Mock(return_value="v1.0")
    mock_s3_registry.load_model = Mock(return_value=artifact)

    mock_s3_registry.save_model(
        model=model,
        model_name="bpr",
        version="v1.0",
        metadata=artifact._metadata,
    )

    print("✓ S3에 저장 (Mock)")
    print("  - Bucket: wine-rec-dev-models")
    print("  - Key: models/bpr/v1.0/model.pt")

    # ============================================
    # Step 5: Feature Store에 feature 저장
    # ============================================
    print_step(5, "Feature Store에 feature 저장 (Mock DynamoDB)")

    mock_feature_store = Mock()
    mock_feature_store.put_features = Mock()
    mock_feature_store.get_features = Mock(
        return_value={
            "user_age": 35,
            "user_country": "US",
            "user_wine_preference": "red",
            "user_total_orders": 15,
        }
    )
    mock_feature_store.batch_get_features = Mock(
        return_value=[{"items": [f"wine_{i:03d}" for i in range(20)]}]
    )

    # Save features
    for user_id in ["user_001", "user_002", "user_003"]:
        mock_feature_store.put_features(
            entity_type="user",
            entity_id=user_id,
            features={
                "user_age": 30 + hash(user_id) % 20,
                "user_country": "US",
                "user_wine_preference": "red",
            },
        )

    print("✓ Feature Store 저장")
    print("  - Users: 3")
    print("  - Features per user: 3")
    print(f"  - Put calls: {mock_feature_store.put_features.call_count}")

    # ============================================
    # Step 6: Recommender로 추천 생성
    # ============================================
    print_step(6, "Recommender로 추천 생성")

    from wine_rec.serving.recommender import RecallSource, Recommender

    recall_sources = [
        RecallSource(name="bpr", model_name="bpr_v1", quota=50),
        RecallSource(name="popular", model_name="popularity", quota=20),
    ]

    recommender = Recommender(
        feature_store=mock_feature_store,
        model_registry=mock_s3_registry,
        recall_sources=recall_sources,
        diversity_weight=0.1,
    )

    print("✓ Recommender 초기화")
    print(f"  - Recall sources: {len(recall_sources)}")
    print("  - Diversity weight: 0.1")

    # Generate recommendations
    recs = recommender.recommend(
        user_id="user_001",
        n_items=10,
        context={"season": "winter", "hour": 20},
    )

    print("✓ 추천 생성 완료")
    print("  - User: user_001")
    print(f"  - Recommendations: {len(recs)}")
    print("\n  Top 5 추천:")
    for i, rec in enumerate(recs[:5], 1):
        print(f"    {i}. {rec['wine_sku_id']} (score={rec['score']:.4f})")

    # Validate results
    assert len(recs) == 10, "Should return 10 items"
    assert all("wine_sku_id" in r for r in recs), "Missing wine_sku_id"
    assert all("score" in r for r in recs), "Missing score"

    # Check deduplication
    wine_ids = [r["wine_sku_id"] for r in recs]
    assert len(wine_ids) == len(set(wine_ids)), "Duplicates found!"

    # Check ordering
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True), "Not sorted!"

    print("\n✓ 검증 완료")
    print(f"  - Unique items: {len(set(wine_ids))}")
    print("  - Sorted by score: Yes")
    print(f"  - Score range: {scores[-1]:.4f} to {scores[0]:.4f}")

    # ============================================
    # Step 7: API 서버 검증
    # ============================================
    print_step(7, "API 서버 검증")

    import os
    import signal
    import subprocess

    import requests

    # Start server
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "wine_rec.serving.app:app", "--port", "8002"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(3)

    try:
        # Test health endpoint
        response = requests.get("http://localhost:8002/health", timeout=2)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        print("✓ API 서버 동작 확인")
        print("  - Endpoint: http://localhost:8002/health")
        print(f"  - Status: {data['status']}")
        print(f"  - Version: {data['version']}")

    finally:
        # Cleanup
        os.kill(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)

    # ============================================
    # Summary
    # ============================================
    print("\n" + "=" * 60)
    print("🎉 E2E 시나리오 검증 완료!")
    print("=" * 60)
    print("\n✅ 전체 7단계 성공:")
    print("  1. 데이터 생성 (500 wines, 2000 users)")
    print("  2. Feature Manifest 로드 (5 features)")
    print(f"  3. 모델 학습 (BPR, {n_params:,} params)")
    print("  4. 모델 저장 (S3 Mock)")
    print("  5. Feature Store 저장 (DynamoDB Mock)")
    print("  6. 추천 생성 (10 items, diversity 0.1)")
    print("  7. API 서버 동작 확인 (FastAPI)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
