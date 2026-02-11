RFC-EXEC-PLAN-014

Title: High-End Wine Recommendation — Phase별 구체 실행 계획 & 주차별 산출물 v1
Status: Draft v1.0
Scope: RFC-INFRA-IMPL-013의 AWS 인프라 위에서, RFC-SOTA-ROADMAP-012 Year 0~0.5(SOTA 기초 인프라)를 16주 내에 구현하는 구체 작업 계획을 고정한다.
Depends On:
- RFC-INFRA-IMPL-013: AWS 인프라 스펙
- RFC-E2E-PIPELINE-006: E2E 파이프라인 스펙
- RFC-IR-SCHEMA-007: 저장 스키마 계약
- RFC-LOG-SCHEMA-009: 로그 스키마
- RFC-FEATURE-MANIFEST-010: Feature Manifest & Parity Gate
- RFC-DATASET-BUILDER-011: Dataset Builder
- RFC-DATASET-BENCH-005: Dataset & Benchmark
- RFC-SOTA-ROADMAP-012: 3년 로드맵

0. 목표 (What we deliver)

- 16주(4개월) 내에 RFC-SOTA-ROADMAP-012 §5-1(Year 0~0.5)의 **규정자 5조건 중 #1, #2를 달성**한다.
- 각 주차에 검증 가능한 산출물(artifact)을 명시한다.
- 모든 산출물은 S3 SSOT 경로에 저장되고, 재현 가능해야 한다.

0-1. 최종 산출물 목록 (16주 후)

| # | 산출물 | RFC 근거 | 검증 방법 |
|---|--------|----------|-----------|
| 1 | S3 Data Lake (Iceberg) + Lifecycle | INFRA-013 §1-1 | Terraform apply 성공 |
| 2 | 이벤트 수집 파이프라인 (API GW → Kinesis → S3) | INFRA-013 §1-2 | 테스트 이벤트 → S3 적재 확인 |
| 3 | Bronze → Silver → Gold-A → Gold-B 배치 파이프라인 | E2E-006 §2~5 | Glue Job 성공 + Quality Gate 통과 |
| 4 | dataset_manifest_v1 불변 스펙 | DATASET-BENCH-005 §7-1 | manifest 생성 + 검증 스크립트 |
| 5 | training_examples_v1 + splits_v1 | DATASET-BUILDER-011 §2~7 | Leakage Gate 0% + join_proof 생성 |
| 6 | feature_manifest_v1 (critical 20개) | FEATURE-MANIFEST-010 §1 | Parity Gate CI 통과 |
| 7 | 베이스라인 4종 학습 완료 | SOTA-ROADMAP-012 §5-1 | 동일 manifest 재현 + 평가 리포트 |
| 8 | 벤치마크 스위트 (B0~B3) | DATASET-BENCH-005 §5 | IPS/SNIPS/DR 포함 리포트 |
| 9 | 추천 API 서빙 (Fargate) | INFRA-013 §1-6 | /recommend 엔드포인트 응답 |
| 10 | 모니터링 + 비용 경보 | INFRA-013 §8 | CloudWatch 대시보드 + Budget Alert |

1. Phase A: Storage Foundation (Week 1~2)

1-1. Week 1: IaC 기초 + S3 + IAM

작업:
- [ ] Terraform 프로젝트 초기화 (infra/terraform/)
- [ ] S3 버킷 생성 + Lifecycle 정책 적용
- [ ] IAM Role 생성 (Lambda/Glue/SageMaker/Fargate 각각)
- [ ] VPC + Subnets + VPC Endpoints (S3 Gateway, DynamoDB Gateway)
- [ ] Glue Data Catalog 설정 (Iceberg catalog)

산출물:
```
✓ infra/terraform/modules/storage/ — 적용 완료
✓ S3 버킷: s3://{project}-{env}-data/
✓ IAM: 4개 서비스 Role
✓ VPC: private/public subnet + endpoints
```

검증:
- `terraform plan` → `terraform apply` 성공
- S3 Lifecycle 정책 확인 (콘솔 또는 CLI)
- IAM Role assume 테스트

1-2. Week 2: DynamoDB + Iceberg 테이블 + 경로 규약

작업:
- [ ] DynamoDB 테이블 생성 (features_online_v1, user_profile_v1)
- [ ] Iceberg 테이블 생성 (Glue Catalog에 Gold-A/B 테이블 등록)
- [ ] S3 경로 규약 문서화 (RFC-INFRA-IMPL-013 §3 기반)
- [ ] 초기 데이터 시드 스크립트 작성 (테스트용 와인/리뷰 데이터)

산출물:
```
✓ infra/terraform/modules/feature_store/ — 적용 완료
✓ DynamoDB: 2개 테이블 (On-demand)
✓ Glue Catalog: Iceberg 테이블 등록
✓ scripts/seed_data.py — 테스트 데이터 시드
```

검증:
- DynamoDB 읽기/쓰기 테스트
- Athena에서 Iceberg 테이블 쿼리 확인
- 시드 데이터 S3 업로드 확인

2. Phase B: Ingestion Pipeline (Week 3~4)

2-1. Week 3: 이벤트 수집 Lambda + Kinesis

작업:
- [ ] Lambda: 이벤트 검증/라우팅 함수 구현 (src/ingestion/lambda_handler.py)
- [ ] 로그 스키마 검증기 구현 (RFC-LOG-SCHEMA-009 기반)
- [ ] Kinesis Data Streams 생성 (On-demand, 1 shard)
- [ ] API Gateway HTTP API 설정
- [ ] Terraform 모듈: infra/terraform/modules/ingestion/

스키마 검증 대상 (RFC-LOG-SCHEMA-009):
```python
# 4대 SSOT 로그 스키마
SCHEMAS = {
    "impression_log_v1": {...},
    "action_log_v1": {...},
    "order_log_v1": {...},
    "policy_log_v1": {...}
}
```

산출물:
```
✓ src/ingestion/ — Lambda 코드 완성
✓ infra/terraform/modules/ingestion/ — 적용 완료
✓ API Gateway: POST /events 엔드포인트
✓ Kinesis: wine-events-stream (On-demand)
```

검증:
- curl로 테스트 이벤트 전송 → Lambda 로그 확인
- Kinesis 레코드 도착 확인
- 잘못된 스키마 → 검증 실패 확인

2-2. Week 4: Firehose → S3 Bronze 적재

작업:
- [ ] Kinesis Firehose Delivery Stream 설정 (→ S3 Bronze, Parquet 변환)
- [ ] Lambda Consumer 구현 (실시간 DynamoDB feature 갱신)
- [ ] Bronze layer Parquet 스키마 정의
- [ ] 통합 테스트: 이벤트 → Lambda → Kinesis → Firehose → S3

Firehose 설정:
```yaml
buffer_size: 5 MB
buffer_interval: 300 seconds  # 5분
output_format: parquet
compression: snappy
s3_prefix: bronze/{log_type}/{dt}/
```

산출물:
```
✓ Firehose → S3 Bronze 적재 확인
✓ src/ingestion/ — Lambda Consumer 추가
✓ Bronze layer: Parquet 파일 생성 확인
✓ DynamoDB: 실시간 feature 갱신 확인
```

검증:
- 테스트 이벤트 100건 전송 → 5분 후 S3 Bronze 확인
- Parquet 파일 Athena 쿼리 확인
- DynamoDB 조회로 feature 갱신 확인

3. Phase C: Batch Pipeline (Week 5~8)

3-1. Week 5: Bronze → Silver 정제

작업:
- [ ] Glue Job: bronze_to_silver.py (정제/검증/중복 제거)
- [ ] Silver 스키마 정의 (cleaned, validated)
- [ ] Step Functions 워크플로 정의 시작 (daily_refresh.asl.json)
- [ ] EventBridge 스케줄러 설정 (일간 트리거)

정제 규칙:
```python
# Bronze → Silver 정제 목록
CLEANING_RULES = [
    "deduplicate_by_event_id",
    "validate_schema_version",
    "fill_missing_timestamps",
    "remove_bot_traffic",
    "normalize_user_ids",
]
```

산출물:
```
✓ src/pipeline/bronze_to_silver.py
✓ Glue Job: bronze-to-silver 등록/실행 성공
✓ S3: silver/ 경로에 정제된 Parquet
```

검증:
- Glue Job 실행 → Silver 데이터 행 수 비교
- 중복 레코드 0 확인
- Athena 쿼리로 Silver 데이터 샘플 검증

3-2. Week 6: Silver → Gold-A (SSOT) + Gold-B (IR)

작업:
- [ ] Glue Job: silver_to_gold_a.py (SSOT 테이블 갱신)
- [ ] Glue Job: gold_a_to_gold_b.py (IR 파생 자산 생성)
- [ ] Iceberg 테이블 upsert 로직 구현
- [ ] Gold-A: wine_core_master_v1, wine_sku_master_v1, review_master_v1
- [ ] Gold-B: wine_text_ir_v1, wine_temporal_ir_v1, wine_review_aggregate_ir_v1

Gold-B IR 생성 우선순위 (Phase 1):
```
1. wine_text_ir_v1          — 텍스트 임베딩 (Cold-start 1순위)
2. wine_temporal_ir_v1      — 음용 시기 (Temporal IR)
3. wine_review_aggregate_ir_v1 — 리뷰 집계 (Expert-aware)
4. wine_attr_ir_v1          — 가격/속성 (Price)
5. wine_scarcity_ir_v1      — 희소성 (Scarcity)
```

산출물:
```
✓ src/pipeline/silver_to_gold_a.py
✓ src/pipeline/gold_a_to_gold_b.py
✓ Gold-A: Iceberg 테이블 5종 생성
✓ Gold-B: IR 5종 생성
```

검증:
- Athena: Iceberg 테이블 time-travel 쿼리 성공
- Gold-A → Gold-B 파생 lineage 키 확인 (input_unit_id, transform_version, recipe_version)

3-3. Week 7: Quality Gates + Step Functions 완성

작업:
- [ ] Lambda: quality_gates.py (Leakage Gate, Integrity Gate)
- [ ] Leakage Gate: time-travel 위반 검사 (as_of_ts <= event_ts)
- [ ] Integrity Gate: join 성공률 임계치 검사
- [ ] Step Functions: daily_refresh.asl.json 완성
- [ ] SNS 알림 설정 (실패 시 이메일)

Quality Gate 규칙:
```python
GATES = {
    "leakage_rate": {"threshold": 0.0, "action": "fail"},       # 0% 허용
    "join_success_rate": {"threshold": 0.99, "action": "fail"},  # 99%+
    "schema_mismatch_rate": {"threshold": 0.01, "action": "warn"},
}
```

산출물:
```
✓ src/pipeline/quality_gates.py
✓ Step Functions: daily_refresh 워크플로 완성
✓ EventBridge: 일간 트리거 설정
✓ SNS: 파이프라인 실패 알림
```

검증:
- Step Functions 콘솔에서 전체 워크플로 실행 성공
- 의도적 leakage 주입 → Gate 실패 확인
- SNS 알림 수신 확인

3-4. Week 8: Dataset Builder + Manifest

작업:
- [ ] Glue Job: dataset_builder.py (training_examples_v1 생성)
- [ ] split 생성 (time split only, RFC-DATASET-BUILDER-011 §7)
- [ ] dataset_manifest_v1 생성 스크립트
- [ ] join_proof_audit_v1 생성 + S3 보관
- [ ] Leakage 위반 사례 자동 저장 (leakage_violations)
- [ ] Negative sampling seed 고정

Dataset Manifest 핵심 필드:
```json
{
  "dataset_version": "ds_v1_20260301",
  "split_id": "time_split_v1",
  "feature_set_version": "fs_v1",
  "join_rules_json": {
    "as_of_ts_le_event_ts": true,
    "published_at_le_event_ts": true
  },
  "negative_sampling_spec_json": {
    "method": "shown_but_no_action",
    "cap_per_pos": 10,
    "seed": 42
  },
  "attribution_spec_json": {
    "rule": "last_impression_within_window",
    "version": "attr_v1"
  },
  "candidate_budget_spec_version": "budget_v1"
}
```

산출물:
```
✓ src/pipeline/dataset_builder.py
✓ S3: dataset/training_examples_v1/{version}/
✓ S3: dataset/splits_v1/{version}/
✓ S3: dataset/dataset_manifest_v1/{version}/
✓ S3: artifacts/join_proof_audit_v1/{version}/
✓ scripts/manifest_diff.py (Manifest Diff Tool)
```

검증:
- training_examples_v1 행 수 및 라벨 분포 확인
- splits_v1: train/val/test 기간 겹침 없음 확인
- Leakage Gate: 위반률 0%
- join_proof: 모든 레코드에 as_of_ts + published_at_max 존재
- manifest_diff.py: 두 버전 비교 출력 확인

4. Phase D: Feature Engineering (Week 7~10)

(Week 7~8은 Phase C와 병행 가능)

4-1. Week 9: Feature Manifest 정의 + Offline Builder

작업:
- [ ] feature_manifest_v1.yaml 작성 (critical tier 20개 피처)
- [ ] Offline Builder 구현 (time-travel join 강제)
- [ ] features_offline_v1 생성 (event_ts 기준)
- [ ] recipe_version/transform_version/lineage_input_refs 기록

Critical Tier 20개 피처 (우선순위):
```yaml
# User entity
- user_price_elasticity          # 가격 민감도
- user_avg_rating                # 평균 평점
- user_purchase_count            # 구매 횟수
- user_review_count              # 리뷰 수
- user_preferred_variety_top3    # 선호 품종 Top 3
- user_preferred_region_top3     # 선호 지역 Top 3
- user_taste_embedding           # 취향 임베딩

# Wine_core entity
- item_core_weighted_rating_mean  # 가중 평균 평점 (expert-aware)
- item_core_critic_consensus      # 전문가 합의도
- item_core_temporal_stage        # 현재 음용 단계
- item_core_peak_proximity        # 최적 음용 시기 근접도
- item_core_text_embedding        # 텍스트 임베딩
- item_core_variety               # 품종
- item_core_region                # 지역
- item_core_producer              # 생산자

# Wine_sku entity
- item_sku_median_price           # 중앙 가격
- item_sku_in_stock               # 재고 여부
- item_sku_rarity_score           # 희소성 점수

# Context entity
- ctx_surface                     # 노출 서피스
- ctx_request_hour                # 요청 시간대
```

산출물:
```
✓ src/features/manifest/feature_manifest_v1.yaml (20개 critical)
✓ src/features/offline_builder.py
✓ S3: config/feature_manifest/ — JSON 배포본
```

검증:
- Manifest 스키마 검증 통과
- Offline Builder: 출력 feature 수 = manifest 정의 수
- time-travel 규칙 위반 0건

4-2. Week 10: Online Materializer + Parity Gate

작업:
- [ ] Online Materializer Lambda 구현 (DynamoDB 조회/갱신)
- [ ] Parity Checker 구현 (online vs offline 비교)
- [ ] Parity Gate CI 설정 (GitHub Actions)
- [ ] Parity Diff Histogram 리포트 생성
- [ ] Drift 원인 자동 분류 (data_delay/version_mismatch/logic_bug)

Parity Gate CI 규칙:
```yaml
# .github/workflows/parity_gate.yml
parity_test:
  sample_size: 100
  seed: 42
  critical_tier:
    max_diff: 0          # diff == 0 엄격
    on_failure: block     # CI 실패
  important_tier:
    max_diff: 0
    on_failure: report    # 리포트만 (초기)
  experimental_tier:
    on_failure: report
```

산출물:
```
✓ src/features/online_materializer.py
✓ src/features/parity_checker.py
✓ .github/workflows/parity_gate.yml
✓ S3: artifacts/quality_gate_report_v1/ — Parity Diff Histogram
```

검증:
- Online/Offline 동일 입력 → 동일 출력 (critical tier diff=0)
- GitHub Actions CI 통과
- Parity Diff Histogram 리포트 생성 확인

5. Phase E: Model Training (Week 9~12)

5-1. Week 11: SageMaker 설정 + BPR/Two-Tower

작업:
- [ ] SageMaker 학습 환경 설정 (Spot, 체크포인트, 재시도)
- [ ] Docker 학습 이미지 빌드 + ECR 푸시
- [ ] BPR 모델 구현 (RecBole 기반)
- [ ] Two-Tower 모델 구현 (RecBole 기반)
- [ ] 학습 스크립트: trainer.py (SageMaker 호환)

SageMaker 학습 설정:
```python
estimator = PyTorch(
    entry_point="trainer.py",
    role=sagemaker_role,
    instance_type="ml.g4dn.xlarge",
    instance_count=1,
    use_spot_instances=True,
    max_wait=7200,
    max_run=3600,
    checkpoint_s3_uri=f"s3://{bucket}/checkpoints/",
    hyperparameters={
        "model": "bpr",
        "dataset_version": "ds_v1_20260301",
        "feature_set_version": "fs_v1",
        "epochs": 50,
        "lr": 0.001,
        "batch_size": 1024,
    },
)
```

산출물:
```
✓ infra/docker/training/Dockerfile
✓ src/models/baselines/bpr.py
✓ src/models/baselines/two_tower.py
✓ src/models/training/trainer.py
✓ S3: gold/c_model/models/bpr_v1/ — 학습된 모델
✓ S3: gold/c_model/models/two_tower_v1/ — 학습된 모델
```

검증:
- SageMaker 학습 Job 성공 (Spot 인스턴스)
- 모델 아티팩트 S3 저장 확인
- 체크포인트 저장/복원 테스트

5-2. Week 12: LightGCN/DeepFM + 평가 파이프라인

작업:
- [ ] LightGCN 모델 구현 (PyG 기반)
- [ ] DeepFM/DLRM 모델 구현 (RecBole 기반)
- [ ] 평가 스크립트: evaluator.py (Recall@K, NDCG@K, Hit@K)
- [ ] Counterfactual 평가: counterfactual.py (IPS/SNIPS/DR)
- [ ] 벤치마크 스위트 실행 스크립트: run_benchmark.sh

벤치마크 스위트 (RFC-DATASET-BENCH-005):
```
B0: General — 전체 데이터, 표준 메트릭
B1: Cold-start — 새 와인/유저만, Recall@K
B2: High-end slice — 가격 상위 N%, 희소 와인만
B3: Temporal-fit — peak proximity 반영 메트릭
```

산출물:
```
✓ src/models/baselines/lightgcn.py
✓ src/models/baselines/deepfm.py (+ dlrm.py)
✓ src/models/evaluation/evaluator.py
✓ src/models/evaluation/counterfactual.py
✓ scripts/run_benchmark.sh
✓ S3: artifacts/eval_reports/ — 4종 모델 × 4종 벤치 = 16개 리포트
```

검증:
- 베이스라인 4종 모두 동일 dataset_manifest에서 학습/평가 완료
- 평가 리포트에 IPS/SNIPS/DR 포함 확인
- cold-start / high-end slice 별도 리포트 확인

6. Phase F: Serving (Week 11~14)

6-1. Week 13: FastAPI + Fargate 배포

작업:
- [ ] FastAPI 앱 구현 (src/serving/app.py)
- [ ] Multi-Recall 추천 로직 (src/serving/recommender.py)
- [ ] Feature Client (DynamoDB 조회, src/serving/feature_client.py)
- [ ] Docker 서빙 이미지 빌드 + ECR 푸시
- [ ] Fargate Service + ALB 설정 (Terraform)

API 엔드포인트:
```
POST /recommend
  Input: { user_id, context, n_items }
  Output: { items: [...], explanations: [...] }

GET /health
  Output: { status: "ok", model_version, feature_set_version }
```

Multi-Recall 전략 (v1):
```python
RECALL_SOURCES = [
    {"name": "collaborative", "model": "bpr_v1", "quota": 50},
    {"name": "content", "model": "two_tower_v1", "quota": 50},
    {"name": "graph", "model": "lightgcn_v1", "quota": 30},
    {"name": "popular", "model": "popularity", "quota": 20},
]
# 총 후보 ~150개 → Ranker(DeepFM/DLRM) → Top-K
```

산출물:
```
✓ src/serving/ — FastAPI 앱 완성
✓ infra/docker/serving/Dockerfile
✓ infra/terraform/modules/serving/ — Fargate + ALB
✓ ALB 엔드포인트로 /recommend 호출 가능
```

검증:
- /health 응답 확인
- /recommend 테스트 요청 → 추천 결과 반환
- Fargate Spot 태스크 실행 확인
- p99 지연 측정

6-2. Week 14: 서빙 로그 + 피드백 루프

작업:
- [ ] 서빙 로그 → Kinesis → S3 파이프라인 연결
- [ ] impression_log, policy_log 자동 생성
- [ ] 설명 시스템 구현 (temporal/expert/scarcity/price)
- [ ] 서빙 → 학습 피드백 루프 완성

설명 템플릿 (v1):
```python
EXPLANATION_TEMPLATES = {
    "temporal": "현재 최적 음용 시기인 와인입니다 (peak stage)",
    "expert": "전문가 평균 {score}점, 높은 합의도 ({consensus}%)",
    "scarcity": "연간 생산량 {volume}병, 희소성 높음",
    "price": "가격 대비 전문가 평가가 우수합니다",
    "discovery": "같은 지역의 숨겨진 생산자 발견",
}
```

산출물:
```
✓ src/serving/explainer.py — 설명 생성
✓ 서빙 로그 → Kinesis → S3 Bronze 적재 확인
✓ 피드백 루프: 서빙 로그 → 다음 배치 학습 데이터에 포함
```

검증:
- /recommend 응답에 explanations 포함 확인
- 서빙 로그 S3 적재 확인 (impression_log, policy_log)
- 다음 Daily Refresh에서 서빙 로그 반영 확인

7. Phase G: Evaluation Loop + 완성 (Week 13~16)

7-1. Week 15: Counterfactual 평가 + Long-horizon 규칙

작업:
- [ ] Counterfactual 평가 파이프라인 통합 (Step Functions)
- [ ] IPS/SNIPS/DR 모든 벤치 리포트 필수 포함 확인
- [ ] Long-horizon 승자 판정 규칙 구현
- [ ] propensity 누락률 모니터링 게이트 (>5% 경보, >20% 차단)

Long-horizon 규칙:
```python
WINNER_RULES = {
    "7d_repurchase_decline": {
        "threshold": -0.05,      # 5% 이상 하락
        "action": "block_deploy"  # 배포 불가
    },
    "30d_repurchase_decline": {
        "threshold": -0.03,      # 3% 이상 하락
        "action": "block_deploy"
    },
    "short_term_only_improvement": {
        "condition": "ctr_up AND repurchase_down",
        "action": "tag_short_term_only"  # 태그만, 배포 불가
    }
}
```

산출물:
```
✓ Counterfactual 평가가 모든 벤치에 포함
✓ Long-horizon 규칙 구현 + 테스트
✓ propensity 모니터링 게이트 작동
```

검증:
- 벤치 리포트에 IPS/SNIPS/DR 수치 존재 확인
- 의도적 repurchase 하락 시나리오 → 배포 차단 확인
- propensity 누락 20% 초과 시 → 차단 확인

7-2. Week 16: 통합 테스트 + 모니터링 + 마무리

작업:
- [ ] E2E 통합 테스트 (이벤트 수집 → 학습 → 서빙 → 피드백)
- [ ] CloudWatch 대시보드 구성
- [ ] AWS Budget Alert 설정 ($100, $200)
- [ ] 비용 리포트 초회 작성
- [ ] 전체 Terraform 상태 정리 + 문서화
- [ ] README.md 업데이트

모니터링 대시보드:
```
Dashboard: WineRec-MVP
├── Pipeline Health
│   ├── Daily Refresh 성공/실패
│   ├── Glue Job Duration
│   └── Quality Gate 통과율
├── Serving
│   ├── Request Count / Latency (p50, p95, p99)
│   ├── 5xx Rate
│   └── Fargate CPU/Memory
├── Data Quality
│   ├── Leakage 위반률 (0이어야 함)
│   ├── Parity Diff (critical tier)
│   └── Feature Null Rate
└── Cost
    ├── 일별 비용 추이
    ├── 서비스별 비용 분포
    └── Budget vs Actual
```

산출물:
```
✓ tests/e2e/ — 통합 테스트 통과
✓ CloudWatch 대시보드 4개 패널
✓ Budget Alert: $100, $200
✓ 비용 리포트 v1
✓ README.md 업데이트 완료
```

검증:
- E2E: 이벤트 전송 → 24시간 후 학습 데이터 반영 → 모델 재학습 → 서빙 확인
- 전체 비용 < $100/월 확인
- 모든 Quality Gate 통과 상태

8. 주차별 요약 (타임라인)

```
Week  1: ████ Storage Foundation (S3 + IAM + VPC)
Week  2: ████ DynamoDB + Iceberg + 시드 데이터
Week  3: ████ Lambda + Kinesis + API Gateway
Week  4: ████ Firehose → S3 Bronze 적재
Week  5: ████ Bronze → Silver (Glue)
Week  6: ████ Silver → Gold-A/B (SSOT + IR)
Week  7: ████ Quality Gates + Step Functions ─────────┐
Week  8: ████ Dataset Builder + Manifest               │ 병행 가능
Week  9: ████ Feature Manifest + Offline Builder ──────┘
Week 10: ████ Online Materializer + Parity Gate
Week 11: ████ SageMaker + BPR/Two-Tower ──────────────┐
Week 12: ████ LightGCN/DeepFM + 벤치마크               │ 병행 가능
Week 13: ████ FastAPI + Fargate 배포 ─────────────────┘
Week 14: ████ 서빙 로그 + 피드백 루프
Week 15: ████ Counterfactual + Long-horizon 규칙
Week 16: ████ 통합 테스트 + 모니터링 + 마무리
```

9. 의존성 그래프 (크리티컬 패스)

```
Week 1~2 (Storage)
    │
    ▼
Week 3~4 (Ingestion) ──────────────────────────────┐
    │                                                │
    ▼                                                │
Week 5~6 (Batch: Bronze→Gold)                       │
    │                                                │
    ├──▶ Week 7~8 (Quality Gates + Dataset Builder)  │
    │       │                                        │
    │       ▼                                        │
    ├──▶ Week 9~10 (Feature Engineering)             │
    │       │                                        │
    │       ▼                                        │
    └──▶ Week 11~12 (Training) ◀─────────────────────┘
            │
            ▼
        Week 13~14 (Serving)
            │
            ▼
        Week 15~16 (Eval Loop + 완성)
```

크리티컬 패스: Storage → Ingestion → Batch → Dataset Builder → Training → Serving → Eval Loop
병행 가능: Feature Engineering은 Dataset Builder와 병행, Serving은 Training과 병행

10. 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| SageMaker Spot 확보 실패 | 중 | 학습 지연 | 3회 재시도 + On-demand 폴백 |
| Glue Job 느림 (대용량) | 저 | 파이프라인 지연 | DPU 증가 (2→4) |
| Kinesis 지연 | 저 | 실시간 feature 지연 | Buffer interval 조정 |
| 초기 데이터 부족 | 고 | 모델 품질 저하 | 합성 데이터 생성 + Public dataset 활용 |
| 비용 초과 | 중 | 예산 문제 | Budget Alert + 즉시 리뷰 |
| Fargate Spot 회수 | 중 | 서빙 중단 | On-demand 20% 혼합 |

초기 데이터 부족 대응 전략:
```
1. Public dataset 활용:
   - Vivino 공개 리뷰 데이터
   - Wine-Searcher 가격 데이터 (크롤링 주의)
   - CellarTracker 공개 부분

2. 합성 데이터:
   - wine_core: 품종/지역/생산자 조합 생성
   - review: LLM 기반 리뷰 합성 (온톨로지 기반)
   - impression: 시뮬레이션 로그 생성

3. 소규모 실제 데이터:
   - 내부 테스터 10~50명 기반 시작
   - onboarding quiz → pseudo-profile 생성
```

11. 규정자 5조건 매핑

| 규정자 조건 | 달성 Phase | 핵심 산출물 |
|-------------|-----------|-------------|
| #1 재현 가능한 데이터/평가 프로토콜 | Phase C (Week 8) | dataset_manifest_v1 + join_proof |
| #2 반사실 평가 기본 탑재 | Phase G (Week 15) | IPS/SNIPS/DR 모든 벤치 필수 |
| #3 도메인 고유 난제 정의 | Phase E (Week 12) | B1(cold-start) + B2(high-end) + B3(temporal) |
| #4 외부 검증 루프 | Year 0.5~1.5 | 리더보드 (본 계획 범위 밖) |
| #5 Long-horizon 목적함수 | Phase G (Week 15) | 7d/30d 재구매율 승자 판정 |

→ 16주 내에 #1, #2, #3, #5 달성. #4는 Year 0.5~1.5에서 달성 (RFC-SOTA-ROADMAP-012 §5-2).

12. Conclusion

본 실행 계획은:
- **16주(4개월)** 내에 MVP 추천 시스템 전체 파이프라인 구축
- **규정자 5조건 중 4개(#1, #2, #3, #5)** 달성
- **월 $42~100 이내** 비용으로 운영
- 모든 산출물은 **S3 SSOT + Iceberg + Manifest**로 재현 가능

을 보장한다.
