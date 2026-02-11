#!/usr/bin/env bash
# 모델 배포 및 추론 서빙 시작

set -euo pipefail

MODEL_VERSION=${1:-"v1"}
BUCKET="rec-ml-dev-data"

echo "🚀 Deploying Model Serving Infrastructure"
echo "📦 Model Version: $MODEL_VERSION"
echo ""

# ============================================
# 1️⃣ Docker 이미지 빌드 & ECR 푸시
# ============================================
echo "1️⃣  Building Docker image..."

cat > infra/docker/serving/Dockerfile << 'DOCKERFILE'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/wine_rec /app/wine_rec
COPY models/ /app/models/

# Expose port
EXPOSE 8080

# Run FastAPI server
CMD ["uvicorn", "wine_rec.serving.app:app", "--host", "0.0.0.0", "--port", "8080"]
DOCKERFILE

# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  058264332540.dkr.ecr.ap-northeast-2.amazonaws.com

# ECR 리포지토리 생성 (없으면)
aws ecr describe-repositories --repository-names rec-ml-serving \
  --region ap-northeast-2 2>/dev/null || \
  aws ecr create-repository --repository-name rec-ml-serving \
  --region ap-northeast-2

# 이미지 빌드 & 푸시
docker build -t rec-ml-serving:$MODEL_VERSION -f infra/docker/serving/Dockerfile .
docker tag rec-ml-serving:$MODEL_VERSION \
  058264332540.dkr.ecr.ap-northeast-2.amazonaws.com/rec-ml-serving:$MODEL_VERSION
docker push 058264332540.dkr.ecr.ap-northeast-2.amazonaws.com/rec-ml-serving:$MODEL_VERSION

echo "✅ Image pushed to ECR"
echo ""

# ============================================
# 2️⃣ Fargate 서비스 배포
# ============================================
echo "2️⃣  Deploying Fargate service..."

cd infra/terraform/modules/serving

# Terraform apply
terraform init
terraform apply -auto-approve \
  -var="model_version=$MODEL_VERSION" \
  -var="image_uri=058264332540.dkr.ecr.ap-northeast-2.amazonaws.com/rec-ml-serving:$MODEL_VERSION"

ALB_DNS=$(terraform output -raw alb_dns_name)

echo "✅ Fargate service deployed"
echo "🌐 Load Balancer: http://$ALB_DNS"
echo ""

# ============================================
# 3️⃣ Health Check
# ============================================
echo "3️⃣  Running health check..."
sleep 30  # Wait for service to be ready

curl -f http://$ALB_DNS/health || {
  echo "❌ Health check failed"
  exit 1
}

echo "✅ Service is healthy"
echo ""

# ============================================
# 4️⃣ 추론 테스트
# ============================================
echo "4️⃣  Testing inference..."

curl -X POST http://$ALB_DNS/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-001",
    "k": 10,
    "filters": {}
  }' | jq

echo ""
echo "🎉 Deployment Complete!"
echo ""
echo "📊 Endpoints:"
echo "  - Health: http://$ALB_DNS/health"
echo "  - Recommend: http://$ALB_DNS/recommend"
echo "  - Metrics: http://$ALB_DNS/metrics"
