#!/usr/bin/env bash
# Run E2E tests with LocalStack

set -euo pipefail

echo "🚀 Starting E2E Test Suite with LocalStack"
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start LocalStack
echo "1️⃣  Starting LocalStack..."
docker-compose -f docker-compose.localstack.yml up -d

# Wait for LocalStack to be ready
echo "⏳ Waiting for LocalStack to be ready..."
sleep 5

max_retries=30
for i in $(seq 1 $max_retries); do
    if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
        echo "✅ LocalStack is ready"
        break
    fi
    if [ $i -eq $max_retries ]; then
        echo "❌ LocalStack failed to start"
        docker-compose -f docker-compose.localstack.yml logs
        docker-compose -f docker-compose.localstack.yml down
        exit 1
    fi
    sleep 1
done

# Run E2E tests
echo ""
echo "2️⃣  Running E2E tests..."
export LOCALSTACK_ENDPOINT=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

uv run pytest tests/e2e/ -v -m e2e --tb=short

TEST_EXIT_CODE=$?

# Cleanup
echo ""
echo "3️⃣  Cleaning up..."
docker-compose -f docker-compose.localstack.yml down -v

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ E2E tests passed!"
    exit 0
else
    echo ""
    echo "❌ E2E tests failed"
    exit $TEST_EXIT_CODE
fi
