RFC-E2E-PIPELINE-006

Title: High-End Wine Recommendation — E2E Data Pipeline “확정 구현 스펙” v1 (SOTA Standard Flow)
Status: Draft v1.0
Scope: Raw→SSOT→Gold Assets→Dataset Builder→Multi-Recall→Rank/Re-rank→Post-rank→Serving/Logging/Eval 전체 파이프라인을 재현/확장/성능보장 관점에서 “고정 스펙”으로 정의
Depends On: RFC-SSOT-IR-001(Wine/Review SSOT&IR v1), RFC-REC-EXT-004(High-End Extensions), RFC-DATASET-BENCH-005(Dataset & Benchmark)

0. 목표 (What we freeze)

0-1. 추천 품질의 SSOT를 “모델”이 아니라 “데이터/IR/로그 설계”에 둔다

0-2. 아래를 “비가역적으로” 고정한다

(A) 노출(impression) 기반 학습데이터 재현
(B) 시간축 누설 차단(time-travel join + published_at/as_of_ts 규율)
(C) wine_core vs wine_sku SSOT 분리
(D) 멀티-리콜 + 정밀 랭킹 + 제약/다양성 + 설명 + 온라인 루프(서빙/로깅/평가)까지 포함한 실서비스 표준 흐름

1. Non-Negotiable (비가역 원칙)

1-1. 파생 자산(Lineage) 3단 키 의무화

모든 파생 자산(feature/embedding/index/graph)은 아래 3단 키를 반드시 가진다.

- input_unit_id (어느 canonical unit에서 왔나)
- transform_version (정제/청킹/정규화 버전)
- recipe_or_encoder_version (피처 레시피/임베딩 인코더 버전)

1-2. 학습 데이터의 SSOT는 impression 단위다

학습 예제는 반드시 (impression_id)에서 출발하며, “노출된 후보 집합”을 정답/오답 정의의 기준으로 삼는다.

1-3. time-travel join 규칙은 manifest로 고정한다

- join rule: as_of_ts <= event_ts
- 텍스트/리뷰: published_at <= action_ts(또는 event_ts)
- 가격/시세/경매: as_of_ts + window 정의 필수(last_30d 등)

1-5. 버전 변경 → dataset_version 전파 규칙 (Non-Negotiable)

아래 항목 중 하나라도 변경되면 dataset_version을 반드시 bump한다:

- transform_version (정제/청킹/정규화 버전)
- recipe_or_encoder_version (피처 레시피/임베딩 인코더 버전)
- feature_set_version
- negative_sampling_spec (seed 포함)
- candidate_budget_spec_version
- join_rules (as_of_ts/published_at)
- attribution_spec
- split 기간

"같은 dataset_version인데 내용이 다른" 상황은 구조적으로 차단한다.
이 규칙은 lineage 3단 키(1-1)가 dataset_manifest까지 전파되는 마지막 고리이다.
(정본: RFC-DATASET-BENCH-005 §7-1, RFC-DATASET-BUILDER-011 §8-1)

1-4. Serving 표준은 “Multi-Recall + 2-Stage Re-rank + Post-rank”다

latency 상한(p95)을 구조적으로 통제하기 위해 서빙 파이프라인 형태를 고정한다.

2. Phase A — Data Ingestion (Bronze / Raw)

2-1. 소스 분리

- 1st-party(서비스 SSOT): 행동/노출/정책 로그, 주문/반품, 가격/재고 스냅샷
- 3rd-party(부트스트랩/확장): tech-sheet, critic/review, public dataset, 경매/시세, 서치 트렌드 등

2-2. Raw 수집 원칙 (원문 + provenance)

- 원문 보존 + provenance 메타 필수
- 최소 메타: source_system, fetched_at, license_tag, checksum, raw_ref(file/url), content_type, content_length

2-3. Raw 이벤트/로그 스키마 (정본)

Raw(노출/정책/행동/주문) 이벤트의 **필드/타입/예시 JSON**은 아래를 정본으로 한다.

- RFC-LOG-SCHEMA-009: 실시간(append-only) 이벤트/SSOT 로그 계약

오프라인 저장(Parquet/Iceberg/Delta) 테이블 계약(파티션/키/조인)은 아래를 따른다.

- RFC-IR-SCHEMA-007: Bronze/Silver/Gold 저장 스키마 계약

3. Phase B — Canonicalization & MDM (Silver / SSOT)

3-1. 핵심 엔티티 SSOT

- wine_core: 취향 누적의 안정 ID
- wine_sku: 판매 단위(빈티지/용량/국가/수입사) + 재고/가격 변동
- producer, region(계층), grape_variety
- critic/outlet, merchant(셀러/경매소)

3-2. Entity Resolution (정규화/매핑) 산출물

- alias 해소: “Chateau Margaux” == “Ch. Margaux”
- source별 외부 ID → 내부 키 매핑(신뢰도 포함)

결과물(예)
- dim_wine_core_v1, dim_wine_sku_v1
- map_external_id_to_core_v1, map_external_id_to_sku_v1
- dim_critic_outlet_v1 + credibility_score(가중치의 SSOT; 값 자체는 버전드 스냅샷)

3-3. 시간 메타 고정(누설 방지의 핵심)

- critic/review: published_at 필수(없으면 fetched_at로 대체하되, 결측률 모니터링)
- tech-sheet: vintage_year + published_at(or release_at) 필수
- market/auction: as_of_ts + window 정의 필수(last_30d, last_7d 등)

4. Phase C — Gold Assets Build (SOTA: Gold를 “하나”로 보지 않는다)

Gold는 아래 3개 자산으로 “분리 고정”한다.

(A) Gold-A Canonical IR: 임베딩/피처의 입력 SSOT (모델-불가지론)
(B) Gold-B Feature Store: 파생 피처(모델-불가지론 또는 약한 의존)
(C) Gold-C Embedding Store / Vector Index: 임베딩/인덱스(모델-의존)

4-1. Gold-A/B/C 스키마(저장 계약) 정본

Gold-A/B/C의 **테이블/필드/타입/키/파티션**은 아래를 정본으로 한다(중복 정의 금지).

- RFC-IR-SCHEMA-007: `canonical_*_unit_v1`, `features_*_v1`, `embeddings_v1`, `vector_index_manifest_v1`

5. Phase D — Training Dataset Builder (핵심 SSOT 컴포넌트)

5-1. 입력 SSOT

- impression_log + policy_log + action_log (노출 단위)
- order_log (고의도 라벨)
- features_offline_v1 (event_ts 기준 time-travel)

5-2. 예제 생성 규칙(고정)

단위: (impression_id, user_id, context, candidate_item)

positive 정의(예시; 우선순위)
- purchase > cart > click > dwell_long

negative 정의(최우선)
- shown_but_no_action (노출됐는데 미반응)

샘플링(권장)
- in-session negatives + shown negatives 우선

누설 차단(필수)
- feature join: as_of_ts <= action_ts (또는 event_ts)
- critic/review join: published_at <= action_ts (또는 event_ts)

5-3. Dataset Builder 정본

학습데이터 생성 규칙(라벨/네거티브/윈도우/스플릿/조인/누설 차단)은 아래를 정본으로 한다.

- RFC-DATASET-BUILDER-011__Impression-Centric-Dataset-Builder-v1.md

산출 테이블 계약(스키마)은 아래를 정본으로 한다.

- RFC-IR-SCHEMA-007: `training_examples_v1`, `splits_v1`, `dataset_manifest_v1`

6. Phase E — Candidate Generation (Recall / Multi-Recall)

6-1. 멀티 채널 후보 생성(표준)

- Recall-1: CF/Graph 기반 (LightGCN류) topN
- Recall-2: Text/LLM embedding 기반 topN
- Recall-3: Popular/Trend(세그먼트별) topN
- Recall-4: Constraint-aware recall(가격대/재고/배송 가능) topN

6-2. 비용 상한(필수: latency/비용 보장)

- channel_topk 하드 캡 (예: 각 채널 200)
- channel_latency_budget_ms + fallback 정책
- merge 이후 total_candidate_cap (예: 800)

6-3. 후보 병합 규칙

- merge + dedup (wine_core 기준 우선, sku는 옵션)
- candidate feature로 고정:
  - candidate_source, channel_id
  - recall_score, recall_rank

7. Phase F — Ranking / Re-ranking (정밀 점수화)

7-1. 입력

- 후보 200~1000개
- user/context + item features + candidate features

7-2. 모델 형태(실무 표준)

- DeepFM/DLRM/Wide&Deep 계열(정형 sparse feature 강점)
- 목적함수 multi-task 권장:
  - p_purchase, p_cart, p_click 동시 학습
- 최종 score는 비즈니스 목적에 맞게 조합(정책/시장별 상수는 config로)

7-3. 2-Stage Re-rank로 비용 상한 고정(권장)

- light ranker(cheap): 800 → 200
- heavy ranker(full): 200 → 20
- post-rank(rule/diversity): 20 → 5

7-4. 하이엔드 특화 로직(learned + rules)

- critic_affinity 가중치 상향(유저가 신뢰하는 평론가)
- maturity window boost(지금 마시기 적기; as_of_ts 기반)
- price elasticity(예산 대비 과도한 이탈 방지)
- scarcity/auction momentum(희소성 과열 방지/강조 정책 선택)

8. Phase G — Post-ranking (제약/다양성/설명)

8-1. Hard Constraints

- 재고/배송/법규/예산/구매 가능성 필터(하드 필터는 반드시 ranking 이후/이전에 어디서 적용되는지 policy_log에 기록)

8-2. Diversity / Serendipity

- producer/region/vintage/style 다양성 최소 조건
- 유사도 과집중 방지(MMR류 or rule-based)

8-3. Explanation Payload (하이엔드 전환 핵심)

- critic quote(요약), taste tags, maturity status
- price trend, scarcity rationale, provenance/condition 요약(가능 시)

9. Phase H — Serving / Logging / Evaluation (Online Loop)

9-1. Online Serving (표준 경로)

request → recall → (light rank) → (heavy rank) → post-rank → response(TopK + explanation)

- online feature store 조회 + 캐시(스냅샷은 as_of_ts로 관리)

9-2. Logging (SSOT 재유입; 누락 허용 불가)

impression_log_v1 (노출)
- impression_id, model_version, item_ids, positions, shown_ts, surface

action_log_v1 (행동)
- impression_id, item_id, action_type, action_ts, dwell_ms, session_id

policy_log_v1 (정책)
- impression_id, model_version
- candidate_set(채널별 후보/점수/랭크)
- rerank_scores, constraints_applied, diversification_applied

9-3. Evaluation

Offline
- time-split NDCG/Recall@K
- high-end segment(고가/희소) 별도 리포트
- T1~T4 하이엔드 태스크 리포트(SSOT)

Counterfactual (Off-policy)
- IPS / SNIPS / DR 기반 오프라인 정책 평가를 1급 시민으로 포함
- 전제: policy_log에 propensity(또는 추정 가능 최소 필드셋)가 남아야 함
- 목적: “A/B 결과만 진실” 구조에서 탈피하고, 정책 비교를 실험 체계로 고정

Online
- A/B
- 탐색(신규/희소 노출 bandit 정책; 정책은 policy_log에 버전으로 기록)

Long-horizon (승자 판정 기준)
- 7일/30일 재구매율, cellar-building 패턴, 반품/취소율 등 장기 지표를 온라인/오프라인 리포트에 포함
- **Long-horizon 지표 개선 없이 short-term CTR만 개선된 모델은 "승자 아님"으로 판정한다** (정본: RFC-DATASET-BENCH-005 §5-5)
- 배포 승인 조건: 7일/30일 재구매율이 기존 대비 하락하지 않아야 함

10. 계약(Contract) 스펙: Manifest / Parity CI / Quality Gates

10-1. feature_manifest_v1 (계약 SSOT)

feature 정의/조인/누설 규칙/기본값/레시피 버전 및 online/offline parity gate는 아래를 정본으로 한다.

- RFC-FEATURE-MANIFEST-010__Feature-Manifest-and-Parity-Gate-v1.md

10-2. Online/Offline Parity CI (필수 게이트)

Parity CI의 구체 규칙(샘플링/비교/eps/tier)은 RFC-FEATURE-MANIFEST-010을 따른다.

10-3. Quality Gates (성능보장의 전제; 자동 집행)

누설 체크
- published_at/as_of_ts <= event_ts 위반률 0

중복 체크
- 동일 텍스트/리뷰 중복률 경보(content_hash 기반)

ER drift
- alias 매핑 변경량(일/주 단위) 경보

이상치/결측
- price 급변, abv 범위 위반, 필수키 결측률 경보

로그 무결성
- impression_id 조인 성공률(노출→행동) 99%+ 목표
- policy_log model_version/candidate_set 누락률 ~0

임베딩 회귀 방지(encoder rollout 게이트)
- embedding norm 분포 변화
- nearest neighbor stability(샘플)
- retrieval recall@K 변화

11. 증분(Incremental) 빌드: 변경 전파 이벤트(확장성 핵심)

전체 재처리를 금지하고, SSOT 변경을 이벤트로 발행해 파생 자산을 증분 갱신한다.

예시 이벤트 타입(v1)
- WineCoreUpdated(wine_core_id, changed_fields, as_of_ts)
- TextUnitAdded(text_unit_id), TextUnitUpdated(text_unit_id)
- StructUnitAdded(struct_unit_id)
- PriceSnapshotAdded(wine_sku_id, as_of_ts, window)
- EmbeddingEncoderRolled(encoder_version, effective_ts)

소비 규칙
- 임베딩: 영향받은 input_unit만 재인코딩 + index upsert
- 피처: 영향받은 entity만 recipe 재계산 + online snapshot 갱신
- 그래프: 영향받은 edge만 증분 반영

12. 비용 상한 정책(SSOT): candidate_budget_spec_v1

candidate_budget_spec_v1의 저장 스키마는 RFC-IR-SCHEMA-007을 정본으로 한다.

candidate_budget_spec_v1이 dataset_manifest에 포함되는 방식/정합 규칙은 RFC-DATASET-BUILDER-011을 정본으로 한다.

13. 한 줄 요약(확정 흐름)

Bronze(raw 수집: 노출/행동/정책 + 외부 원문)
→ Silver(SSOT: wine_core/sku, alias/매핑, published_at/as_of_ts 고정)
→ Gold-A/B/C(Canonical IR + Feature Store + Embedding Store/Index)
→ Dataset Builder(노출 기반 학습데이터 재현 + 누설 차단 규칙)
→ Multi-Recall(그래프+임베딩+트렌드+제약; 비용 상한)
→ 2-Stage Re-rank(정형 sparse + multi-task; 비용 상한)
→ Post-rank(제약 + 다양성 + 설명)
→ Serving & Logging(정책/노출 로그로 닫힌 루프)
