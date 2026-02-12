#!/bin/bash

echo "🚀 Setting up LocalStack infrastructure for wine-rec"

# S3 Buckets
awslocal s3 mb s3://wine-rec-dev-data
awslocal s3 mb s3://wine-rec-dev-models

echo "✓ S3 buckets created"

# DynamoDB Tables
awslocal dynamodb create-table \
  --table-name wine-rec-dev-features \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST

echo "✓ DynamoDB tables created"

# Kinesis Streams
awslocal kinesis create-stream \
  --stream-name wine-rec-dev-events \
  --shard-count 1

echo "✓ Kinesis streams created"

echo "✅ LocalStack infrastructure ready"
