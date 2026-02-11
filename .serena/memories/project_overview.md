# recommandation-ml-w (wine-rec)

## Purpose
고급 와인 추천 시스템. ML 기반 추천 파이프라인·모델·서빙 API를 포함한 모듈러 모놀리스.

## Tech Stack
- **Language**: Python 3.11+
- **Package Manager**: uv
- **Lint/Format**: ruff
- **Type Check**: basedpyright
- **Test**: pytest
- **Task Runner**: just
- **ML**: PyTorch + RecBole + PyG
- **Serving**: FastAPI (Fargate Spot)
- **Infra**: AWS Serverless (Terraform)

## Codebase Structure (Ports & Adapters)
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
└── common/      # Config, logging
```

## Module Boundary (pyproject.toml banned-api)
- serving/ingestion/models → pipeline 내부 import 금지
- models → serving import 금지
- ingestion → models import 금지
