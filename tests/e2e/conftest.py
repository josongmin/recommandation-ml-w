"""E2E test configuration and fixtures."""

from __future__ import annotations

import os
import time

import boto3
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_localstack() -> None:
    """Ensure LocalStack is running before E2E tests."""
    if os.getenv("SKIP_E2E") == "1":
        pytest.skip("E2E tests disabled")

    endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")

    # Check if LocalStack is accessible
    max_retries = 30
    for i in range(max_retries):
        try:
            # Try to connect to S3
            s3 = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1")
            s3.list_buckets()
            break
        except Exception as e:
            if i == max_retries - 1:
                pytest.skip(f"LocalStack not available at {endpoint}: {e}")
            time.sleep(1)

    # Ensure buckets exist
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1")
    dynamodb = boto3.client("dynamodb", endpoint_url=endpoint, region_name="us-east-1")

    # Create S3 buckets
    for bucket in ["wine-rec-dev-data", "wine-rec-dev-models"]:
        try:
            s3.create_bucket(Bucket=bucket)
        except s3.exceptions.BucketAlreadyOwnedByYou:
            pass
        except Exception:
            pass

    # Create DynamoDB table
    try:
        dynamodb.create_table(
            TableName="wine-rec-dev-features",
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # Wait for table to be active
        time.sleep(2)
    except Exception:
        pass
