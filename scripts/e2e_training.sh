#!/usr/bin/env bash
# 전체 학습 파이프라인 실행 스크립트

set -euo pipefail

BUCKET="rec-ml-dev-data"
DATE=$(date +%Y-%m-%d)

echo "🚀 Starting E2E Training Pipeline"
echo "📅 Date: $DATE"
echo "🪣 Bucket: $BUCKET"
echo ""

# ============================================
# 1️⃣ 데이터 수집 시뮬레이션
# ============================================
echo "1️⃣  Generating seed data..."
python scripts/seed_data.py
echo "✅ Seed data generated"
echo ""

# ============================================
# 2️⃣ S3 업로드
# ============================================
echo "2️⃣  Uploading to S3 Bronze layer..."
aws s3 cp data/seed/events.json \
  s3://$BUCKET/bronze/dt=$DATE/events.json \
  --region ap-northeast-2
echo "✅ Data uploaded to bronze/"
echo ""

# ============================================
# 3️⃣ Glue ETL 파이프라인 트리거
# ============================================
echo "3️⃣  Triggering Glue ETL pipeline..."
STATE_MACHINE="arn:aws:states:ap-northeast-2:058264332540:stateMachine:rec-ml-dev-daily-pipeline"

EXEC_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn $STATE_MACHINE \
  --input "{\"dt\":\"$DATE\"}" \
  --region ap-northeast-2 \
  --query 'executionArn' \
  --output text)

echo "Execution ARN: $EXEC_ARN"
echo "⏳ Waiting for ETL completion (polling every 30s)..."

while true; do
  STATUS=$(aws stepfunctions describe-execution \
    --execution-arn "$EXEC_ARN" \
    --region ap-northeast-2 \
    --query 'status' \
    --output text)

  echo "   Status: $STATUS"

  if [ "$STATUS" = "SUCCEEDED" ]; then
    echo "✅ ETL pipeline completed successfully"
    break
  elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "TIMED_OUT" ] || [ "$STATUS" = "ABORTED" ]; then
    echo "❌ ETL pipeline failed with status: $STATUS"
    exit 1
  fi

  sleep 30
done
echo ""

# ============================================
# 4️⃣ 학습 데이터셋 빌드 확인
# ============================================
echo "4️⃣  Checking dataset in S3..."
aws s3 ls s3://$BUCKET/dataset/dt=$DATE/ --region ap-northeast-2
echo "✅ Dataset ready"
echo ""

# ============================================
# 5️⃣ SageMaker 학습 작업 생성
# ============================================
echo "5️⃣  Starting SageMaker training job..."

cat > /tmp/training_config.json <<JSON
{
  "TrainingJobName": "rec-ml-two-tower-$(date +%Y%m%d-%H%M%S)",
  "RoleArn": "arn:aws:iam::058264332540:role/rec-ml-dev-sagemaker-role",
  "AlgorithmSpecification": {
    "TrainingImage": "763104351884.dkr.ecr.ap-northeast-2.amazonaws.com/pytorch-training:2.0.0-gpu-py310",
    "TrainingInputMode": "File"
  },
  "InputDataConfig": [
    {
      "ChannelName": "training",
      "DataSource": {
        "S3DataSource": {
          "S3DataType": "S3Prefix",
          "S3Uri": "s3://$BUCKET/dataset/dt=$DATE/",
          "S3DataDistributionType": "FullyReplicated"
        }
      }
    }
  ],
  "OutputDataConfig": {
    "S3OutputPath": "s3://$BUCKET/models/"
  },
  "ResourceConfig": {
    "InstanceType": "ml.g4dn.xlarge",
    "InstanceCount": 1,
    "VolumeSizeInGB": 30
  },
  "StoppingCondition": {
    "MaxRuntimeInSeconds": 7200
  },
  "HyperParameters": {
    "model_name": "two_tower",
    "epochs": "10",
    "embedding_dim": "64",
    "learning_rate": "0.001"
  }
}
JSON

aws sagemaker create-training-job \
  --cli-input-json file:///tmp/training_config.json \
  --region ap-northeast-2

echo "✅ SageMaker training job started"
echo ""

# ============================================
# 6️⃣ Feature Materialization
# ============================================
echo "6️⃣  Materializing features to DynamoDB..."
python -c "
from wine_rec.features.online_materializer import materialize_features

materialize_features(
    s3_bucket='$BUCKET',
    gold_b_prefix='gold-b/dt=$DATE/',
    dynamodb_table='rec-ml-dev-features-online-v1'
)
"
echo "✅ Features materialized to DynamoDB"
echo ""

echo "🎉 E2E Pipeline Complete!"
echo ""
echo "📊 Next steps:"
echo "  - Monitor training: aws sagemaker describe-training-job --training-job-name <job-name>"
echo "  - Deploy model: scripts/deploy_model.sh"
echo "  - Test inference: curl https://<alb-endpoint>/recommend?user_id=123"
