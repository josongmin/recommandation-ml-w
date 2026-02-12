# rec-ml

Production-Grade ML Recommendation System.

## Quick Start

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup dev environment
just setup

# Run checks
just check

# Run tests (382 tests, 63% coverage)
just test

# Run E2E tests with LocalStack
./scripts/run_e2e_tests.sh

# Start API locally
just serve
```

## Test Status

| Category | Count | Status | Coverage |
|----------|-------|--------|----------|
| Unit Tests | 376 | ✅ 368 passed, 8 skipped | 63% |
| Integration Tests | 8 | ✅ 8 passed | - |
| E2E Tests | 6 | ⚡ LocalStack required | - |
| **Total** | **390** | **✅ 384 passed** | **63%** |

See [TESTING.md](TESTING.md) for details.

## Architecture

**Modular Monolith + Ports & Adapters (lightweight)**

```
src/wine_rec/
├── schemas/      # Shared Kernel: data contracts (RFC → code)
├── contracts/    # Shared Kernel: interface protocols
├── infra/        # AWS adapters (DynamoDB, S3, Kinesis)
├── ingestion/    # Event collection + validation
├── pipeline/     # Batch ETL (Bronze → Silver → Gold)
├── features/     # Feature engineering + parity gate
├── models/       # ML baselines + training + evaluation
├── serving/      # FastAPI recommendation API
└── common/       # Config, logging
```

## E2E Pipeline

**Phase 1-2: Data Collection & ETL** (Automated)
- API Gateway → Lambda → Kinesis → Firehose → S3 Bronze (Real-time)
- EventBridge (daily 01:00 UTC) → Step Functions → Glue Jobs (Bronze→Silver→Gold-A→Gold-B→Dataset)

**Phase 3-4: Training & Feature Materialization** (scripts/)
```bash
scripts/e2e_training.sh           # Full training pipeline
scripts/deploy_serving.sh v1      # Deploy serving (Fargate + ALB)
```

**Phase 5-6: Serving** (Deployed)
- Client → ALB → Fargate (Feature lookup + Model inference + ANN search)

See [/tmp/e2e_pipeline.md](/tmp/e2e_pipeline.md) for detailed flow.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv
- **Lint/Format**: ruff
- **Type Check**: basedpyright
- **Test**: pytest
- **Task Runner**: just
- **ML**: PyTorch + RecBole + PyG
- **Serving**: FastAPI on Fargate Spot
- **Infra**: AWS Serverless-first (Terraform)

## RFCs

See [rfc/README.md](rfc/README.md) for the full design document index.
