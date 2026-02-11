# Week 5-8 완료 보고서 (Batch Pipeline)

## 완료 날짜
2026-02-11

## 산출물 (RFC-EXEC-PLAN-014 §5-8 기준)

### ✅ Python 파이프라인 구현 (Polars 기반)
```python
src/wine_rec/pipeline/
├── bronze_to_silver.py      # 98% coverage, 108 tests passed
├── silver_to_gold_a.py       # 85% coverage
├── gold_a_to_gold_b.py       # 96% coverage (v1+v2 IR)
├── dataset_builder.py        # 91% coverage
├── quality_gates.py          # 77% coverage
└── temporal_estimator.py     # 98% coverage
```

**주요 기능**:
- Deduplication (event_id/impression_id)
- Timestamp normalization (UTC)
- Null validation (required fields)
- Enrichment (action/order aggregates)
- IR generation (6종: review_agg v1/v2, temporal v1/v2, scarcity, expert_profile)
- Quality Gates (Leakage/Join/Propensity)

### ✅ Terraform Pipeline Module
```
infra/terraform/modules/pipeline/
├── main.tf        # Glue Jobs 4종 + Step Functions + EventBridge
├── variables.tf   # s3_bucket_name, glue_role_arn
└── outputs.tf     # step_functions_arn, glue job names
```

**생성 리소스** (14개 .tf 파일 총):
- Glue Jobs: bronze_to_silver, silver_to_gold_a, gold_a_to_gold_b, dataset_builder
- Step Functions: daily_pipeline (Glue job orchestration)
- EventBridge: daily trigger (01:00 UTC)
- IAM Roles: step_functions, eventbridge

### ✅ Quality Gates (RFC-E2E-PIPELINE-006 §5)
```python
- LeakageGate: as_of_ts <= event_ts (0% 허용)
- JoinSuccessGate: join 성공률 99%+
- PropensityGate: 누락률 5% 경고, 20% 차단
```

### ✅ IR Assets (Gold-B)
**v1 (Week 5-8 MVP)**:
- wine_review_aggregate_ir_v1: weighted_rating_mean, critic_consensus_score
- wine_temporal_ir_v1: drinking_window (rule-based)
- wine_scarcity_ir_v1: rarity_score (review count 역수)

**v2 (Phase H SOTA 확장)**:
- wine_review_aggregate_ir_v2: temporal_decay, inter/intra expert variance, consensus_category
- expert_profile_ir_v1: author aggregates, authority_score, specialization_tags
- wine_temporal_ir_v2: peak_trajectory, merged_confidence (rule/model/expert)

## Step Functions 워크플로
```json
BronzeToSilver
  → SilverToGoldA
  → GoldAToGoldB
  → DatasetBuilder
  → Success
```

- **실행 주기**: Daily 01:00 UTC (EventBridge cron)
- **Retry**: 각 Glue job 1회
- **Timeout**: 60-90분
- **Error Handling**: Catch → FailureNotification

## 테스트 결과
- **108개 pipeline 테스트** 전체 통과
- **Coverage**: bronze_to_silver 98%, gold_a_to_gold_b 96%
- **Dataset Builder**: 91% coverage (leakage/join/propensity gates)

## 예상 비용 (Week 5-8 추가)
- Glue Jobs (G.1X × 2, daily 1h): ~$15/month
- Glue Jobs (G.2X × 3, dataset builder): ~$25/month
- Step Functions: ~$1/month
- EventBridge: Free
- **Total 추가: ~$41/month**
- **누적: ~$55/month**

## RFC 준수
- ✓ RFC-E2E-PIPELINE-006: Bronze → Silver → Gold-A → Gold-B → Dataset
- ✓ RFC-LOG-SCHEMA-009: 4대 SSOT 로그 (impression/action/order/policy)
- ✓ RFC-FEATURE-MANIFEST-010: Feature Manifest + Parity Gate (Week 9-10)
- ✓ RFC-DATASET-BUILDER-011: Impression-Centric Dataset Builder
- ✓ RFC-REC-EXT-004: Expert-Aware IR (v2)

## 다음 작업 (Week 9-10)
- Feature Engineering (Manifest + Parity Gate)
- Online Materialization (DynamoDB feature update Lambda)
