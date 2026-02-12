# Testing Guide

## 테스트 구조

```
tests/
├── unit/               # 단위 테스트 (376개)
│   ├── features/
│   ├── models/
│   ├── pipeline/
│   ├── serving/
│   ├── monitoring/
│   └── infra/         # ✨ S3ModelRegistry 포함
├── integration/       # 통합 테스트 (8개)
│   └── test_full_recommendation_flow.py
└── e2e/              # E2E 테스트 (LocalStack)
    ├── conftest.py
    └── test_recommendation_flow.py
```

## 빠른 실행

### 1. 단위 테스트
```bash
# 전체 실행
just test

# 특정 모듈
pytest tests/unit/serving/ -xvs

# 커버리지 포함
pytest --cov=src/wine_rec --cov-report=html
```

### 2. 통합 테스트
```bash
# Recommender 통합 테스트 (AWS 불필요)
pytest tests/integration/ -m integration -xvs
```

### 3. E2E 테스트 (LocalStack)
```bash
# LocalStack 시작 + E2E 테스트 + 정리
./scripts/run_e2e_tests.sh

# 또는 수동
docker-compose -f docker-compose.localstack.yml up -d
export LOCALSTACK_ENDPOINT=http://localhost:4566
pytest tests/e2e/ -m e2e -xvs
docker-compose -f docker-compose.localstack.yml down
```

## 테스트 결과 (2024-02-12)

| 카테고리 | 개수 | 상태 | 커버리지 |
|---------|------|------|---------|
| 단위 테스트 | 376개 | 368 통과, 8 스킵 | 63% |
| 통합 테스트 | 8개 | 8 통과 | - |
| E2E 테스트 | 6개 | LocalStack 필요 | - |
| **합계** | **390개** | **384 통과** | **63%** |

**스킵된 8개**: FAISS segfault (Python 3.13, production은 Python 3.11)

## 주요 테스트 시나리오

### A. Recommender 플로우
```python
# tests/integration/test_full_recommendation_flow.py
def test_recommend_with_model_registry():
    """Model Registry를 통한 추천"""
    recommender = Recommender(
        feature_store=mock_feature_store,
        model_registry=mock_model_registry,
    )
    results = recommender.recommend(user_id="u1", n_items=10)
    assert len(results) == 10
```

### B. S3 Model Registry
```python
# tests/unit/infra/test_s3_model_registry.py
def test_save_and_load_model():
    """모델 저장 및 로드"""
    registry.save_model(model, "bpr", "v1")
    artifact = registry.load_model("bpr", "v1")
    assert artifact.version == "v1"
```

### C. Feature Store
```python
# tests/unit/infra/test_dynamodb_feature_store.py
def test_get_features():
    """DynamoDB에서 feature 조회"""
    features = store.get_features("user", "user_123")
    assert "user_age" in features
```

### D. A/B Testing
```python
# tests/unit/monitoring/test_ab_test.py
def test_stable_assignment():
    """Hash 기반 안정적 할당"""
    v1 = ab.assign_variant(user_id="u1")
    v2 = ab.assign_variant(user_id="u1")
    assert v1.variant_id == v2.variant_id
```

### E. Business Metrics
```python
# tests/unit/monitoring/test_business_metrics.py
def test_diversity_metrics():
    """임베딩 기반 ILS 계산"""
    diversity = compute_diversity_metrics(
        recommended_items=["w1", "w2"],
        item_embeddings=embeddings,
        ...
    )
    assert 0 < diversity.intra_list_diversity < 2
```

## Mock vs LocalStack

### Mock 사용 (통합 테스트)
- ✅ 빠름 (1.3초)
- ✅ 의존성 없음
- ❌ 실제 AWS 동작과 차이 있을 수 있음

```python
mock_feature_store = Mock()
mock_feature_store.get_features.return_value = {...}
```

### LocalStack 사용 (E2E 테스트)
- ✅ 실제 AWS API 사용
- ✅ S3/DynamoDB/Kinesis 통합 검증
- ❌ Docker 필요, 느림 (20초+)

```bash
export LOCALSTACK_ENDPOINT=http://localhost:4566
pytest tests/e2e/ -m e2e
```

## CI/CD

### GitHub Actions (예상)
```yaml
- name: Unit Tests
  run: just test

- name: Integration Tests
  run: pytest tests/integration/ -m integration

- name: E2E Tests (LocalStack)
  run: ./scripts/run_e2e_tests.sh
```

### Pre-commit Hooks
```bash
just hooks  # ruff format + typecheck + test
```

## 커버리지 목표

| 모듈 | 목표 | 현재 |
|------|------|------|
| features/ | 80% | 94% ✅ |
| serving/ | 80% | 87% ✅ |
| monitoring/ | 70% | 76% ✅ |
| pipeline/ | 70% | 91% ✅ |
| models/ | 60% | 40% ⚠️ |
| infra/ | 80% | 100% ✅ |
| **전체** | **55%** | **63%** ✅ |

## 트러블슈팅

### FAISS segfault
```bash
# Python 3.13에서 발생
# 해결: Python 3.11 사용 또는 테스트 스킵
pytest -m "not ann_index"
```

### LocalStack 연결 실패
```bash
# Health check
curl http://localhost:4566/_localstack/health

# 재시작
docker-compose -f docker-compose.localstack.yml restart
```

### 커버리지 부족
```bash
# HTML 리포트로 누락 확인
pytest --cov=src/wine_rec --cov-report=html
open htmlcov/index.html
```
