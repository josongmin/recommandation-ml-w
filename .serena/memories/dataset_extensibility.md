# Dataset Builder 확장성 보장 (SOTA급)

## 핵심 설계 원칙 (RFC-DATASET-BUILDER-011)

### 1. Manifest-Driven Architecture
```python
DatasetManifest {
  dataset_version: str          # 변경 시 반드시 bump
  split_id: str                 # 재현성 보장
  feature_set_version: str      # Feature Manifest 연동
  embedding_versions: dict      # 임베딩 버전 추적
  join_rules_json: JoinRules    # Time-travel 규칙
  negative_sampling_spec_json   # Seed 포함 (재현성)
  attribution_spec_json         # Attribution window
}
```

**확장 포인트**:
- ✓ Feature 추가/삭제 → `feature_set_version` bump
- ✓ Embedding 교체 → `embedding_versions` 업데이트
- ✓ Negative sampling 전략 변경 → `method` 수정 (shown_but_no_action → hard_negative)
- ✓ Attribution window 조정 → `window_days` 변경

### 2. Label Hierarchy 확장성
```python
LABEL_VALUES = {
    "purchase": 5,    # 구매
    "cart": 4,        # 장바구니
    "wishlist": 3,    # 위시리스트
    "click": 2,       # 클릭
    "view": 1,        # 조회
    "none": 0,        # 노출만
}
```

**SOTA 확장 시나리오**:
```python
# Multi-task learning
LABEL_VALUES_MULTI_TASK = {
    "engagement": {  # Task 1: Engagement prediction
        "cart": 3, "click": 2, "view": 1, "none": 0
    },
    "conversion": {  # Task 2: Conversion prediction
        "purchase": 1, "none": 0
    }
}

# Graded relevance (NDCG용)
LABEL_RELEVANCE = {
    "purchase": 3,    # Perfect
    "cart": 2,        # Excellent
    "click": 1,       # Good
    "view": 0,        # Fair
    "none": -1,       # Bad (explicitly shown but ignored)
}
```

### 3. Negative Sampling 전략 (학계 SOTA)
**현재 구현**: shown_but_no_action (cap_per_positive=10)

**확장 가능 전략**:
```python
def sample_negatives_strategy(
    strategy: str,
    positives: pl.DataFrame,
    all_items: pl.DataFrame,
    **kwargs
):
    if strategy == "shown_but_no_action":
        # 현재 구현 (Impression-based)
        return _sample_shown_negatives(positives, kwargs["cap_per_pos"])

    elif strategy == "hard_negative_mining":
        # 모델 예측 기반 hard negative 샘플링
        # 높은 score지만 실제 negative인 item 선택
        model_scores = kwargs["model_scores"]
        return _sample_hard_negatives(positives, all_items, model_scores, top_k=50)

    elif strategy == "popularity_biased":
        # 인기도 기반 negative 샘플링 (popularity bias 완화)
        item_popularity = kwargs["item_popularity"]
        return _sample_popularity_negatives(positives, all_items, item_popularity)

    elif strategy == "in_batch_negative":
        # Batch 내 다른 user의 positive를 negative로 사용 (Two-Tower용)
        return _in_batch_negatives(positives, kwargs["batch_size"])
```

### 4. Time-Travel Join 확장성
```python
JoinRules {
  as_of_ts_le_event_ts: bool = True      # 기본: Leakage 방지
  published_at_le_event_ts: bool = True  # Review 리뷰 게시일 체크
}
```

**확장**: Counterfactual Learning 대응
```python
# Offline Evaluation with historical policy
JoinRules {
  as_of_ts_le_event_ts: True,
  historical_policy_cutoff: "2026-01-01T00:00:00Z",  # 특정 시점 정책 재현
  feature_version_pinning: {
    "user_embedding_v1": "fs_v2_20260101",
    "wine_embedding_v1": "fs_v2_20260101"
  }
}
```

### 5. Attribution Spec 확장성
**현재**: Last-impression attribution (7-day window)

**SOTA 확장**:
```python
AttributionSpec {
  rule: str  # 선택 가능 전략
  # - "last_impression_within_window": 기본 (현재)
  # - "first_impression": First-touch attribution
  # - "linear": 모든 impression에 균등 분배
  # - "time_decay": 최근 impression에 더 높은 가중치
  # - "position_based": U-shaped (첫/마지막 40%, 중간 20%)

  version: str
  window_days: int
  decay_half_life_days: int | None  # time_decay용
}

# Multi-touch attribution 예시
def time_decay_attribution(
    impressions: pl.DataFrame,
    conversions: pl.DataFrame,
    half_life_days: int = 3
) -> pl.DataFrame:
    # exp(-ln2 * days_since / half_life)로 가중치 계산
    pass
```

### 6. Split Strategy 확장성
**현재**: Time-based split (70/15/15)

**SOTA 확장**:
```python
def split_dataset(
    df: pl.DataFrame,
    strategy: str,
    **kwargs
) -> pl.DataFrame:
    if strategy == "time_based":
        # 현재 구현 (chronological)
        return _time_split(df, train_ratio=0.7, val_ratio=0.15)

    elif strategy == "user_stratified":
        # User별 분리 (cold-start 평가용)
        # Train users ∩ Test users = ∅
        return _user_split(df, test_user_ratio=0.2)

    elif strategy == "item_stratified":
        # Item별 분리 (cold-start item 평가)
        return _item_split(df, test_item_ratio=0.2)

    elif strategy == "temporal_validation":
        # Rolling window validation (시계열 검증)
        # Week 1-8: train, Week 9: val, Week 10: test
        return _rolling_split(df, train_weeks=8, val_weeks=1, test_weeks=1)
```

### 7. Feature Manifest 통합 (RFC-FEATURE-MANIFEST-010)
```python
FeatureManifest {
  feature_set_version: str
  entities: [
    {
      entity_type: "user_item",  # User-Item pair features
      features: [
        {
          name: "user_wine_affinity_score",
          dtype: "float",
          source: {table: "user_item_ir_v1", key: ["user_id", "wine_core_id"]},
          time_travel_rule: {rule: "as_of_ts_le_event_ts", timestamp_field: "as_of_ts"},
          tier: "critical",  # Parity Gate에서 diff=0 강제
          null_policy: "error"  # NULL 발견 시 빌드 실패
        }
      ]
    }
  ]
}
```

**Parity Gate 확장**:
- Critical tier: Online/Offline diff = 0 (엄격)
- Important tier: diff < 1% 경고
- Experimental tier: 체크 안 함

### 8. Quality Gates 확장성 (RFC-E2E-PIPELINE-006 §5)
**현재**: Leakage, Join Success, Propensity

**SOTA 추가 Gates**:
```python
# Data Quality Gates
- MinSampleGate: 최소 샘플 수 (Train: 10K+, Val: 2K+)
- LabelDistributionGate: Class imbalance 체크 (positive ratio 0.1~30%)
- FeatureCompleteness: Feature 누락률 < 5%
- TemporalConsistency: Train/Val/Test 시간 순서 검증

# Model Quality Gates
- BaselineGate: Random/Popular baseline 대비 성능
- FairnessGate: 특정 subgroup 성능 격차 < 10%
- LatencyGate: Feature 생성 시간 < 100ms (serving)
```

## 학계/업계 SOTA 대응 능력

### 학계 (RecSys/KDD/SIGIR)
- ✓ **Multi-task Learning**: Label hierarchy 확장으로 대응
- ✓ **Counterfactual Learning**: JoinRules + historical_policy_cutoff
- ✓ **Debiasing**: Propensity weighting (policy_log_v1 연동)
- ✓ **Cold-start**: User/Item stratified split 지원

### 업계 (Netflix/Spotify/Amazon)
- ✓ **A/B Testing**: Dataset versioning (manifest-driven)
- ✓ **Online-Offline Parity**: Parity Gate (critical tier)
- ✓ **Feature Engineering**: Feature Manifest + Time-travel join
- ✓ **Scalability**: Polars → PySpark 교체 가능 (interface 동일)

## 마이그레이션 패스

### Polars (Local Dev) → PySpark (Production)
```python
# 현재: Polars
df = pl.read_parquet("data/gold_b/...")
df = df.filter(pl.col("label") > 0)

# Production: PySpark (interface 유지)
df = spark.read.parquet("s3://bucket/gold_b/...")
df = df.filter(col("label") > 0)  # Same logic
```

**호환성 보장**:
- 모든 pipeline 함수는 DataFrame 추상화 사용
- Type hints: `pl.DataFrame | spark.DataFrame` 지원
- 테스트는 Polars로 빠르게, 배포는 Spark로 확장

## 결론
✓ Manifest-driven → 모든 변경 추적 가능
✓ Pluggable strategies → Negative sampling/Attribution/Split 교체 용이
✓ Quality Gates → 데이터 품질 자동 검증
✓ Polars/Spark 호환 → 로컬 개발 → 프로덕션 확장 seamless

**SOTA급 보장**: 학계 논문 재현 + 업계 프로덕션 요구사항 만족
