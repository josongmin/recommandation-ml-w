RFC-IR-SCHEMA-007

Title: High-End Wine Recommendation — IR Schema v1 (Tables/Types/Keys/Parquet Contracts)
Status: Draft v1.0
Scope: RFC/006(E2E Pipeline Spec)의 “Gold-A/B/C + Dataset Builder + Logging + Manifest/Quality Gate”를 실제 저장 스키마로 확정한다.
Depends On:
- RFC-SSOT-IR-001: Wine/Review Master & IR v1 (기본 SSOT)
- RFC-REC-EXT-004: High-End Extensions (temporal/scarcity/authority/condition/market)
- RFC-DATASET-BENCH-005: Dataset & Benchmark (벤치/태스크/권리)
- RFC-E2E-PIPELINE-006: E2E Pipeline Implementation Spec (파이프라인 고정 흐름)

Conventions (공통 규칙)
- ID: ULID 권장(string). 외부 키는 source_system+source_item_key 조합으로 추적.
- Timestamp: UTC 기준 `timestamp`(millis).
- 파티션(Parquet/Iceberg/Delta 가정):
  - 이벤트 로그: `event_date=DATE(ts)` 또는 `shown_date`
  - 스냅샷: `as_of_date=DATE(as_of_ts)`
  - 임베딩: `encoder_version`, `as_of_date`
- Append-only 우선. “사실/스냅샷”은 SCD2 또는 append-only event로 유지(덮어쓰기 금지).
- Lineage 3단 키 의무:
  - `input_unit_id`
  - `transform_version`
  - `recipe_or_encoder_version`
- time-travel join 계약:
  - `as_of_ts <= event_ts`
  - `published_at <= event_ts` (리뷰/텍스트)

1. Bronze (Raw) — 원문/원 이벤트 SSOT (append-only)

Bronze의 정본 스키마(필드/타입/예시 JSON)는 **RFC-LOG-SCHEMA-009**를 따른다.
본 RFC에서는 “저장 계약(파티션/조인키/append-only)”만 고정하며, 이벤트 필드 정의를 중복하지 않는다.

1-1. SSOT 이벤트(정본: RFC-LOG-SCHEMA-009)
- impression_log_v1
- policy_log_v1
- action_log_v1
- order_log_v1

1-2. 저장 규칙(권장)
- append-only
- 파티션(Parquet/Iceberg/Delta 가정)
  - impression_log_v1: shown_date=DATE(shown_ts)
  - policy_log_v1: event_date=DATE(event_ts) 또는 policy_date=DATE(event_ts)
  - action_log_v1: event_date=DATE(event_ts)
  - order_log_v1: event_date=DATE(event_ts)

2. Silver (SSOT Facts) — 조인 가능한 “정규화 사실” 계층

NOTE: 엔티티 SSOT(dim_wine_core_v1, dim_wine_sku_v1, review_master_v1 등)은 RFC-SSOT-IR-001을 정본으로 한다.
여기서는 “노출/행동/정책/주문”을 모델 학습에 쓰기 위한 canonical fact 테이블만 확정한다.

2-1. fact_impression_v1
- impression_id: string (pk)
- user_id: string
- surface: string
- shown_ts: timestamp
- shown_date: date
- candidate_item_ids: array<string>  // canonical: wine_core_id 권장(서비스 설계에 따라 sku도 병행 가능)
- candidate_item_kind: string  // "core"|"sku"
- positions: array<int32>
- request_context: struct<
    locale: string nullable,
    device: string nullable,
    market: string nullable,
    budget_hint: float64 nullable
  >
- raw_ref: string  // raw 파일/레코드 포인터
- ingested_at: timestamp

Partition: shown_date

2-2. fact_policy_v1
- impression_id: string (pk, fk->fact_impression_v1)
- policy_ts: timestamp
- model_version: string
- stage_versions: struct<
    recall: string nullable,
    light_rank: string nullable,
    heavy_rank: string nullable,
    post_rank: string nullable
  >
- candidate_set: array<struct<
    channel_id: string,
    candidate_source: string,
    item_id: string,
    item_kind: string,        // "core"|"sku"
    recall_score: float32 nullable,
    recall_rank: int32 nullable
  >>
- rerank_scores: array<struct<
    item_id: string,
    score: float32
  >> nullable
- constraints_applied: array<string>
- diversification_applied: array<string>
- raw_ref: string
- ingested_at: timestamp

Partition: policy_date=DATE(policy_ts)

2-3. fact_action_v1
- action_id: string (pk)
- impression_id: string (fk)
- user_id: string
- item_id: string
- item_kind: string  // "core"|"sku"
- action_type: string
- action_ts: timestamp
- dwell_ms: int32 nullable
- session_id: string nullable
- raw_ref: string
- ingested_at: timestamp

Partition: action_date=DATE(action_ts)

2-4. fact_order_v1
- order_id: string (pk)
- user_id: string
- wine_sku_id: string  // canonical sku 필수(매핑 실패시 별도 dead-letter)
- qty: int32
- paid_amount: float64
- currency: string
- order_ts: timestamp
- refund_ts: timestamp nullable
- raw_ref: string
- ingested_at: timestamp

Partition: order_date=DATE(order_ts)

3. Gold-A (Canonical IR) — 임베딩/피처 “입력” SSOT

3-1. canonical_text_unit_v1
- text_unit_id: string (pk)
- wine_core_id: string
- source_type: string  // critic_review|community_review|product_desc|techsheet_extracted
- lang: string         // BCP-47
- published_at: timestamp nullable
- fetched_at: timestamp
- canonical_text: string
- transform_version: string  // cleaning+chunking 정책 버전
- content_hash: string       // dedup
- rights_store_raw: bool nullable
- rights_display: bool nullable
- license_tag: string nullable
- raw_ref: string
- created_at: timestamp

Partition: source_type, lang

3-2. canonical_struct_unit_v1
- struct_unit_id: string (pk)
- wine_core_id: string nullable
- wine_sku_id: string nullable
- as_of_ts: timestamp
- fields: map<string, string>  // 정규화된 값(문자열) + 단위 포함은 금지(단위는 transform_version에서 고정)
- transform_version: string
- content_hash: string
- license_tag: string nullable
- raw_ref: string
- created_at: timestamp

Partition: as_of_date

3-3. canonical_image_unit_v1 (Phase 2+)
- image_unit_id: string (pk)
- wine_sku_id: string
- as_of_ts: timestamp
- image_ref: string
- transform_version: string  // resize/crop 정책
- content_hash: string
- license_tag: string nullable
- raw_ref: string
- created_at: timestamp

Partition: as_of_date

4. Gold-B (Feature Store) — Derived Features SSOT

NOTE: “feature는 계약(Manifest)으로 정의되고, offline/online parity를 CI로 강제”한다.

4-1. features_offline_v1
- entity_type: string  // user|wine_core|wine_sku|user_item|context
- entity_id: string
- event_ts: timestamp      // 라벨/행동 시점
- as_of_ts: timestamp      // 피처 유효 시점(반드시 event_ts 이전)
- feature_set_version: string  // feature_manifest_v1.version
- dense_f: map<string, float64> nullable
- sparse_f: map<string, string> nullable
- int_f: map<string, int64> nullable
- lineage_input_refs: array<string>  // input_unit_id list
- recipe_versions: map<string, string>  // feature_group -> recipe_version
- created_at: timestamp

Primary Key (logical): (entity_type, entity_id, event_ts, feature_set_version)
Partition: event_date=DATE(event_ts)

4-2. features_online_v1
- entity_type: string
- entity_id: string
- as_of_ts: timestamp
- feature_set_version: string
- dense_f: map<string, float64> nullable
- sparse_f: map<string, string> nullable
- int_f: map<string, int64> nullable
- created_at: timestamp

Primary Key (logical): (entity_type, entity_id, as_of_ts, feature_set_version)
Partition: as_of_date

5. Gold-C (Embedding Store / Vector Index) — 모델 의존 SSOT

5-1. embeddings_v1
- embedding_id: string (pk)
- input_unit_type: string  // text_unit|image_unit
- input_unit_id: string
- encoder_version: string
- transform_version: string  // input unit transform_version을 그대로 복제(lineage 3단키의 일부)
- as_of_ts: timestamp
- dim: int32
- vector_ref: string        // blob/vecdb pointer
- content_hash: string      // 입력 hash (재현성)
- created_at: timestamp

Partition: encoder_version, as_of_date

5-2. vector_index_manifest_v1
- index_id: string (pk)
- encoder_version: string
- index_type: string  // hnsw|ivf_pq...
- params_json: string
- build_ts: timestamp
- source_embedding_filter: string  // 예: "latest_as_of_ts_per_unit"
- created_at: timestamp

6. Dataset Builder Outputs — 학습데이터 재현 SSOT

6-1. training_examples_v1 (Parquet)
- example_id: string (pk)  // ULID
- impression_id: string
- user_id: string
- item_id: string
- item_kind: string  // core|sku
- surface: string
- shown_ts: timestamp
- position: int32
- label: int8        // 0/1
- label_type: string // purchase|cart|click|dwell_long|none
- action_ts: timestamp nullable
- candidate_features: struct<
    channel_id: string nullable,
    candidate_source: string nullable,
    recall_score: float32 nullable,
    recall_rank: int32 nullable
  >
- feature_set_version: string
- user_feature_ref: string nullable   // (entity_type,user_id,event_ts,feature_set_version)로 조회 가능한 ref
- item_feature_ref: string nullable
- context_feature_ref: string nullable
- embedding_versions: array<string> nullable  // 사용한 encoder_version 목록
- join_proof: struct<
    as_of_ts: timestamp,               // 실제 join 기준
    published_at_max: timestamp nullable
  >
- created_at: timestamp

Partition: shown_date=DATE(shown_ts)

6-2. splits_v1
- split_id: string (pk)
- split_strategy: string  // time_split_v1
- train_start: date
- train_end: date
- val_start: date
- val_end: date
- test_start: date
- test_end: date
- seed: int32
- created_at: timestamp

6-3. dataset_manifest_v1 (SSOT)
- dataset_id: string (pk)
- dataset_version: string
- split_id: string (fk->splits_v1)
- feature_set_version: string
- embedding_versions: array<string>
- join_rules_json: string  // as_of_ts/published_at rules
- negative_sampling_spec_json: string
- candidate_budget_spec_version: string
- created_at: timestamp

7. Contracts (SSOT) — Manifest / Budget / Quality Gate

7-1. feature_manifest_v1
- feature_set_version: string (pk)
- manifest_json: string  // 정의(엔티티, 소스, 조인키, time-travel, recipe_version, null policy)
- created_at: timestamp

7-2. candidate_budget_spec_v1
- candidate_budget_spec_version: string (pk)
- per_channel_topk: map<string, int32>
- total_candidate_cap: int32
- latency_budget_ms: map<string, int32>  // stage->ms
- fallback_order: array<string>
- created_at: timestamp

7-3. quality_gate_report_v1 (운영 리포트; append-only)
- report_id: string (pk)
- report_ts: timestamp
- window: string  // last_24h 등
- metrics: map<string, float64>
- violations: array<struct<
    gate_name: string,
    rate: float64,
    sample_refs: array<string>
  >>
- created_at: timestamp

8. Incremental Build Events (변경 전파) — 증분 재처리 SSOT

8-1. pipeline_change_event_v1
- event_id: string (pk)
- event_type: string  // WineCoreUpdated|TextUnitAdded|TextUnitUpdated|StructUnitAdded|PriceSnapshotAdded|EmbeddingEncoderRolled...
- entity_id: string
- entity_type: string
- as_of_ts: timestamp
- changed_fields: array<string> nullable
- payload_json: string nullable
- created_at: timestamp

Partition: event_date=DATE(as_of_ts)

9. Cross-Doc Mapping Notes (용어 정합)

- RFC-SSOT-IR-001의 “IR”는 추천/검색 표현층 전반을 의미한다.
- 본 문서(RFC-IR-SCHEMA-007)의 “Gold-A Canonical IR”는 **임베딩/피처 생성 입력의 SSOT**로, RFC-SSOT-IR-001의 IR 철학(재생성 가능/버전드)과 동일하되, 실무적으로 “임베딩 이전 데이터의 자리”를 명시하기 위해 분리 표기한다.
