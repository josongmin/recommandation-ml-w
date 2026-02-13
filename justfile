# wine-rec justfile — 2026 SOTA Python toolchain
# uv + ruff + basedpyright + pytest

set dotenv-load
set positional-arguments

# AWS CLI: project-local config
aws_config := justfile_directory() / ".aws" / "config"
aws_creds := justfile_directory() / ".aws" / "credentials"
export AWS_CONFIG_FILE := aws_config
export AWS_SHARED_CREDENTIALS_FILE := aws_creds

default:
    @just --list

# ════════════════════════════════════════════════
# Setup
# ════════════════════════════════════════════════

# Copy AWS credentials from source profile to project .aws (run once)
aws-setup profile="default":
    bash scripts/aws_setup.sh {{profile}}

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

# Run all checks (lint + typecheck + architecture)
check: lint typecheck lint-arch

# Lint with ruff
lint:
    uv run ruff check src/ tests/ scripts/

# Lint architecture (module boundaries)
lint-arch:
    uv run python scripts/lint_architecture.py

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

tf := justfile_directory() / ".bin" / "terraform"

# Terraform init (dev)
tf-init:
    cd infra/terraform/envs/dev && {{tf}} init

# Terraform plan (dev)
tf-plan:
    cd infra/terraform/envs/dev && {{tf}} plan

# Terraform apply (dev)
tf-apply:
    cd infra/terraform/envs/dev && {{tf}} apply -auto-approve

# ════════════════════════════════════════════════
# Run
# ════════════════════════════════════════════════

# Start serving API locally
serve:
    uv run uvicorn wine_rec.serving.app:app --reload --host 0.0.0.0 --port 8000

# Run benchmark suite
benchmark:
    uv run python -m wine_rec.models.evaluation.evaluator

# Run E2E scenario (Mock-based, no AWS required)
e2e:
    uv run python scripts/run_e2e_scenario.py

# ════════════════════════════════════════════════
# Data Pipeline (Bronze → Silver → Gold → Training)
# ════════════════════════════════════════════════

# Generate seed data (Bronze + Gold-A only)
seed:
    uv run python scripts/seed_data.py --output-dir data --seed 42

# Run complete pipeline (Bronze → Gold-B → Training)
pipeline:
    uv run python scripts/run_pipeline.py --seed 42

# Run pipeline without re-generating seed data
pipeline-fast:
    uv run python scripts/run_pipeline.py --skip-seed

# Clean all data
data-clean:
    @echo "🗑️  Cleaning all data..."
    rm -rf data/
    @echo "✓ Data cleaned"

# Reset pipeline (clean + run)
data-reset: data-clean pipeline
    @echo "✅ Pipeline reset complete"

# Legacy aliases (deprecated, use pipeline instead)
data-init: pipeline
data-retrain: pipeline-fast

# 데이터 통계 확인
data-stats:
    @echo "📊 데이터 통계:"
    @echo ""
    @echo "=== Seed Data ==="
    @[ -f data/gold_a/wine_core_master_v1/data.parquet ] && echo "✓ 와인: $(PYTHONPATH=src python -c 'import polars as pl; print(len(pl.read_parquet(\"data/gold_a/wine_core_master_v1/data.parquet\")))' 2>/dev/null || echo '0') 종" || echo "✗ 와인 데이터 없음"
    @[ -f data/profiles/user_profile_v1/data.parquet ] && echo "✓ 사용자: $(PYTHONPATH=src python -c 'import polars as pl; print(len(pl.read_parquet(\"data/profiles/user_profile_v1/data.parquet\")))' 2>/dev/null || echo '0') 명" || echo "✗ 사용자 데이터 없음"
    @[ -f data/bronze/impression_log_v1/data.parquet ] && echo "✓ Impression: $(PYTHONPATH=src python -c 'import polars as pl; print(len(pl.read_parquet(\"data/bronze/impression_log_v1/data.parquet\")))' 2>/dev/null || echo '0') 건" || echo "✗ Impression 데이터 없음"
    @echo ""
    @echo "=== Training Data ==="
    @[ -f data/training/training_examples_v1__ds=ds_v1/data.parquet ] && PYTHONPATH=src python -c "import polars as pl; df = pl.read_parquet('data/training/training_examples_v1__ds=ds_v1/data.parquet'); print(f'✓ Total: {len(df)} examples'); print(f'  - Train: {(df[\"split\"] == \"train\").sum()}'); print(f'  - Val: {(df[\"split\"] == \"val\").sum()}'); print(f'  - Test: {(df[\"split\"] == \"test\").sum()}'); print(f'  - Positive: {(df[\"label\"] > 0).sum()} ({(df[\"label\"] > 0).mean():.1%})')" 2>/dev/null || echo "✗ Training 데이터 없음"

# Synthetic 대규모 데이터 생성 (10K+ scale)
data-synthetic scale="10000":
    @echo "🔬 Synthetic 데이터 생성 중 (scale={{scale}})..."
    @echo "⚠️  구현 예정: scripts/generate_synthetic_data.py"
    @echo "   - 와인: {{scale}} 종"
    @echo "   - 사용자: {{scale}} 명"
    @echo "   - Impression: $(({{scale}} * 10)) 건"

# ════════════════════════════════════════════════
# AWS 리소스 관리
# ════════════════════════════════════════════════

# AWS 리소스 전체 초기화 (terraform apply)
aws-init: tf-init tf-apply
    @echo "✅ AWS 리소스 초기화 완료"

# AWS 리소스 삭제 (terraform destroy)
aws-destroy:
    @echo "⚠️  AWS 리소스 삭제 중..."
    cd infra/terraform/envs/dev && {{tf}} destroy -auto-approve
    @echo "✓ AWS 리소스 삭제 완료"

# AWS 리소스 재생성 (destroy → init)
aws-reset: aws-destroy aws-init
    @echo "✅ AWS 리소스 재생성 완료"

# AWS 리소스 상태 확인
aws-status:
    @echo "📊 AWS 리소스 상태:"
    @echo ""
    AWS_PROFILE=wine-rec-dev aws s3 ls | grep wine-rec-dev || echo "✗ S3 bucket 없음"
    AWS_PROFILE=wine-rec-dev aws dynamodb list-tables --query 'TableNames[?contains(@, `wine-rec-dev`)]' --output text || echo "✗ DynamoDB 테이블 없음"
    AWS_PROFILE=wine-rec-dev aws kinesis list-streams --query 'StreamNames[?contains(@, `wine-rec-dev`)]' --output text || echo "✗ Kinesis stream 없음"

# ════════════════════════════════════════════════
# 전체 환경 관리 (올인원)
# ════════════════════════════════════════════════

# 전체 환경 초기화 (dev setup + aws + data)
init-all: setup aws-init data-init
    @echo ""
    @echo "🎉 전체 환경 초기화 완료!"
    @echo ""
    @echo "다음 명령어로 시작하세요:"
    @echo "  just serve     # API 서버 시작"
    @echo "  just test      # 테스트 실행"
    @echo "  just data-stats # 데이터 통계 확인"

# 전체 환경 삭제
clean-all: clean data-clean
    @echo "✅ 전체 환경 삭제 완료"

# 전체 환경 재생성
reset-all: clean-all init-all
    @echo "✅ 전체 환경 재생성 완료"

# 상태 확인 (health check)
status:
    @echo "🔍 시스템 상태 확인"
    @echo ""
    @echo "=== Python 환경 ==="
    @which python >/dev/null && echo "✓ Python: $(python --version)" || echo "✗ Python 없음"
    @which uv >/dev/null && echo "✓ uv: $(uv --version)" || echo "✗ uv 없음"
    @echo ""
    @echo "=== AWS 환경 ==="
    @which aws >/dev/null && echo "✓ AWS CLI: $(aws --version | head -1)" || echo "✗ AWS CLI 없음"
    @[ -f .aws/config ] && echo "✓ AWS Config: .aws/config" || echo "✗ AWS Config 없음"
    @[ -f .aws/credentials ] && echo "✓ AWS Credentials: .aws/credentials" || echo "✗ AWS Credentials 없음"
    @echo ""
    @echo "=== Terraform ==="
    @[ -f .bin/terraform ] && echo "✓ Terraform: $(.bin/terraform version | head -1)" || echo "✗ Terraform 없음"
    @echo ""
    @just data-stats
    @echo ""
    @just aws-status

# ════════════════════════════════════════════════
# Clean
# ════════════════════════════════════════════════

# Remove all caches and build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    @echo "✓ Cleaned"
