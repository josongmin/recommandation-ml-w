#!/usr/bin/env python3
"""로컬 환경에서 빠른 모델 학습"""

import sys
from pathlib import Path


# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wine_rec.models.training.trainer import train


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "two_tower"

    print(f"🧠 Training {model_name} model locally...")

    # 시드 데이터가 없으면 생성
    dataset_path = Path("data/training/dataset_v1.parquet")
    if not dataset_path.exists():
        print("⚠️  Dataset not found. Run: python scripts/seed_data.py first")
        return

    # 학습 실행
    metrics = train(
        model_name=model_name,
        dataset_version="v1",
        feature_set_version="v1",
        hyperparams={
            "dataset_path": str(dataset_path),
            "epochs": 5,  # 로컬 테스트용 적은 epoch
            "embedding_dim": 32,  # 로컬 테스트용 작은 dim
            "learning_rate": 0.001,
            "batch_size": 512,
        },
        output_dir=f"models/{model_name}_local/",
        seed=42,
    )

    print("\n✅ Training complete!")
    print(f"📊 Metrics: {metrics}")
    print(f"📁 Model saved to: models/{model_name}_local/")


if __name__ == "__main__":
    main()
