RFC-INFRA-IMPL-013

Title: High-End Wine Recommendation — AWS Serverless-First Infrastructure & Cost Optimization v1
Status: Draft v1.0
Scope: 전체 파이프라인의 AWS 서비스 매핑, Serverless-first 원칙, 비용 최적화 전략, 빌드 순서를 고정한다.
Depends On:
- RFC-E2E-PIPELINE-006: E2E 파이프라인 스펙 (데이터 흐름/계층 정의)
- RFC-IR-SCHEMA-007: 저장 스키마 계약
- RFC-REALTIME-PIPELINE-008: 실시간 파이프라인 스펙
- RFC-LOG-SCHEMA-009: 로그 스키마
- RFC-FEATURE-MANIFEST-010: Feature Manifest & Parity Gate
- RFC-DATASET-BUILDER-011: Dataset Builder
- RFC-SOTA-ROADMAP-012: 3년 로드맵

0. 목표 (What we freeze)

0-1. Serverless-First 원칙
- "항상 켜진 클러스터"를 최소화하고, 이벤트 기반 + 온디맨드 컴퓨트를 기본으로 한다.
- 트래픽 0일 때 비용 ~$0을 목표로 한다.

0-2. 비용 상한
- MVP 단계: 월 $30~160 (Free Tier 포함)
- 프로덕션 단계: 월 $300~800 (트래픽 규모에 따라)
- 학습 인프라: SageMaker Spot 기반 (최대 70% 절감)

0-3. 고정 원칙
- (A) 모든 데이터는 S3가 SSOT (Iceberg 테이블 포맷)
- (B) 오케스트레이션은 Step Functions (MWAA 대비 90% 저렴)
- (C) 스트리밍은 Kinesis On-demand (MSK 대비 1/10 비용)
- (D) 서빙은 Fargate Spot + ALB (EKS 대비 운영 비용 제거)

1. 인프라 6계층 아키텍처

1-1. Layer 0: Data Lake & Storage

| 서비스 | 용도 | 비용 최적화 |
|--------|------|-------------|
| S3 Standard | Hot 데이터 (최근 90일 로그, 현재 IR) | 기본 |
| S3 IA (Infrequent Access) | Warm (90~365일) | Lifecycle 자동 전환 |
| S3 Glacier Instant | Cold (365일+, 감사/재현용) | Lifecycle 자동 전환 |
| S3 Intelligent-Tiering | 접근 패턴 불확실한 데이터 | 자동 최적화 |

S3 Lifecycle 정책 (고정):
```json
{
  "Rules": [
    {
      "ID": "hot-to-ia",
      "Filter": {"Prefix": "gold/"},
      "Transitions": [
        {"Days": 90, "StorageClass": "STANDARD_IA"},
        {"Days": 365, "StorageClass": "GLACIER_INSTANT_RETRIEVAL"}
      ]
    },
    {
      "ID": "logs-retention",
      "Filter": {"Prefix": "logs/"},
      "Transitions": [
        {"Days": 30, "StorageClass": "STANDARD_IA"},
        {"Days": 180, "StorageClass": "GLACIER_INSTANT_RETRIEVAL"}
      ]
    },
    {
      "ID": "artifacts-permanent",
      "Filter": {"Prefix": "artifacts/"},
      "Transitions": [
        {"Days": 365, "StorageClass": "GLACIER_INSTANT_RETRIEVAL"}
      ],
      "NoncurrentVersionExpiration": {"NoncurrentDays": 730}
    }
  ]
}
```

Iceberg 테이블 포맷:
- 모든 Gold Layer 테이블은 Apache Iceberg 포맷으로 관리
- time-travel query 네이티브 지원 (as_of_ts 기반 조회)
- Glue Data Catalog을 Iceberg catalog로 사용
- 파티션: dt(날짜) + entity_type 기본

1-2. Layer 1: Ingestion & Streaming

| 서비스 | 용도 | 비용 근거 |
|--------|------|-----------|
| API Gateway (HTTP API) | 이벤트 수집 엔드포인트 | $1/백만 req |
| Lambda | 이벤트 검증 + 라우팅 | 프리티어 1M req/월 |
| Kinesis Data Streams (On-demand) | 실시간 이벤트 스트림 | 사용량 비례, 최소 비용 ~$0.04/시간/shard |
| Kinesis Firehose | S3 적재 (배치) | $0.029/GB |

MSK 대신 Kinesis를 선택한 이유:
- MSK: 최소 $0.21/시간 × 3 broker = **$460/월** (항시 가동)
- Kinesis On-demand: 트래픽 0이면 **~$0/월**, MVP 트래픽에서 **~$5~15/월**
- 하이엔드 와인 추천은 초기 트래픽이 낮으므로 Kinesis가 압도적으로 유리

이벤트 흐름:
```
Client → API Gateway (HTTP API)
       → Lambda (검증/enrichment)
       → Kinesis Data Streams
       → Firehose → S3 (Bronze layer, Parquet)
       → Lambda Consumer → DynamoDB (실시간 feature 갱신)
```

1-3. Layer 2: Orchestration & Batch Processing

| 서비스 | 용도 | 비용 근거 |
|--------|------|-----------|
| Step Functions (Standard) | 파이프라인 오케스트레이션 | $0.025/1000 전환 |
| Glue (Spark Serverless) | ETL/배치 변환 | DPU-시간 기반, 필요 시만 과금 |
| Glue Crawlers | 스키마 자동 감지 | 크롤러 실행 시만 과금 |
| EventBridge | 스케줄링 + 이벤트 라우팅 | 프리티어 충분 |

MWAA(Airflow) 대신 Step Functions를 선택한 이유:
- MWAA: 최소 **$315/월** (소형 환경, 항시 가동)
- Step Functions: MVP에서 **~$1~5/월** (실행 횟수 기반)
- DAG 복잡도가 낮은 초기에는 Step Functions이 10배+ 저렴

Step Functions 워크플로 정의 (핵심):
```
Pipeline A: Daily SSOT Refresh
  1. Glue Job: Bronze → Silver (정제/검증)
  2. Glue Job: Silver → Gold-A (SSOT 테이블 갱신)
  3. Glue Job: Gold-A → Gold-B (IR 생성)
  4. Lambda: Quality Gate 검증
  5. SNS: 성공/실패 알림

Pipeline B: Dataset Build (주간/온디맨드)
  1. Glue Job: training_examples_v1 생성
  2. Glue Job: splits_v1 생성
  3. Lambda: dataset_manifest_v1 기록
  4. Lambda: Leakage Gate + join_proof 검증
  5. Lambda: Integrity Gate (join 성공률 등)

Pipeline C: Model Training (온디맨드)
  1. SageMaker Training Job (Spot)
  2. Lambda: 평가 트리거
  3. Step Functions: 벤치마크 스위트 실행
  4. Lambda: 승자 판정 + 배포 승인

Pipeline D: Feature Parity Check (일간)
  1. Lambda: 샘플 추출
  2. Lambda: Online/Offline 비교
  3. Lambda: Parity Diff Histogram 기록
  4. SNS: 위반 경보
```

1-4. Layer 3: Feature Store & Serving DB

| 서비스 | 용도 | 비용 근거 |
|--------|------|-----------|
| DynamoDB (On-demand) | 실시간 feature 서빙 | 읽기/쓰기 단위 과금, 유휴 시 ~$0 |
| ElastiCache (Redis) | 핫 캐시 (선택) | 후기 도입, 필요 시만 |
| OpenSearch Serverless | ANN 벡터 검색 (후보 리콜) | 후기 도입 |

DynamoDB 테이블 설계:
```
Table: features_online_v1
  PK: entity_type#entity_id
  SK: feature_set_version
  Attributes: feature_json, as_of_ts, ttl

Table: user_profile_v1
  PK: user_id
  SK: "PROFILE"
  Attributes: taste_profile, price_elasticity, ...

Table: wine_embedding_v1
  PK: wine_core_id
  SK: embedding_model#version
  Attributes: embedding_vector, as_of_ts
```

DynamoDB 대신 Redis를 쓰지 않는 이유 (초기):
- ElastiCache: 최소 **$12/월** (t4g.micro, 항시 가동)
- DynamoDB On-demand: 유휴 시 **$0**, MVP 트래픽에서 **~$1~5/월**
- 읽기 지연 p99 < 10ms 요구사항이 없는 초기에는 DynamoDB가 적합

1-5. Layer 4: ML Training & Evaluation

| 서비스 | 용도 | 비용 근거 |
|--------|------|-----------|
| SageMaker Training (Spot) | 모델 학습 | On-demand 대비 **최대 70% 절감** |
| SageMaker Processing | 평가/벤치마크 실행 | 실행 시간만 과금 |
| ECR | 학습/서빙 컨테이너 이미지 | 저장 비용만 (최소) |
| S3 | 모델 아티팩트 저장 | Gold-C 경로 |

SageMaker Spot 전략:
```yaml
training_job_config:
  instance_type: ml.g4dn.xlarge    # GPU (LightGCN, DeepFM 등)
  instance_count: 1
  use_spot: true
  max_wait_time: 7200              # 최대 2시간 대기
  max_run_time: 3600               # 최대 1시간 실행
  checkpoint_s3_uri: s3://bucket/checkpoints/

  # Spot 중단 대응
  checkpoint_interval: 300          # 5분마다 체크포인트
  retry_strategy:
    max_retries: 3                  # 3회 재시도
```

인스턴스 비용 비교:
| 인스턴스 | On-demand | Spot | 절감율 |
|----------|-----------|------|--------|
| ml.g4dn.xlarge (GPU) | $0.736/h | ~$0.22/h | 70% |
| ml.m5.xlarge (CPU) | $0.23/h | ~$0.07/h | 70% |
| ml.c5.2xlarge (CPU heavy) | $0.408/h | ~$0.12/h | 70% |

학습 빈도 및 비용 추정 (MVP):
- 베이스라인 4종 학습: 주 1회, 각 ~30분 → **~$2~5/월**
- 실험 학습: 주 2~3회 → **~$3~8/월**
- 벤치마크 평가: 학습마다 → 포함

1-6. Layer 5: Model Serving

| 서비스 | 용도 | 비용 근거 |
|--------|------|-----------|
| Fargate Spot | 추천 API 서빙 | On-demand 대비 **최대 70% 절감** |
| ALB | 로드밸런싱 | $16/월 + LCU |
| Lambda | 경량 추론 (fallback) | 프리티어 |

Fargate 대신 EKS를 쓰지 않는 이유:
- EKS: 컨트롤 플레인 **$73/월** + 노드 비용 (항시 가동)
- Fargate Spot: 실행 시간만 과금, **운영 오버헤드 제거**
- 초기에는 오토스케일링 복잡도가 낮으므로 Fargate가 적합

Fargate 서빙 아키텍처:
```
ALB → Fargate Service (Spot, 최소 1 태스크)
    ├── /recommend  → Multi-Recall + Rank
    ├── /explain    → 설명 생성
    └── /health     → 헬스체크

Fargate Task 정의:
  CPU: 0.5 vCPU
  Memory: 1 GB
  Auto-scaling: 최소 1, 최대 4 (CPU 70% 기준)
  Spot 비율: 80% Spot + 20% On-demand (가용성)
```

2. 데이터 흐름 아키텍처 (End-to-End)

```
[Client/App]
    │
    ▼
[API Gateway HTTP API] ─── 이벤트 수집 (impression/action/order)
    │
    ▼
[Lambda: Event Validator] ─── 스키마 검증, enrichment
    │
    ├──▶ [Kinesis Data Streams] ─── 실시간 스트림
    │       │
    │       ├──▶ [Firehose → S3 Bronze] ─── 배치 적재 (Parquet, 5분 버퍼)
    │       │
    │       └──▶ [Lambda Consumer] ─── 실시간 feature 갱신
    │               │
    │               └──▶ [DynamoDB: features_online_v1]
    │
    ▼
[EventBridge Scheduler] ─── 일간/주간 트리거
    │
    ▼
[Step Functions: Pipeline A] ─── Daily SSOT Refresh
    │
    ├──▶ [Glue: Bronze → Silver → Gold-A → Gold-B]
    │       │
    │       └──▶ [S3: Gold Layer (Iceberg)]
    │
    ├──▶ [Step Functions: Pipeline B] ─── Dataset Build
    │       │
    │       └──▶ [S3: training_examples_v1 + splits_v1]
    │
    └──▶ [Step Functions: Pipeline C] ─── Training
            │
            ├──▶ [SageMaker Spot: Model Training]
            │       │
            │       └──▶ [S3: model artifacts (Gold-C)]
            │
            └──▶ [SageMaker Processing: Evaluation]
                    │
                    └──▶ [S3: eval reports + quality_gate_report_v1]

[Fargate Spot Service] ─── 추천 API 서빙
    │
    ├── DynamoDB 조회 (features_online_v1)
    ├── S3 조회 (모델 아티팩트, 임베딩 인덱스)
    └── 로그 → Kinesis → S3 (서빙 로그, 피드백 루프)
```

3. S3 경로 규약 (고정)

```
s3://{bucket}/
├── bronze/
│   ├── impression_log/{dt}/
│   ├── action_log/{dt}/
│   ├── order_log/{dt}/
│   └── policy_log/{dt}/
│
├── silver/
│   ├── impression_cleaned/{dt}/
│   ├── action_cleaned/{dt}/
│   └── order_cleaned/{dt}/
│
├── gold/
│   ├── a_ssot/                          # Gold-A: SSOT 테이블
│   │   ├── wine_core_master_v1/
│   │   ├── wine_sku_master_v1/
│   │   ├── review_master_v1/
│   │   └── ...
│   │
│   ├── b_ir/                            # Gold-B: IR 파생 자산
│   │   ├── wine_text_ir_v1/
│   │   ├── wine_temporal_ir_v1/
│   │   ├── wine_review_aggregate_ir_v1/
│   │   ├── wine_hetero_graph_ir_v1/
│   │   ├── wine_scarcity_ir_v1/
│   │   ├── wine_market_ir_v1/
│   │   ├── wine_condition_ir_v1/
│   │   ├── wine_image_ir_v1/
│   │   └── ...
│   │
│   └── c_model/                         # Gold-C: 모델 아티팩트
│       ├── embeddings/
│       │   ├── text_embedding_v1/
│       │   ├── image_embedding_v1/
│       │   └── graph_embedding_v1/
│       ├── models/
│       │   ├── bpr_v1/
│       │   ├── two_tower_v1/
│       │   ├── lightgcn_v1/
│       │   ├── deepfm_v1/
│       │   └── dlrm_v1/
│       └── indices/
│           └── ann_index_v1/
│
├── dataset/
│   ├── training_examples_v1/{dataset_version}/
│   ├── splits_v1/{dataset_version}/
│   └── dataset_manifest_v1/{dataset_version}/
│
├── artifacts/                            # 영구 보관
│   ├── join_proof_audit_v1/{dataset_version}/
│   ├── leakage_violations/{dataset_version}/
│   ├── quality_gate_report_v1/{run_id}/
│   ├── feature_manifest_v1/{feature_set_version}/
│   └── eval_reports/{experiment_id}/
│
├── config/
│   ├── feature_manifest/
│   ├── ranking_weight_config/
│   └── pipeline_config/
│
└── logs/
    ├── serving_log/{dt}/
    └── pipeline_log/{dt}/
```

4. 비용 상세 추정

4-1. MVP 단계 (월간, Free Tier 포함)

| 계층 | 서비스 | 추정 비용 | 비고 |
|------|--------|-----------|------|
| Storage | S3 (50GB) | $1~2 | 초기 데이터 소량 |
| Ingestion | API Gateway + Lambda | $0 | Free Tier |
| Streaming | Kinesis On-demand (1 shard) | $5~15 | 트래픽 비례 |
| Batch | Glue (일 1회, 2 DPU × 10분) | $3~8 | DPU-시간 과금 |
| Orchestration | Step Functions | $1~3 | 전환 횟수 기반 |
| Feature Store | DynamoDB On-demand | $1~5 | 읽기/쓰기 비례 |
| Training | SageMaker Spot (주 1회) | $5~15 | GPU 30분/회 |
| Serving | Fargate Spot (1 태스크) | $10~30 | 0.5 vCPU, 1GB |
| Serving | ALB | $16 | 고정비 (최소) |
| Monitoring | CloudWatch | $0~5 | 기본 메트릭 무료 |
| **합계** | | **$42~100** | |

4-2. Free Tier 최대 활용 (12개월)

| 서비스 | Free Tier 한도 | 절감 효과 |
|--------|----------------|-----------|
| Lambda | 1M 요청/월, 400K GB-초 | ~$10/월 절감 |
| DynamoDB | 25GB 저장 + 25 WCU/RCU | ~$5/월 절감 |
| S3 | 5GB Standard | ~$0.1/월 절감 |
| API Gateway | 1M HTTP API 요청/월 | ~$1/월 절감 |
| CloudWatch | 기본 메트릭 | ~$5/월 절감 |
| SageMaker | 첫 2개월 무료(일부) | 가변 |

4-3. 비용 최적화 규칙 (고정)

1. **제로 트래픽 = 제로 비용 원칙**: 항시 가동 서비스는 ALB만 허용 (MVP)
2. **Spot 우선**: 학습(SageMaker Spot) + 서빙(Fargate Spot) 모두 Spot 기본
3. **S3 Lifecycle 필수**: 모든 경로에 Lifecycle 정책 적용, 90일 이상 IA 전환
4. **DynamoDB TTL 활용**: 오래된 feature 스냅샷은 TTL로 자동 삭제
5. **Glue 최소 DPU**: 초기 2 DPU부터 시작, 데이터 규모에 따라 증가
6. **Reserved Capacity 금지 (MVP)**: 트래픽 패턴 확정 전까지 On-demand만 사용
7. **월별 비용 리뷰**: AWS Cost Explorer + Budget Alert ($100, $200 임계치)

5. 프로젝트 디렉토리 구조 (고정)

```
wine-recommendation-ml/
├── rfc/                              # 설계 문서 (현재)
│
├── infra/                            # IaC (Infrastructure as Code)
│   ├── terraform/                    # Terraform 모듈
│   │   ├── modules/
│   │   │   ├── storage/              # S3 + Lifecycle
│   │   │   ├── ingestion/            # API GW + Lambda + Kinesis
│   │   │   ├── processing/           # Glue + Step Functions
│   │   │   ├── feature_store/        # DynamoDB
│   │   │   ├── training/             # SageMaker
│   │   │   ├── serving/              # Fargate + ALB
│   │   │   └── monitoring/           # CloudWatch + Alarms
│   │   ├── envs/
│   │   │   ├── dev/
│   │   │   └── prod/
│   │   └── main.tf
│   └── docker/
│       ├── training/
│       │   └── Dockerfile
│       └── serving/
│           └── Dockerfile
│
├── src/
│   ├── ingestion/                    # Layer 1: 이벤트 수집
│   │   ├── lambda_handler.py         # 이벤트 검증/라우팅
│   │   ├── schema_validator.py       # 로그 스키마 검증
│   │   └── tests/
│   │
│   ├── pipeline/                     # Layer 2: 배치 파이프라인
│   │   ├── bronze_to_silver.py       # 정제
│   │   ├── silver_to_gold_a.py       # SSOT 생성
│   │   ├── gold_a_to_gold_b.py       # IR 생성
│   │   ├── dataset_builder.py        # training_examples 생성
│   │   ├── quality_gates.py          # Integrity/Leakage/Parity Gate
│   │   ├── step_functions/           # Step Functions 정의 (ASL JSON)
│   │   │   ├── daily_refresh.asl.json
│   │   │   ├── dataset_build.asl.json
│   │   │   └── training_pipeline.asl.json
│   │   └── tests/
│   │
│   ├── features/                     # Layer 3: Feature 엔지니어링
│   │   ├── manifest/
│   │   │   └── feature_manifest_v1.yaml
│   │   ├── offline_builder.py        # Offline feature 생성
│   │   ├── online_materializer.py    # Online feature 갱신 (Lambda)
│   │   ├── parity_checker.py         # Online/Offline 비교
│   │   └── tests/
│   │
│   ├── models/                       # Layer 4: 모델
│   │   ├── baselines/
│   │   │   ├── bpr.py
│   │   │   ├── two_tower.py
│   │   │   ├── lightgcn.py
│   │   │   ├── deepfm.py
│   │   │   └── dlrm.py
│   │   ├── training/
│   │   │   ├── trainer.py            # SageMaker 학습 스크립트
│   │   │   └── config.yaml
│   │   ├── evaluation/
│   │   │   ├── evaluator.py          # 벤치마크 실행
│   │   │   ├── counterfactual.py     # IPS/SNIPS/DR
│   │   │   └── metrics.py
│   │   └── tests/
│   │
│   ├── serving/                      # Layer 5: 서빙
│   │   ├── app.py                    # FastAPI 앱
│   │   ├── recommender.py            # Multi-Recall + Rank
│   │   ├── explainer.py              # 설명 생성
│   │   ├── feature_client.py         # DynamoDB feature 조회
│   │   └── tests/
│   │
│   └── common/                       # 공통 유틸
│       ├── config.py
│       ├── s3_utils.py
│       ├── iceberg_utils.py
│       └── logging.py
│
├── scripts/                          # 운영/유틸 스크립트
│   ├── setup_infra.sh
│   ├── deploy.sh
│   ├── run_benchmark.sh
│   └── manifest_diff.py              # Dataset Manifest Diff Tool
│
├── notebooks/                        # 탐색/분석 노트북
│   ├── eda/
│   └── experiments/
│
├── configs/                          # 런타임 설정
│   ├── ranking_weight_config.yaml    # Expert authority weights 등
│   └── pipeline_config.yaml
│
├── tests/                            # 통합 테스트
│   ├── integration/
│   └── e2e/
│
├── pyproject.toml
├── Makefile
└── README.md
```

6. 기술 스택 (고정)

6-1. 언어 및 프레임워크

| 영역 | 기술 | 선정 이유 |
|------|------|-----------|
| 언어 | Python 3.11+ | ML 생태계 + Lambda 지원 |
| 웹 프레임워크 | FastAPI | 비동기 + Pydantic 검증 + OpenAPI 자동 |
| ML 프레임워크 | PyTorch 2.x | RecBole/TorchRec 기반 |
| 추천 라이브러리 | RecBole | 베이스라인 4종 통합 제공 |
| 그래프 | PyG (PyTorch Geometric) | LightGCN/R-GCN 구현 |
| 데이터 처리 | PySpark (Glue) + Polars (경량) | 배치/로컬 분리 |
| 벡터 검색 | FAISS → OpenSearch Serverless | 초기 FAISS, 프로덕션 OpenSearch |
| IaC | Terraform | AWS 네이티브 + 상태 관리 |
| CI/CD | GitHub Actions | 무료 + 간편 |
| 컨테이너 | Docker + ECR | 학습/서빙 이미지 |

6-2. 데이터 포맷

| 용도 | 포맷 | 이유 |
|------|------|------|
| 로그 저장 | Parquet | 컬럼 압축 + Glue/Athena 호환 |
| 테이블 관리 | Apache Iceberg | time-travel + schema evolution |
| Feature Manifest | YAML (원본) → JSON (배포) | 가독성 + 정합성 |
| 모델 아티팩트 | PyTorch state_dict + config.json | 표준 |
| 설정 | YAML | 가독성 |

7. 보안 및 네트워크 (최소 구성)

7-1. IAM
- 서비스별 최소 권한 IAM Role (Lambda용, Glue용, SageMaker용, Fargate용)
- S3 버킷 정책: 명시적 deny-all + allow-list

7-2. 네트워크
- VPC: 서빙/DB만 private subnet
- S3: VPC Endpoint (Gateway) — 데이터 전송 비용 제거
- DynamoDB: VPC Endpoint (Gateway)
- Public: API Gateway만 (ALB는 internal 가능)

7-3. 암호화
- S3: SSE-S3 기본 (SSE-KMS는 비용 발생 시 후기 전환)
- DynamoDB: 기본 암호화 (추가 비용 없음)
- 전송: TLS 필수

8. 모니터링 및 경보 (최소 구성)

| 대상 | 메트릭 | 경보 조건 |
|------|--------|-----------|
| Lambda | Errors, Duration | 에러율 > 5% |
| Glue | Job Duration, Failure | 실패 시 즉시 |
| SageMaker | Training Time, Spot 중단 | 3회 연속 Spot 중단 |
| Fargate | CPU, Memory, 5xx Rate | CPU > 80%, 5xx > 1% |
| DynamoDB | Throttled Requests | 스로틀 > 0 |
| Step Functions | Execution Failed | 실패 시 즉시 |
| S3 | Storage Size | 월별 리포트 |
| **비용** | AWS Budgets | $100, $200 임계치 |

알림 채널: SNS → Email (MVP) → Slack (프로덕션)

9. 확장 경로 (Non-MVP)

현재 설계에서 프로덕션으로 전환 시 변경점:

| 현재 (MVP) | 프로덕션 | 전환 조건 |
|------------|----------|-----------|
| Kinesis 1 shard | Auto-scaling | 일 10만 이벤트 초과 |
| DynamoDB On-demand | Provisioned + Auto-scaling | 예측 가능한 트래픽 패턴 확보 |
| Fargate Spot 1 태스크 | 2~4 태스크 + On-demand 혼합 | p99 지연 요구 < 200ms |
| Glue 2 DPU | 4~10 DPU | 데이터 > 10GB/일 |
| FAISS (인메모리) | OpenSearch Serverless | 임베딩 > 100K 벡터 |
| CloudWatch 기본 | CloudWatch + X-Ray | 디버깅 복잡도 증가 |
| Step Functions | Step Functions + EventBridge Pipes | 실시간 파이프라인 필요 |

10. 빌드 순서 (인프라 관점)

RFC 의존성 그래프 기반 빌드 순서:

```
Phase A: Storage Foundation (Week 1~2)
  → S3 버킷 + Lifecycle + Iceberg 설정
  → DynamoDB 테이블 생성
  → IAM Roles + VPC Endpoints

Phase B: Ingestion Pipeline (Week 3~4)
  → API Gateway + Lambda + Kinesis + Firehose
  → 로그 스키마 검증 (RFC-LOG-SCHEMA-009)
  → Bronze layer 적재 확인

Phase C: Batch Pipeline (Week 5~8)
  → Glue Jobs (Bronze → Silver → Gold)
  → Step Functions 워크플로
  → Quality Gates (Leakage/Integrity)

Phase D: Feature Engineering (Week 7~10)
  → Feature Manifest 정의
  → Offline Builder (Glue)
  → Online Materializer (Lambda → DynamoDB)
  → Parity Gate CI

Phase E: Training (Week 9~12)
  → SageMaker 학습 설정
  → 베이스라인 4종 학습
  → 평가/벤치마크 파이프라인

Phase F: Serving (Week 11~14)
  → Fargate + ALB 설정
  → FastAPI 앱 배포
  → 서빙 로그 → Kinesis 연결

Phase G: Evaluation Loop (Week 13~16)
  → Counterfactual 평가 파이프라인
  → Long-horizon 승자 판정 규칙
  → 모니터링 + 경보 완성
```

11. Non-Goals

- 멀티 리전 배포 (단일 리전으로 시작)
- GPU 서빙 (CPU 서빙으로 시작, 모델 복잡도 증가 시 전환)
- 실시간 학습 (배치 학습으로 시작)
- Kubernetes/EKS (Fargate로 충분)
- Data Mesh / Lake Formation (초기에는 S3 경로 규약으로 충분)

12. Conclusion

본 RFC는:
- **Serverless-first**: 트래픽 0 = 비용 ~$0 원칙
- **Spot 우선**: 학습/서빙 모두 70% 절감
- **S3 중심 SSOT**: Iceberg 포맷 + Lifecycle 자동 관리
- **Step Functions 오케스트레이션**: MWAA 대비 10x+ 비용 절감
- **Kinesis On-demand**: MSK 대비 1/10 비용

을 고정하여 MVP $42~100/월 이내에서 전체 추천 파이프라인을 운영 가능하게 한다.
