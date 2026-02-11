#!/usr/bin/env bash
# Build Lambda deployment package (.zip) for AWS Lambda (Linux x86_64)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔨 Building Lambda package for Linux x86_64..."

# Clean
rm -rf lambda_package lambda_deployment.zip
mkdir -p lambda_package

# Use Docker to build for Lambda runtime
docker run --rm \
  -v "$PWD":/var/task \
  --entrypoint /bin/bash \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install --target /var/task/lambda_package \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    pydantic \
    pydantic-settings \
    boto3 \
    structlog"

# Copy source code
cp -r src/wine_rec lambda_package/

# Create zip
cd lambda_package
zip -r ../lambda_deployment.zip . -q
cd ..

echo "✓ Lambda package created: lambda_deployment.zip"
ls -lh lambda_deployment.zip
echo "✓ Compatible with AWS Lambda Python 3.11 runtime"
