# Week 9-10 완료 보고서 (Feature Engineering)

## 완료 날짜
2026-02-11

## 산출물 (RFC-EXEC-PLAN-014 §9-10 기준)

### ✅ Feature Manifest v2 (RFC-FEATURE-MANIFEST-010)
```yaml
feature_set_version: fs_v2
entities:
  - user:        17 features (embeddings, behavior, demographics)
  - session:      5 features (time, device, context)
  - wine_core:   14 features (core, temporal_v2, expert)
  - wine_sku:     8 features (price, availability, scarcity)
  - context:      4 features (surface, position, campaign)
  - user_item:    7 features (affinity, co-occurrence, CTR)

Total: 55 features
```

**Tier 분류**:
- Critical (21개): Online/Offline parity diff=0 강제
- Important (19개): diff < 1% 경고
- Experimental (15개): 체크 안 함

### ✅ Offline Feature Builder (94% coverage)
```python
src/wine_rec/features/offline_builder.py
- load_manifest(): YAML → FeatureManifest Pydantic
- time_travel_filter(): as_of_ts <= event_ts 강제
- extract_feature_value(): Table join + NULL policy
- apply_null_policy(): error|default|allow_null
- cast_default(): dtype 변환 (float|int|bool|string|vector)
- build_offline_features(): End-to-end orchestration
```

**Time-Travel Rules**:
```python
- as_of_ts_le_event_ts: 가장 엄격 (leakage 방지)
- published_at_le_event_ts: Review 게시일 체크
- none: Static feature (e.g., wine_type)
```

### ✅ Online Feature Materializer (97% coverage)
```python
src/wine_rec/features/online_materializer.py
- WineCoreUpdated: wine_core_master 변경 시 DynamoDB 업데이트
- TextUnitAdded: 텍스트 임베딩 갱신
- StructUnitAdded: 구조화 필드 갱신
- PriceSnapshotAdded: 가격 변동 반영
- EmbeddingEncoderRolled: 임베딩 버전 업데이트
- ExpertAggregateUpdated: Expert-aware 필드 (v2)
- TemporalV2Updated: Temporal IR v2 필드
```

**Event-Driven Architecture**:
```
Gold-B IR 변경
  → Kinesis Event
  → Lambda (online_materializer)
  → DynamoDB features_online_v1 업데이트
```

### ✅ Parity Checker (100% coverage)
```python
src/wine_rec/features/parity_checker.py
- check_parity(): Online vs Offline feature diff 검증
- critical tier: diff = 0 (엄격)
- important tier: diff < eps (1e-6)
- experimental tier: 항상 pass
```

**Parity Gate 통과 조건**:
```python
for feature in manifest.critical_features:
    assert online[feature] == offline[feature]  # Exact match

for feature in manifest.important_features:
    assert abs(online[feature] - offline[feature]) < 1e-6  # Epsilon tolerance
```

## Feature Manifest 구조 (fs_v2)

### User Entity (17 features)
```yaml
- user_embedding_v1 (critical, vector[128])
- user_purchase_count_30d (important, int)
- user_avg_rating_given (experimental, float)
- user_preferred_wine_type (important, string)
- user_lifetime_spend (critical, float)
...
```

### Wine Core Entity (14 features)
```yaml
- wine_embedding_v1 (critical, vector[128])
- wine_weighted_rating (critical, float)
- wine_critic_consensus (important, float)
- wine_temporal_stage (important, string)  # too_young|early|peak|past
- wine_expert_agreement_pct (experimental, float)  # v2
- wine_inter_expert_variance (experimental, float)  # v2
...
```

### User-Item Entity (7 features)
```yaml
- user_wine_affinity_score (critical, float)
- user_wine_ctr_60d (important, float)
- user_wine_cooccurrence_score (experimental, float)
...
```

## 테스트 결과
- **43개 feature 테스트** 전체 통과
- **Coverage**: offline_builder 94%, online_materializer 97%, parity_checker 100%
- **Manifest 검증**: YAML → Pydantic 스키마 변환 성공

## RFC 준수
- ✓ RFC-FEATURE-MANIFEST-010: Feature Manifest SSOT
- ✓ RFC-E2E-PIPELINE-006 §6: Parity Gate
- ✓ RFC-REC-EXT-004: Expert-Aware features (v2)
- ✓ Time-Travel Join 엄격 적용 (leakage 0%)

## 확장성 포인트

### 1. Feature 추가
```yaml
# manifest에 추가
- name: user_wine_recent_dwell_time_ms
  dtype: float
  source: {table: action_log_v1, key: [user_id, wine_sku_id]}
  time_travel_rule: {rule: as_of_ts_le_event_ts, timestamp_field: action_ts}
  tier: experimental  # 처음엔 experimental, 검증 후 critical로 승격
  null_policy: default
  default: 0.0
```

### 2. Embedding 교체
```yaml
# v1 → v2 마이그레이션
- name: user_embedding_v2
  dtype: vector
  source: {table: user_embedding_ir_v2, key: user_id}
  recipe_version: "sentence_transformers_v2"  # 버전 명시
  embedding_dim: 256  # 128 → 256 확장
```

### 3. Tier 승격/강등
```yaml
# Experimental → Critical 승격 (Parity 검증 완료 후)
- name: wine_temporal_stage
  tier: critical  # experimental → critical
  null_policy: error  # allow_null → error (엄격)
```

## 예상 비용 (Week 9-10 추가)
- Lambda (Online Materializer): ~$5/month
- DynamoDB Write (feature update): ~$10/month
- **Total 추가: ~$15/month**
- **누적: ~$70/month**

## 다음 작업 (Week 11-12)
- Model Training (BPR, Two-Tower, LightGCN, DeepFM)
- RecBole 통합
- Hyperparameter tuning (Optuna)
- Model Registry (MLflow or custom S3)
