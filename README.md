# wine-rec

High-End Wine Recommendation System.

## Quick Start

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup dev environment
just setup

# Run checks
just check

# Run tests
just test

# Start API locally
just serve
```

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
