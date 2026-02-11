#!/usr/bin/env bash
# Quick training script

set -euo pipefail

MODEL=${1:-"two_tower"}
DATASET=${2:-"v1"}

echo "🚀 Starting training pipeline for $MODEL..."

# 1. Generate seed data
echo "📊 Step 1/5: Generating seed data..."
python scripts/seed_data.py

# 2. Upload to S3
echo "☁️  Step 2/5: Uploading to S3..."
aws s3 cp data/seed/ s3://rec-ml-dev-data/bronze/dt=$(date +%Y-%m-%d)/ --recursive

# 3. Trigger ETL
echo "⚙️  Step 3/5: Running ETL pipeline..."
EXECUTION_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-northeast-2:058264332540:stateMachine:rec-ml-dev-daily-pipeline \
  --input "{\"dt\":\"$(date +%Y-%m-%d)\"}" \
  --region ap-northeast-2 \
  --query 'executionArn' --output text)

echo "Waiting for ETL completion..."
aws stepfunctions describe-execution \
  --execution-arn "$EXECUTION_ARN" \
  --region ap-northeast-2 \
  --query 'status' --output text

# 4. Build dataset
echo "📦 Step 4/5: Building training dataset..."
python -c "
from wine_rec.pipeline.dataset_builder import build_dataset
from datetime import datetime

build_dataset(
    s3_bucket='rec-ml-dev-data',
    gold_b_prefix=f'gold-b/dt={datetime.now().strftime(\"%Y-%m-%d\")}/',
    output_path='data/training/dataset_$DATASET.parquet'
)
"

# 5. Train model
echo "🧠 Step 5/5: Training $MODEL model..."
python -c "
from wine_rec.models.training.trainer import train

metrics = train(
    model_name='$MODEL',
    dataset_version='$DATASET',
    feature_set_version='v1',
    hyperparams={
        'dataset_path': 'data/training/dataset_$DATASET.parquet',
        'epochs': 10,
        'embedding_dim': 64,
        'learning_rate': 0.001
    },
    output_dir='models/${MODEL}_${DATASET}/',
    seed=42
)
print(f'✅ Training complete! Metrics: {metrics}')
"

echo "✅ Pipeline complete! Model saved to models/${MODEL}_${DATASET}/"
