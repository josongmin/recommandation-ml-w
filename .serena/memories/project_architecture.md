# Wine Rec 프로젝트 아키텍처 메모리

## 프로젝트 개요
- **목적**: High-End Wine Recommendation System (SOTA급 ML 추천 시스템)
- **기간**: 16주 (RFC-EXEC-PLAN-014 기준)
- **스택**: Python 3.11+, uv, ruff, basedpyright, pytest, PyTorch, RecBole, FastAPI, AWS Serverless

## 아키텍처 원칙

### Modular Monolith + Ports & Adapters (Lightweight)
```
src/wine_rec/
├── schemas/      # Shared Kernel: RFC → Pydantic 스키마
├── contracts/    # Shared Kernel: Protocol 인터페이스
├── infra/        # Adapters: AWS (DynamoDB, S3, Kinesis)
├── ingestion/    # Event collection + validation
├── pipeline/     # Batch ETL (Bronze → Silver → Gold)
├── features/     # Feature engineering + parity gate
├── models/       # ML baselines + training + evaluation
├── serving/      # FastAPI recommendation API
└── common/       # Config, logging
```

### 모듈 경계 규칙 (pyproject.toml L126-140)
**절대 금지:**
- serving/ingestion/models → pipeline internals
- models → serving
- ingestion → models

**허용:**
- 모든 모듈 → schemas, contracts (Shared Kernel)
- infra → 모든 모듈 (Adapter)

## 핵심 RFC 의존성
1. **RFC-SSOT-IR-001**: Wine/Review Master + IR 정의
2. **RFC-E2E-PIPELINE-006**: E2E 파이프라인 스펙
3. **RFC-LOG-SCHEMA-009**: 4대 SSOT 로그 (impression/action/order/policy)
4. **RFC-FEATURE-MANIFEST-010**: Feature Manifest + Parity Gate
5. **RFC-DATASET-BUILDER-011**: Impression-Centric Dataset Builder
6. **RFC-EXEC-PLAN-014**: 16주 실행 계획

## 데이터 파이프라인

### 레이어 구조
```
Bronze (Raw)
  ↓ (bronze_to_silver.py)
Silver (Cleaned)
  ↓ (silver_to_gold_a.py)
Gold-A (SSOT: Master 테이블)
  ↓ (gold_a_to_gold_b.py)
Gold-B (IR: 파생 자산)
  ↓ (dataset_builder.py)
Training Dataset (training_examples_v1)
```

### Quality Gates
- **Leakage Gate**: 0% 허용 (as_of_ts <= event_ts 엄격)
- **Integrity Gate**: join 성공률 99%+
- **Parity Gate**: Online/Offline feature diff=0 (critical tier)

## 이벤트 스키마 (schemas/events.py)
- `ImpressionEvent`: 노출 로그
- `PolicyEvent`: 모델 정책 로그 (propensity 필수, 누락률 >20% 차단)
- `ActionEvent`: 사용자 행동 (VIEW/CLICK/LIKE/CART 등)
- `OrderEvent`: 구매 로그

## 테스트 전략 (TDD)
- **Markers**: unit, integration, e2e, slow, gpu
- **Coverage**: 55%+ (초기, 구현 진행하며 상향)
- **lint**: ruff (L72-L103에서 80+ 규칙 적용)
- **typecheck**: basedpyright strict mode

## 16주 계획 요약
- Week 1-2: Storage Foundation (S3, DynamoDB, Iceberg)
- Week 3-4: Ingestion (API GW → Kinesis → S3 Bronze)
- Week 5-8: Batch Pipeline (Bronze → Gold-B + Dataset Builder)
- Week 9-10: Feature Engineering (Manifest + Parity Gate)
- Week 11-12: Model Training (BPR, Two-Tower, LightGCN, DeepFM)
- Week 13-14: Serving (FastAPI + Fargate)
- Week 15-16: Evaluation Loop + Monitoring

## 현재 상태
- 코드 스켈레톤 완성 (모든 모듈 __init__.py + stub 구현)
- 테스트 파일 존재 (unit/integration/e2e)
- 시드 데이터 스크립트 존재 (scripts/seed_data.py)
