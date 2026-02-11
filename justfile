# wine-rec justfile — 2026 SOTA Python toolchain
# uv + ruff + basedpyright + pytest

set dotenv-load
set positional-arguments

default:
    @just --list

# ════════════════════════════════════════════════
# Setup
# ════════════════════════════════════════════════

# Create venv + install all deps
setup:
    uv venv
    uv pip install -e ".[all]"
    uv run pre-commit install
    uv run pre-commit install --hook-type commit-msg
    @echo "✓ Dev environment ready"

# Install core only
install:
    uv pip install -e .

# Install dev + test
install-dev:
    uv pip install -e ".[dev,test]"

# Sync lockfile (after dependency change)
lock:
    uv lock

# ════════════════════════════════════════════════
# Quality — lint, format, type-check
# ════════════════════════════════════════════════

# Run all checks (lint + typecheck)
check: lint typecheck

# Lint with ruff
lint:
    uv run ruff check src/ tests/ scripts/

# Format with ruff
fmt:
    uv run ruff format src/ tests/ scripts/
    uv run ruff check --fix src/ tests/ scripts/

# Type-check with basedpyright
typecheck:
    uv run basedpyright src/wine_rec

# Lint + format + typecheck (fix everything)
fix: fmt
    uv run basedpyright src/wine_rec

# ════════════════════════════════════════════════
# Test
# ════════════════════════════════════════════════

# Run all tests
test *args:
    uv run pytest {{args}}

# Unit tests only
test-unit:
    uv run pytest -m unit

# Integration tests (AWS mocks)
test-integration:
    uv run pytest -m integration

# E2E tests
test-e2e:
    uv run pytest -m e2e

# Fast parallel tests
test-fast:
    uv run pytest -m "not slow and not e2e" -n auto

# Tests with verbose output
test-v:
    uv run pytest -v --tb=long

# ════════════════════════════════════════════════
# Pre-commit
# ════════════════════════════════════════════════

# Run pre-commit on all files
hooks:
    uv run pre-commit run --all-files

# Update pre-commit hooks
hooks-update:
    uv run pre-commit autoupdate

# ════════════════════════════════════════════════
# Docker
# ════════════════════════════════════════════════

# Build training image
docker-train:
    docker build -t wine-rec-train:latest -f infra/docker/training/Dockerfile .

# Build serving image
docker-serve:
    docker build -t wine-rec-serve:latest -f infra/docker/serving/Dockerfile .

# ════════════════════════════════════════════════
# Infrastructure (Terraform)
# ════════════════════════════════════════════════

# Terraform init (dev)
tf-init:
    cd infra/terraform/envs/dev && terraform init

# Terraform plan (dev)
tf-plan:
    cd infra/terraform/envs/dev && terraform plan

# Terraform apply (dev)
tf-apply:
    cd infra/terraform/envs/dev && terraform apply

# ════════════════════════════════════════════════
# Run
# ════════════════════════════════════════════════

# Start serving API locally
serve:
    uv run uvicorn wine_rec.serving.app:app --reload --host 0.0.0.0 --port 8000

# Run benchmark suite
benchmark:
    uv run python -m wine_rec.models.evaluation.evaluator

# ════════════════════════════════════════════════
# Clean
# ════════════════════════════════════════════════

# Remove all caches and build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    @echo "✓ Cleaned"
