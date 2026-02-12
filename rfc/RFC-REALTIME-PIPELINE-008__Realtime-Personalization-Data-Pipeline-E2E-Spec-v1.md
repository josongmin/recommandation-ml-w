RFC-REALTIME-PIPELINE-008

Title: 하이엔드 와인 추천 — 실시간 개인화 데이터 파이프라인 E2E 구현 스펙 v1
Status: Draft v1.0
Scope: Client 이벤트 수집 → 스트림 처리 → Online State/Feature → Serving(Multi-Recall + 2-Stage Rerank + Post-rank) → SSOT Logging → Offline Dataset Builder/Training까지 “동일 SSOT(로그/manifest/lineage)”로 결합
Depends On (관련 RFC):
- RFC-E2E-PIPELINE-006: 오프라인/Gold 자산 중심 E2E 표준 흐름
- RFC-IR-SCHEMA-007: Gold-A/B/C + Logs + Manifest를 저장 스키마로 확정
- RFC-DATASET-BENCH-005: 벤치/평가/재현 프로토콜
Note:
- 본 RFC는 “실시간(Online) 상태/피처”를 추가하고, Offline 학습과의 결합을 impression SSOT로 고정한다.
- 기존 RFC들이 Offline 중심으로 이미 정의한 부분(예: Gold-A/B/C, Dataset Manifest, 품질게이트)은 본 RFC에서 “실시간 접점/강제 규칙”만 재명시하고 상세는 해당 RFC를 따른다.

1. RFC 개요

1-1. RFC ID / 제목

RFC-REALTIME-PIPELINE-008

하이엔드 와인 추천: 실시간 개인화 데이터 파이프라인 E2E 구현 스펙 v1

1-2. 목표

- 실시간 개인화(Online)와 오프라인 학습/IR(Offline) 파이프라인을 “동일 SSOT(로그/manifest/lineage)”로 결합
- 200~300ms급 요청 예산 내에서 개인화 후보 생성 + 2단 랭킹 + 포스트랭킹 + 로깅을 완결
- 노출(impression) 단위 학습데이터 재현, time-travel 누설 차단, online/offline feature parity 보장
- 데이터셋 구분(훈련/평가/리플레이/관측로그)을 명시적으로 고정

1-3. Non-Negotiable (비가역 원칙)

아래 원칙은 정본 RFC를 따른다(중복 정의 금지).

- RFC-E2E-PIPELINE-006 §1: impression SSOT / lineage 3단 키 / time-travel / 서빙 표준 형태
- RFC-FEATURE-MANIFEST-010__Feature-Manifest-and-Parity-Gate-v1.md: parity gate(offline/online)

본 RFC에서 추가로 “실시간” 관점에서 강제하는 것
- event_ts + ingest_ts(관측 시각) 동시 기록(지연/클럭 스큐 관측)
- 200~300ms 요청 예산 내에서 multi-recall + 2-stage rerank + post-rank 실행(예산/캡은 policy_log에 남김)

내 의견(현업 관점에서의 “왜 이게 비가역인가”)
- impression을 SSOT로 고정하면 “노출된 후보집합”이 학습/평가의 기준이 되어, 가격/희소/재고처럼 관측 편향이 강한 도메인에서 평가 프로토콜이 무너지지 않는다.
- lineage 3단 키는 “결과가 나쁘면 원인(입력/정제/레시피/인코더)을 정확히 되돌릴 수 있는가”의 최소 단위다. 이게 없으면 장애/회귀 분석이 인력빨로만 해결된다.

2. 아키텍처 한 장 요약

2-1. 전체 구성

Client SDK → Event Collector API → Stream Bus → Stream Processor → Online State Store/Online Feature Store

Recsys Serving API → (State/Feature Fetch) → Multi-Recall → Rank → Post-rank → Response

Logging(Policy/Impression/Action) → Stream/Batch 적재 → Dataset Builder → Offline Feature Store/Training

2-2. “기존 오프라인 파이프라인”과의 접점

- 기존 Gold-A/B/C( Canonical IR / Feature Store / Embedding+Index )는 유지
- 실시간은 “Online State/Feature”를 생성하고, 동일한 SSOT 로그(정책/노출/행동)가 Dataset Builder로 흘러가 Offline 학습으로 귀결됨
- 즉, Offline은 IR/모델을 만든다, Online은 상태를 만든다, SSOT는 로그와 manifest임

3. 데이터셋/테이블 구분(최종)

3-1. Online Observability Logs (SSOT, append-only)

- impression_log_v1: 노출 단위 SSOT
- policy_log_v1: 추천 정책/후보/점수/버전 SSOT
- action_log_v1: 노출 후 행동 SSOT
- order_log_v1: 결제/반품 SSOT

3-2. Online State/Feature (서빙 전용)

- user_profile_snapshot_v1: 장기 사용자 프로필/벡터(rolling window)
- user_session_snapshot_v1: 세션 프로필/벡터(단기 의도)
- features_online_v1: low-latency 서빙 피처(머티리얼라이즈)

3-3. Offline Assets (정본 참조)

오프라인 Gold-A/B/C 및 Dataset Builder 산출물의 스키마/정의는 아래를 정본으로 한다.

- RFC-IR-SCHEMA-007: Gold-A/B/C + dataset tables 저장 스키마
- RFC-DATASET-BUILDER-011__Impression-Centric-Dataset-Builder-v1.md: 학습데이터 생성 규칙(dataset_manifest SSOT)

내 의견(명시적으로 분리해야 운영이 편해지는 이유)
- Online State/Feature는 “서빙 최신값”이고, Offline Feature는 “time-travel 가능한 과거 재현”이다. 둘을 한 테이블에 섞으면 누설/재현성 둘 다 깨지기 쉽다.

4. 실시간 이벤트 수집 설계(클라이언트 → 버스)

4-1. 이벤트 타입(필수)

- ImpressionEvent
- ActionEvent (view/click/dwell/like/wishlist/cart)
- OrderEvent (purchase/refund)

4-2. 공통 필드(필수)

- trace_id, request_id, session_id, user_id
- event_ts(UTC), surface(home/search/list/pdp), locale, device
- item_id는 wine_sku_id + wine_core_id를 모두 포함

내 의견(필수 필드 보강 추천)
- event_id(ULID) 추가 권장: dedup/재전송/중복 탐지의 기준 키가 생긴다.
- client_sent_ts + server_ingest_ts를 함께 기록 권장: 지연/드리프트/클럭 스큐를 관측할 수 있다.

4-3. 이벤트/정책 로그 스키마(정본)

Impression/Policy/Action/Order 이벤트의 필드/타입/예시 JSON은 아래를 정본으로 한다.

- RFC-LOG-SCHEMA-009__Event-and-SSOT-Log-Schema-v1.md
- action_type: VIEW|CLICK|DWELL|LIKE|WISHLIST|CART
- action_ts
- dwell_ms(optional)

5. 실시간 처리 파이프라인(구체 과정)

5-1. 구성요소(구현 단위)

- Event Collector(API): 이벤트 수신, 스키마 검증, 큐/버스로 전달
- Stream Bus: Kafka/Kinesis/PubSub 중 1
- Stream Processor: Flink(권장) 또는 Spark Structured Streaming
- Online Store:
  - Redis/KeyDB: 초저지연 state/feature 캐시
  - Durable Store(선택): DynamoDB/Bigtable 등(재시작 복원, 고가용성)

5-2. 토픽/스트림(권장 네이밍)

- events.impression.v1
- events.action.v1
- events.order.v1
- recsys.policy_log.v1
- state.user_profile_updates.v1
- state.user_session_updates.v1

5-3. 스트림 처리 단계(Chronological, 확정)

Ingest
- Collector가 이벤트를 수신, 필수 필드/스키마 검증
- 사용자/세션/아이템 키 정합성 확인(wine_sku_id, wine_core_id 둘 다 있는지)

Enrich
- 최소 메타 보강(geo coarse, time bucket, surface normalization)
- 금지: 외부 API 호출로 지연 유발(날씨 등은 별도 batch/캐시로 합성)

Dedup/Ordering
- client 재전송 대비: (event_id, user_id, event_ts) 기반 dedup
- event_ts 기반 out-of-order 허용 창(window) 정의(예: 2~5분)

State Update (핵심)
- user_session_snapshot 업데이트
  - recent_items deque, session_intent, session_vector(u_session)
- user_profile_snapshot 업데이트
  - rolling aggregates(최근 N일), long_vector(u_long), price_pref, critic_affinity

Materialize Online Features
- features_online_v1에 필요한 피처만 생성/업데이트
- TTL/refresh 정책 적용

Persist SSOT Logs
- impression/policy/action/order 로그는 append-only로 저장(데이터레이크/웨어하우스)
- 이 로그가 Offline Dataset Builder의 유일한 입력 SSOT가 됨

내 의견(운영 안정성을 위한 금지/권장)
- 금지: 스트림에서 외부 동기 호출(HTTP)로 피처를 끌어오는 패턴. “가끔 느림”이 p95를 박살낸다.
- 권장: 스트림은 상태 업데이트만, 고비용 피처는 batch/증분 빌드로 생성 후 online cache로 배포.

6. 실시간 개인화 상태 모델(구현 규격)

6-1. 사용자 상태 2층(필수)

Long-term(Profile)
- u_long: 벡터(embedding space 선택)
- price_elasticity, preferred_price_band
- region_pref, grape_pref, style_pref
- critic_affinity(critic_id → weight)

Short-term(Session)
- u_session: 벡터
- recent_items(wine_core_id list)
- inferred_intent(tags), current_budget_hint, novelty_tolerance

6-2. 온라인 벡터 업데이트 방식(권장 v1)

Heuristic online update(안정, 저비용)
- u_session = normalize( Σ w(action_type, recency) * v_item )
- u_long은 실시간 델타로 부분 업데이트 가능하되, 기본은 배치 재계산(일 1회) + 고의도 이벤트 시 보정

결합 벡터
- u = normalize( α*u_long + (1-α)*u_session )
- α는 세션 길이/고의도 이벤트에 따라 동적으로 조정

6-3. v_item(아이템 벡터) 소스

- wine_core 임베딩을 기본으로 사용(취향 안정성)
- wine_sku는 제약/가격/재고의 랭킹 피처로 다루고, 벡터는 보조(선택)

내 의견(하이엔드 도메인에서의 벡터 설계 주의점)
- “희소/고가”는 유저 취향이라기보다 시장/재고/노출 편향의 산물일 수 있으니, u 벡터에 price/rarity를 직접 섞기보다는 랭킹 피처로 분리하는 편이 안전하다(회귀 시 원인 분리가 쉬움).

7. 실시간 서빙 파이프라인(후보 → 랭킹 → 포스트랭킹)

7-1. Serving API 입력/출력

입력
- user_id, session_id, surface, locale, request_ts, optional context(query/filters)

출력
- topK items(wine_sku_id 중심) + explanation payload + impression_id

7-2. Serving 단계(Chronological, 확정)

Fetch State/Features
- user_profile_snapshot, user_session_snapshot, features_online(user, context) 조회

Hard Constraints Filter(먼저)
- 재고/배송/법규/가격 상한/품절 제외
- 결과를 “candidate eligibility set”으로 생성

Multi-Recall(채널별 cap 고정)
- recall_graph_cf(u): topK1
- recall_embedding(u): topK2 (ANN/HNSW)
- recall_trend(segment): topK3
- recall_constraint_rules: topK4
- merge + dedup + merge_cap(예: 800) 적용
- candidate_source/recall_score/recall_rank를 후보에 부착

Light Ranker(cheap)
- 800 → 200
- 구현: 간단 모델(선형/GBDT) 또는 룰 기반(초기)

Heavy Ranker(full)
- 200 → 20
- 구현: DLRM/DeepFM/Wide&Deep 계열(정형+카테고리 임베딩)
- 목적: 다중 라벨(p_purchase, p_cart, p_click) 또는 단일 목적(서비스 단계에 맞게)

Post-rank
- 제약 확정(재고/가격/배송)
- 다양성 규칙(producer/region/vintage/style)
- explanation 생성(근거 키 조합)

Log Write-back
- impression_log 기록(반드시)
- policy_log 기록(반드시, 후보/점수/버전 포함)
- 이후 action이 오면 action_log로 연결

내 의견(200~300ms 예산에서의 현실적인 타협안)
- heavy rank는 “항상 호출”이 아니라, surface/사용자 상태/후보 품질에 따라 degrade 가능하게 설계해두는 게 안전하다(예: cold-start는 light-only + 더 강한 post-rank).

8. Offline 파이프라인과의 접점(학습/평가/재현)

8-1. Dataset Builder 입력 SSOT

- impression_log_v1 + policy_log_v1 + action_log_v1 + order_log_v1
- 이 4개가 학습데이터를 “재현 가능”하게 만드는 유일 근거임

8-2. 학습 레코드 생성 규칙(확정)

unit: (impression_id, user_id, item_id)

labels
- y_purchase: purchase within W_purchase
- y_cart: cart within W_cart
- y_click: click within W_click
- dwell_bucket: dwell_ms bucket

negatives
- shown_but_no_action: impression에 포함됐으나 세션 내 액션 없음

feature join
- event_ts = shown_ts (노출 기반) 또는 action_ts (행동 기반)로 목적별 분리 가능하되, 정의를 dataset_manifest에 고정
- as_of_ts/published_at <= event_ts 강제

8-3. Online/Offline parity(필수)

- feature_manifest_v1에 모든 feature 정의 고정
- offline builder와 online materializer가 동일 manifest를 구현
- CI Gate: 동일 (user_id, item_id, event_ts) 샘플에 대해 offline vs online 출력 diff = 0

내 의견(패리티 게이트를 “깨지지 않게” 만드는 팁)
- parity 대상은 “모든 피처”가 아니라, 우선 서빙 크리티컬 피처(예: 30~50개)부터 시작해 coverage를 늘리는 방식이 현실적이다.

9. 구현 방법(실무 지향, 최소 구성 → 확장)

9-1. MVP 구현 순서(권장)

- 이벤트 스키마 확정 + Collector 구현
- impression_id 기반 노출/행동/정책 로그 SSOT 적재 완성
- user_session_snapshot(세션 상태)부터 Redis에 구현
- 임베딩 기반 recall + trend recall 2채널로 시작
- light ranker(룰/선형)로 1차 운영
- dataset_builder 구축 후 offline 학습 루프 연결
- heavy ranker 도입 + post-rank 다양성/설명 강화
- bandit은 슬롯 1개에서 제한적으로 시작

9-2. Stream Processor 구현 패턴(권장)

Flink 기준
- KeyedStream by user_id/session_id
- ProcessFunction + RocksDB state로 세션 상태 유지
- Sink: Redis(online) + Data Lake(SSOT logs)

Spark Streaming 대안
- stateful mapGroupsWithState + external store(대체 가능)

9-3. Redis 키 설계(예시)

- user:profile:{user_id} → u_long + aggregates + version + updated_at
- sess:profile:{session_id} → u_session + recent_items + intent + ttl
- feat:online:user:{user_id} → features_json + feature_set_version + as_of_ts
- feat:online:item:{wine_sku_id} → availability/price band + as_of_ts

9-4. 서빙 컴포넌트 구현 패턴

Recsys API
- state fetch → recall → rank → postrank → log

Recall 서비스 분리(권장)
- vector recall: vecdb(ANN)
- graph recall: graph store/사전 계산 artifact
- trend recall: precomputed list(세그먼트별)

10. 성능/확장성 “보장 방식”(구조적)

10-1. 비용 상한(필수)

- multi-recall per-channel cap + merge_cap
- 2-stage rerank로 heavy 모델 호출 상한 고정
- constraint prefilter로 후보 공간 사전 축소

10-2. 증분 처리(필수)

- 상태는 스트림으로 증분 업데이트
- embedding/feature/index는 변경 이벤트 기반 증분 재빌드(기존 RFC의 이벤트 타입 사용)

10-3. 회귀 방지(필수)

- parity gate(online/offline)
- leakage gate(as_of_ts/published_at)
- join integrity gate(impression→policy, impression→action)

11. 산출물 목록(이 RFC로 확정되는 것)

11-1. 확정 스키마

- ImpressionEvent/ActionEvent/OrderEvent
- impression_log_v1/policy_log_v1/action_log_v1/order_log_v1
- user_profile_snapshot_v1/user_session_snapshot_v1/features_online_v1

11-2. 확정 규칙

- impression 단위 학습데이터 생성 규칙
- time-travel join 규칙
- multi-recall + 2-stage rerank + post-rank 흐름
- feature_manifest 기반 parity/CI gate

11-3. 확정 운영 예산(템플릿)

- channel_topk, merge_cap, rerank_cap(라이트/헤비), postrank_k
- TTL(session/profile/features) 정책

12. 바로 다음 단계(후속 RFC 또는 부속 문서)

12-1. RFC-LOG-SCHEMA-009

- 이벤트/로그 스키마를 필드/타입/예시 JSON까지 완전 확정

12-2. RFC-FEATURE-MANIFEST-010

- feature_manifest_v1 실제 피처 50개 수준 확정(하이엔드 특화 포함)

12-3. RFC-DATASET-BUILDER-011

- 라벨 윈도우/negative 샘플링/time-split/safeguard 규칙 확정
