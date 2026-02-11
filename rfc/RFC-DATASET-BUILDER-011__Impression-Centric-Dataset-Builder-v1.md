RFC-DATASET-BUILDER-011

Title: 하이엔드 와인 추천 — Dataset Builder v1 (impression 기반 학습데이터 재현 규칙 확정)
Status: Draft v1.0
Scope: impression/policy/action/order SSOT 로그로부터 training_examples_v1 + splits_v1 + dataset_manifest_v1을 생성하는 규칙을 고정한다.
Depends On:
- RFC-REALTIME-PIPELINE-008: impression SSOT 및 누설 차단 원칙
- RFC-LOG-SCHEMA-009: SSOT 로그 스키마
- RFC-IR-SCHEMA-007: training_examples_v1 / splits_v1 / dataset_manifest_v1 저장 스키마
- RFC-FEATURE-MANIFEST-010: feature_set_version 및 time-travel 계약

0. 목표 (What we freeze)

- 학습 레코드는 “노출(impression)로 닫힌 후보집합”을 기준으로 정의한다.
- 라벨/negative/time-split 규칙은 dataset_manifest_v1에 영구 고정되어야 한다(재현성).
- leakage(미래 정보) 위반률 0을 구조적으로 강제한다.

1. 입력 SSOT

- impression_log_v1
- policy_log_v1
- action_log_v1
- order_log_v1

2. Output

- training_examples_v1 (Parquet)
- splits_v1
- dataset_manifest_v1

3. Key 정의

3-1. Example unit

- unit key: (impression_id, user_id, item_id)
- item_id는 wine_sku_id 기준을 권장하되(구매/재고와 일치), 후보생성/학습 안정성 때문에 wine_core_id 병행을 허용한다.
- 어떤 기준을 쓸지는 dataset_manifest에 item_kind로 고정한다.

3-2. Event timestamp 정의

- base_event_ts = impression.shown_ts
- 목적에 따라 action_ts 기반 task를 만들 수 있으나, v1에서는 base_event_ts 고정(누설 방지/단순화).

내 의견(v1에서 shown_ts 고정이 안전한 이유)
- action_ts 기반은 “액션이 생긴 케이스만” 피처가 더 최신이 되어 학습 편향이 생기기 쉽다.
- shown_ts 고정은 정책/노출 당시의 정보로만 예측하도록 강제한다.

4. Label 정의(확정)

4-1. Window

- W_purchase: 기본 7d (surface별 override 가능, dataset_manifest에 고정)
- W_cart: 기본 3d
- W_click: 기본 1d
- dwell_bucket: dwell_ms를 버킷화(예: [0-3s, 3-10s, 10-30s, 30s+])

4-2. Priority

- purchase > cart > click > dwell_long > none

4-3. Attribution 규칙(권장 v1)

- order는 (user_id, wine_sku_id, order_ts)로 먼저 매칭
- impression_id 연결은 “가능하면 사용”하되, 기본은 last_impression_within_window 룰로 attribution
- attribution 룰과 성공률을 dataset_manifest에 기록

5. Negative 샘플링(확정)

5-1. 핵심 negative

- shown_but_no_action: impression.items에 포함되었으나 W_click 내에 action이 없는 아이템

5-2. Sampling policy (권장 v1)

- per impression: positives 전부 포함
- negatives:
  - shown_but_no_action 전량 또는 cap(K_neg_per_pos) 적용
  - cap은 dataset_manifest에 고정

5-3. Negative Sampling Seed 고정 (재현성 필수)

- negative sampling에 random 요소가 있는 경우(cap 적용 시 무작위 선택 등), **seed를 dataset_manifest의 negative_sampling_spec_json에 명시 고정한다.**
- seed 변경 시 dataset_version을 반드시 bump한다(RFC-DATASET-BENCH-005 §7-1 버전 전파 규칙 참조).
- 동일 seed + 동일 규칙이면 동일 결과가 나와야 한다(결정론적 재현).

내 의견(하이엔드에서 negatives를 ‘노출 기반’으로 고정해야 하는 이유)
- 고가/희소 와인은 “애초에 노출 기회”가 적다. 임의 negative를 뽑으면 모델이 기회 편향을 학습한다.
- 노출 후보집합을 negative의 우주로 고정하면 이 편향이 크게 줄어든다.

6. Feature Join (누설 차단)

6-1. time-travel 규칙(필수)

- 모든 feature join은 as_of_ts <= base_event_ts
- 리뷰/텍스트류는 published_at <= base_event_ts

6-2. join 증명(필수 — 연구 자산화)

- training_examples_v1.join_proof에 실제 as_of_ts(최대값) 및 published_at_max를 기록(감사/디버깅용)
- **join_proof를 정식 artifact로 보관한다:**
  - 빌드 완료 시 join_proof 전체를 별도 Parquet 파일(join_proof_audit_v1)로 추출·보관
  - 필드: (example_id, impression_id, as_of_ts, published_at_max, feature_set_version, join_rule_applied)
  - 이 파일은 "데이터 프로토콜 자체가 연구 자산"이 되게 하는 핵심 근거물이다
  - 보관 주기: dataset_version 단위로 영구 보관(삭제 금지)

7. Split 규칙(훈련/평가/리플레이/관측로그)

7-1. Split type (권장 v1)

- time split만 허용 (random split 금지)
- splits_v1에 (train/val/test) 날짜 구간을 저장

7-2. Dataset 종류 고정

- training: train 구간
- evaluation: val/test 구간
- replay: 특정 과거 구간을 “서빙 리플레이”로 재현하기 위한 별도 구간(선택)
- observability: 원본 로그 전체(학습에 바로 쓰지 않음)

8. Dataset Manifest (SSOT)

dataset_manifest_v1에 아래를 고정한다.

- dataset_version
- split_id
- feature_set_version
- embedding_versions (필요 시)
- join_rules_json (as_of_ts/published_at)
- negative_sampling_spec_json (**seed 포함 필수**)
- attribution_spec_json + attribution_rule_version
- candidate_budget_spec_version (서빙 예산과 정합)

8-1. 버전 전파 규칙 (Non-Negotiable)

위 항목 중 하나라도 변경되면, dataset_version을 반드시 변경(bump)한다.
"같은 dataset_version인데 내용이 다른" 상황은 구조적으로 차단한다.
(정본: RFC-DATASET-BENCH-005 §7-1)

8-2. Dataset Manifest Diff Tool (연구 자산화)

- dataset_manifest 버전 간 자동 비교 도구를 제공한다.
- diff 출력: 변경된 필드, 이전값 → 이후값, 변경 사유(커밋 메시지 연동 권장)
- 목적: "이 실험과 저 실험이 정확히 무엇이 달랐는지"를 1분 안에 파악 가능하게 함
- manifest diff 이력은 append-only로 보관하며, 실험 추적의 SSOT가 된다.

9. Integrity Gates (자동 실패 조건)

- impression → policy join 성공률 임계치(예: 99%+) 미만이면 빌드 실패 또는 경보
- impression → action join 누락률 모니터링(표준 지표)
- leakage 위반률 > 0이면 빌드 실패(하드)
- schema_version mismatch 레코드 비율 경보

9-1. Leakage 위반 사례 자동 저장 (연구 자산)

- leakage gate에서 위반이 감지되면(빌드 실패와 별개로), **위반 사례 상위 N건(기본 100건)을 별도 artifact로 자동 저장한다.**
  - 파일명: `leakage_violations_{dataset_version}_{build_ts}.parquet`
  - 필드: (example_id, impression_id, violated_rule, as_of_ts, event_ts, published_at, feature_name, expected_max_ts, actual_ts)
- 목적:
  - 위반 패턴 분석(어떤 feature/source에서 주로 누설이 발생하는지)
  - 파이프라인 버그 조기 발견
  - "왜 이 빌드가 실패했는지" 즉시 진단 가능
- 보관: dataset_version 단위로 영구 보관

