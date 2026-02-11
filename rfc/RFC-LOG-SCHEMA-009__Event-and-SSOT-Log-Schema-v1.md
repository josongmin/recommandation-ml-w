RFC-LOG-SCHEMA-009

Title: 하이엔드 와인 추천 — 이벤트/SSOT 로그 스키마 v1 (필드·타입·예시 JSON 확정)
Status: Draft v1.0
Scope: 실시간 파이프라인의 SSOT(append-only) 로그 계약을 “필드/타입/예시 JSON”까지 고정한다.
Depends On:
- RFC-REALTIME-PIPELINE-008: 실시간 파이프라인 E2E 흐름 및 Non-Negotiable
- RFC-IR-SCHEMA-007: 오프라인/골드/매니페스트 저장 스키마(중복 정의 금지)

0. 목표 (What we freeze)

- Impression 단위로 노출/정책/행동/주문이 1:1 또는 1:N으로 조인 가능해야 한다(재현성의 핵).
- time-travel 누설 차단을 위해, 모든 로그는 event_ts와 함께 “관측 시각” 및 “버전 메타”를 필수로 가진다.
- Online Serving이 생성한 후보/점수/버전이 policy_log에 남아야 한다(오프라인에서 동일 후보집합 재구성이 가능해야 함).

1. 공통 규칙 (All Events)

1-1. 공통 필드 (필수)

- event_id: string (ULID 권장)  // “레코드” 단위 dedup 키
- trace_id: string
- request_id: string
- session_id: string
- user_id: string
- event_ts: timestamp (UTC)       // 의미 시각(클라이언트 기준)
- ingest_ts: timestamp (UTC)      // 서버 수집 시각(관측 시각)
- surface: string                 // home/search/list/pdp
- locale: string                  // ko-KR 등
- device: string                  // ios/android/web 등(표준화 필요)
- schema_version: string          // 예: "v1"

내 의견(운영 관측에서 가장 값 나가는 필드)
- ingest_ts가 없으면 “이벤트가 늦게 들어온 건지, 시스템이 늦게 처리한 건지”가 분리되지 않는다.
- event_id가 없으면 “재전송/중복”을 시스템적으로 제거하기 어렵다.

1-2. ID 규칙

- impression_id: string (ULID 권장)  // 학습 SSOT 단위
- request_id는 Serving API 요청 단위, impression_id는 “노출(응답)” 단위로 분리한다.

1-3. item_id 규칙

- 모든 item payload는 wine_core_id + wine_sku_id를 함께 포함한다.
- 단, 후보생성/학습 단위는 wine_core 중심을 권장하고, 최종 노출/구매는 wine_sku 중심을 권장한다(정의는 policy_version으로 고정).

2. ImpressionEvent / impression_log_v1

2-1. Schema (필드)

- impression_id: string
- shown_ts: timestamp (UTC)            // 실제 노출 시각
- items: array<struct<
    wine_core_id: string,
    wine_sku_id: string,
    position: int32
  >>
- rec_context: struct<
    surface: string,
    query: string nullable,
    filters_json: string nullable,
    page: int32 nullable,
    ab_test_buckets: map<string,string> nullable
  >
- model_meta: struct<
    policy_version: string,
    serving_model_version: string nullable,
    index_versions: map<string,string> nullable
  >

2-2. Example JSON

{
  "schema_version": "v1",
  "event_id": "01J...ULID",
  "trace_id": "trc_...",
  "request_id": "req_...",
  "session_id": "sess_...",
  "user_id": "u_123",
  "event_ts": "2026-02-09T10:00:00Z",
  "ingest_ts": "2026-02-09T10:00:00.120Z",
  "surface": "home",
  "locale": "ko-KR",
  "device": "ios",
  "impression_id": "01J...ULID",
  "shown_ts": "2026-02-09T10:00:00Z",
  "items": [
    {"wine_core_id": "core_1", "wine_sku_id": "sku_1", "position": 1},
    {"wine_core_id": "core_2", "wine_sku_id": "sku_2", "position": 2}
  ],
  "rec_context": {
    "surface": "home",
    "query": null,
    "filters_json": null,
    "page": 1,
    "ab_test_buckets": {"exp_home_ranker":"B"}
  },
  "model_meta": {
    "policy_version": "policy_v1",
    "serving_model_version": "ranker_heavy_v12",
    "index_versions": {"ann_hnsw":"idx_v8"}
  }
}

3. PolicyLog / policy_log_v1

3-1. Schema (필드)

- impression_id: string (PK/FK)
- policy_version: string
- candidate_set_id: string
- exploration_policy: struct<
    policy_name: string nullable,        // epsilon_greedy|ts|ucb|none
    policy_version: string nullable,
    epsilon: float32 nullable,
    temperature: float32 nullable,
    seed: int64 nullable
  >
- budgets: struct<
    recall_caps: map<string,int32>,
    merge_cap: int32,
    rerank_caps: struct<light:int32, heavy:int32>
  >
- candidates: array<struct<
    wine_core_id: string,
    wine_sku_id: string,
    candidate_source: string,     // channel name
    recall_score: float32 nullable,
    recall_rank: int32 nullable,
    propensity: float32 nullable,         // P(item shown | policy) for counterfactual eval (IPS/SNIPS/DR)
    propensity_model: string nullable     // logged|estimated + version tag
  >>
- rank_outputs: array<struct<
    wine_sku_id: string,
    light_score: float32 nullable,
    heavy_score: float32 nullable,
    final_rank: int32
  >>
- postrank: struct<
    diversity_applied: array<string> nullable,
    constraint_filters_applied: array<string> nullable,
    explanation_keys: array<string> nullable
  >

3-2. Example JSON (요지)

{
  "schema_version": "v1",
  "event_id": "01J...ULID",
  "trace_id": "trc_...",
  "request_id": "req_...",
  "session_id": "sess_...",
  "user_id": "u_123",
  "event_ts": "2026-02-09T10:00:00Z",
  "ingest_ts": "2026-02-09T10:00:00.150Z",
  "surface": "home",
  "locale": "ko-KR",
  "device": "ios",
  "impression_id": "01J...ULID",
  "policy_version": "policy_v1",
  "candidate_set_id": "cand_01J...ULID",
  "budgets": {
    "recall_caps": {"graph_cf":200, "embedding_ann":200, "trend":200, "rules":200},
    "merge_cap": 800,
    "rerank_caps": {"light":200, "heavy":20}
  },
  "candidates": [
    {"wine_core_id":"core_1","wine_sku_id":"sku_1","candidate_source":"embedding_ann","recall_score":0.82,"recall_rank":3}
  ],
  "rank_outputs": [
    {"wine_sku_id":"sku_1","light_score":0.12,"heavy_score":0.41,"final_rank":1}
  ],
  "postrank": {
    "diversity_applied":["region_min_2"],
    "constraint_filters_applied":["in_stock_only"],
    "explanation_keys":["peak_window","critic_affinity"]
  }
}

내 의견(정책 로그에서 절대 빼면 안 되는 것)
- 후보 리스트(candidates)는 “대충 topK만” 남기면 학습 재현성이 깨진다. 최소한 merge_cap 이후의 후보집합은 남겨야 한다.
- budgets는 운영 상한의 SSOT다. A/B로 바꿔도 로그에 남겨야 나중에 평가가 가능하다.

Counterfactual 평가를 하려면(IPS/SNIPS/DR):
- candidates에 propensity(또는 propensity 추정 가능 정보)가 필수다.
- exploration_policy(탐험 정책/파라미터/seed)가 없으면 propensity가 재현 불가능해진다.

**propensity 필드 강제 규칙 (SOTA 보장)**

- propensity 필드는 스키마상 nullable이지만, **운영 관점에서 "사실상 필수"로 취급한다.**
- quality_gate_report_v1에서 propensity 누락률을 모니터링한다.
  - 경보 임계치: propensity 누락률 > 5%
  - 차단 임계치: propensity 누락률 > 20% (이 경우 해당 기간 데이터로 counterfactual 평가 불가 판정)
- propensity_model 필드에는 추정 방식("logged"|"estimated") + 버전 태그를 반드시 기록한다.
- 이 규칙은 RFC-DATASET-BENCH-005 §5-4의 "오프라인 반사실 평가 없이 SOTA 주장 불가" 원칙의 데이터 전제 조건이다.

4. ActionEvent / action_log_v1

4-1. Schema (필드)

- impression_id: string
- wine_core_id: string
- wine_sku_id: string
- action_type: enum VIEW|CLICK|DWELL|LIKE|WISHLIST|CART
- action_ts: timestamp
- dwell_ms: int32 nullable

4-2. Example JSON (요지)

{
  "schema_version": "v1",
  "event_id": "01J...ULID",
  "trace_id": "trc_...",
  "request_id": "req_...",
  "session_id": "sess_...",
  "user_id": "u_123",
  "event_ts": "2026-02-09T10:00:05Z",
  "ingest_ts": "2026-02-09T10:00:05.010Z",
  "surface": "home",
  "locale": "ko-KR",
  "device": "ios",
  "impression_id": "01J...ULID",
  "wine_core_id": "core_1",
  "wine_sku_id": "sku_1",
  "action_type": "CLICK",
  "action_ts": "2026-02-09T10:00:05Z",
  "dwell_ms": null
}

5. OrderEvent / order_log_v1

5-1. Schema (필드)

- order_id: string (ULID)
- impression_id: string nullable  // 가능하면 연결(마지막 추천 노출을 attribution)
- wine_sku_id: string
- qty: int32
- paid_amount: float64
- currency: string (ISO 4217)
- order_ts: timestamp
- refund_ts: timestamp nullable

내 의견(현실적인 attribution)
- impression_id를 order에 100% 연결하려고 집착하면 오히려 누락/왜곡이 생긴다.
- 대신 “가능하면 연결 + 연결률 모니터링 + window attribution 규칙(예: last_impression_within_7d)”을 dataset_manifest에 고정하는 게 운영적으로 안전하다.

6. Dedup / Ordering 규칙 (Collector + Stream)

- dedup key: (event_id) 우선, 없으면 (user_id, event_ts, impression_id, action_type, wine_sku_id) 조합
- out-of-order window: 2~5분(초기 권장)
- late event 정책: window 밖 이벤트는 별도 late stream으로 분기하여 지표만 반영(학습 SSOT 반영 여부는 dataset_manifest로 고정)

