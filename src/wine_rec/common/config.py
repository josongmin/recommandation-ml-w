"""Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings loaded from env / .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # AWS
    aws_region: str = "ap-northeast-2"
    s3_bucket: str = "wine-rec-dev-data"

    # DynamoDB
    dynamodb_features_table: str = "features_online_v1"
    dynamodb_user_profile_table: str = "user_profile_v1"

    # Kinesis
    kinesis_stream_name: str = "wine-events-stream"

    # App
    env: str = "dev"
    log_level: str = "DEBUG"
    log_format: str = "json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
