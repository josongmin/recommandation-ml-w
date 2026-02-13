# rec-ml

Production-Grade ML Recommendation System.

## Quick Start

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup dev environment
just setup

# Generate data & train
just pipeline      # Bronze → Gold → Training dataset (54K examples)

# Run checks
just check

# Run tests (365 passed, 63% coverage)
just test

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

## Data Pipeline (RFC-E2E-PIPELINE-006)

### 3-Layer Architecture

```
data/
├── bronze/     # Raw events (15K impressions, 10K actions, 1.2K orders)
├── gold_a/     # SSOT masters (500 wines, 1.5K SKUs, 5K reviews)
├── gold_b/     # IR features (review_agg, temporal, scarcity)
└── training/   # Training dataset (54,865 examples, 70/15/15 split)
```

### Pipeline Commands

```bash
# Generate all data layers
just pipeline

# Seed data only (Bronze + Gold)
just seed

# Training dataset only (skip seed)
just pipeline-fast

# Reset everything
just data-reset
```

### Dataset Statistics

- **Total examples**: 54,865
- **Positive rate**: 19.23%
- **Labels**: none(81%) → view(8%) → click(7%) → wishlist/cart(2%) → purchase(2%)
- **Quality gates**: ✅ Leakage=0.0, Join=1.0
- **Principles**: Impression-centric, Time-travel join, Lineage 3-key

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
