# 모듈 경계 규칙 (Module Boundary Rules)

## 강제 규칙 (pyproject.toml L130-140)

### 금지된 임포트
```python
# ❌ pipeline internals를 외부에서 import 금지
from wine_rec.pipeline.bronze_to_silver import ...
from wine_rec.pipeline.silver_to_gold_a import ...
from wine_rec.pipeline.gold_a_to_gold_b import ...
from wine_rec.pipeline.dataset_builder import ...

# ❌ models → serving 금지
from wine_rec.serving.app import ...
from wine_rec.serving.recommender import ...

# ❌ ingestion → models 금지
from wine_rec.models import ...
```

### 허용된 의존성
```python
# ✅ 모든 모듈 → Shared Kernel
from wine_rec.schemas.events import ImpressionEvent
from wine_rec.contracts.event_stream import EventStream

# ✅ 서비스 → Adapter
from wine_rec.infra.s3_object_store import S3ObjectStore

# ✅ pipeline 내부끼리는 OK (pipeline.__init__.py에서 통제)
# pipeline/quality_gates.py에서:
from wine_rec.pipeline.temporal_estimator import TemporalEstimator
```

## 의존성 방향

```
┌──────────────────────────────────────┐
│       Shared Kernel (schemas,        │
│          contracts)                  │
└────────────┬─────────────────────────┘
             ▲
             │ (모든 모듈이 의존 가능)
             │
┌────────────┴─────────────────────────┐
│  Business Modules                    │
│  - ingestion                         │
│  - pipeline                          │
│  - features                          │
│  - models                            │
│  - serving                           │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  Adapters (infra)                    │
│  - s3_object_store                   │
│  - dynamodb_feature_store            │
│  - kinesis_event_stream              │
└──────────────────────────────────────┘
```

## 위반 체크
```bash
# ruff가 자동으로 체크
just lint
# → TID251 에러 발생 시 모듈 경계 위반
```

## 설계 원칙
1. **Pipeline은 블랙박스**: 외부는 pipeline 내부 구현 알 필요 없음
2. **Serving은 독립적**: Models가 Serving API에 의존하면 순환 의존 발생
3. **Ingestion은 가벼움**: ML 모델 로딩하면 Lambda 콜드스타트 증가
