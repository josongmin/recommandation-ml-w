FROM python:3.11-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python deps
COPY pyproject.toml .
RUN uv pip install --system -e ".[ml]"

# Copy source
COPY src/ src/

# SageMaker expects train script at specific path
ENV SAGEMAKER_PROGRAM=wine_rec.models.training.trainer

ENTRYPOINT ["python", "-m", "wine_rec.models.training.trainer"]
