RFC-FEATURE-MANIFEST-010

Title: 하이엔드 와인 추천 — feature_manifest_v1 및 Online/Offline Parity Gate v1
Status: Draft v1.0
Scope: feature를 “정의(Manifest)”로 고정하고, online materializer와 offline builder가 동일 구현임을 CI로 강제한다.
Depends On:
- RFC-REALTIME-PIPELINE-008: parity 강제 원칙
- RFC-IR-SCHEMA-007: features_offline_v1 / features_online_v1 / feature_manifest_v1 저장 스키마

0. 목표 (What we freeze)

- feature 정의는 코드가 아니라 manifest가 SSOT다(정의/조인/누설 규칙/기본값/레시피 버전).
- online/offline 출력 차이는 “허용 0”을 원칙으로 하되, 단계적 롤아웃을 위해 tier를 둔다.

1. Manifest 포맷

1-1. 저장 형태

- feature_manifest_v1.manifest_json에 JSON 문자열로 저장(스키마는 본 RFC에서 고정)
- 사람이 편집하는 원본은 YAML을 권장하되, 배포/저장은 JSON으로 normalize(파서/정합성).

1-2. 최상위 스키마(개념)

- feature_set_version: string
- generated_at: timestamp
- entities: array<entity_manifest>

entity_manifest
- entity_type: "user"|"session"|"wine_core"|"wine_sku"|"context"|"user_item"
- join_keys: array<string>         // canonical key list
- features: array<feature_def>

feature_def
- name: string                    // snake_case, prefix 권장
- dtype: "float"|"int"|"string"|"bool"|"vector"|"json"
- source: struct<
    table: string,
    key: string,
    value_path: string nullable   // JSON path 등(필요 시)
  >
- time_travel_rule: struct<
    rule: "as_of_ts_le_event_ts"|"published_at_le_event_ts"|"none",
    timestamp_field: string       // as_of_ts/published_at 등
  >
- recipe_version: string          // transform/recipe version (lineage 3단 키)
- default: string|null            // null_policy 포함해 명시
- null_policy: "error"|"default"|"allow_null"
- description: string
- owner: string nullable
- tier: "critical"|"important"|"experimental"

내 의견("tier"를 넣는 이유)
- parity diff=0을 바로 200개 피처에 적용하면 초기에 CI가 계속 깨져서 결국 게이트를 끄게 된다.
- critical(서빙/랭킹 핵심)부터 강제하고, coverage를 늘리는 게 현실적인 강제력이다.

1-3. Parity Coverage 증가 목표 (분기별 SOTA 강화)

- critical tier coverage를 **분기마다 증가 목표를 설정**한다.
  - Q1: critical tier 20개 피처 diff=0 강제
  - Q2: critical tier 40개 + important tier 20개
  - Q3: critical + important 전체 diff=0
  - Q4: experimental tier까지 리포트(diff=0 권장)
- 목표 미달 시 분기 리뷰에서 원인 분석 + 다음 분기 액션 플랜 필수.
- coverage 현황은 quality_gate_report_v1에 분기별로 기록한다.

1-4. Manifest-First 프로세스 규칙 (문화 고착)

- **feature 추가/변경 시 manifest PR이 코드 PR보다 선행한다.**
  - 코드 변경 없이 manifest만 변경하는 PR도 유효하다.
  - manifest PR 없는 feature 변경 코드 PR은 리뷰 거부한다.
- **manifest diff가 곧 feature change log가 된다.**
  - manifest 변경 시 자동으로 diff를 생성하고, feature_set_version bump와 함께 기록한다.
  - "코드보다 manifest가 계약" 원칙을 프로세스로 강제한다.

2. Feature 네이밍/규약

- prefix 권장
  - user_: user entity
  - sess_: session entity
  - item_core_: wine_core entity
  - item_sku_: wine_sku entity
  - ctx_: context entity
  - ui_: user_item entity

- 예시
  - user_price_elasticity
  - sess_recent_core_ids_hash
  - item_core_critic_consensus_score
  - item_sku_in_stock
  - ctx_surface
  - ui_affinity_score

3. Online Materializer 계약

- 입력: (entity_id, context, request_ts/event_ts)
- 출력: features_online_v1 최신 스냅샷(as_of_ts) + feature_set_version
- 필수: manifest에 정의된 null_policy를 동일하게 적용
- 금지: 외부 동기 호출(서빙 지연 유발). 필요하면 별도 캐시/배치로 materialize.

4. Offline Builder 계약

- 입력: (entity_id, event_ts, feature_set_version)
- 출력: features_offline_v1 (event_ts 기준 time-travel join)
- 필수: as_of_ts/published_at <= event_ts 규칙 강제
- 필수: recipe_version/transform_version/lineage_input_refs 기록

5. Parity CI Gate

5-1. 테스트 정의

- 샘플 셋: 고정 seed로 N개 (user_id, item_id, event_ts, context) 추출
- 비교 대상:
  - offline: (entity_id, event_ts)로 생성된 features_offline_v1
  - online: 동일 event_ts를 request_ts로 넣어 materializer를 호출한 결과
- diff 정책:
  - critical tier: diff == 0 (엄격)
  - important tier: diff 허용 0 (원칙), 단 초기에는 allowlist(기간 한정) 가능
  - experimental tier: CI 실패 대신 리포트만 생성 가능(초기)

5-2. 비교 방식(권장)

- float: abs(a-b) <= eps (예: 1e-6) 또는 ULP 기반
- int/bool/string: exact match
- vector: L2 distance <= eps (또는 cosine diff <= eps) + dim match
- json: canonicalize(sort keys) 후 비교

내 의견(실무적으로 자주 터지는 포인트)
- online은 "최신 스냅샷"이라 event_ts 기준으로 재현이 안 되는 경우가 많다.
- 그래서 parity 테스트는 online도 request_ts/event_ts를 받도록 설계하거나, online store가 as_of_ts 스냅샷을 유지해야 한다.

5-3. Parity Diff Histogram (리포트 자산화)

- parity 테스트 실행 시, **per-feature diff 분포(histogram)를 quality_gate_report_v1에 기록한다.**
  - 필드: (feature_name, tier, diff_mean, diff_p50, diff_p95, diff_max, violation_count, sample_count)
- 목적:
  - "어떤 피처에서 얼마나 차이나는지" 추세를 시계열로 추적
  - drift 원인 분석의 1차 근거 (아래 5-4 참조)
  - parity 개선 로드맵의 우선순위 근거

5-4. Drift 원인 자동 분류 (권장)

- parity 위반이 발생하면, 원인을 자동으로 태깅한다 (가능한 범위에서).
  - **data_delay**: online/offline 데이터 도착 시간 차이 (ingest_ts 비교)
  - **version_mismatch**: feature_set_version 또는 recipe_version 불일치
  - **logic_bug**: 동일 버전인데 결과가 다름 (가장 위험 — 즉시 조사)
  - **schema_drift**: 입력 테이블 스키마 변경으로 인한 파생 결과 차이
  - **unknown**: 위 4가지에 해당하지 않음 (수동 조사 필요)
- 분류 결과는 quality_gate_report_v1.violations에 drift_cause 필드로 추가한다.

6. Leakage Gate (manifest 기반)

- manifest의 time_travel_rule을 기반으로, offline builder가 위반 레코드를 산출물에 포함하지 못하게 한다.
- 위반률(샘플/전체)을 quality_gate_report_v1에 append-only로 기록한다.

7. 예시 manifest (축약)

{
  "feature_set_version": "fs_v1",
  "generated_at": "2026-02-09T00:00:00Z",
  "entities": [
    {
      "entity_type": "user",
      "join_keys": ["user_id"],
      "features": [
        {
          "name": "user_price_elasticity",
          "dtype": "float",
          "source": {"table":"user_profile_snapshot_v1","key":"user_id","value_path":"price_elasticity"},
          "time_travel_rule": {"rule":"as_of_ts_le_event_ts","timestamp_field":"as_of_ts"},
          "recipe_version": "profile_v1",
          "default": "0.0",
          "null_policy": "default",
          "description": "User price elasticity (rolling window)",
          "owner": "recsys",
          "tier": "critical"
        }
      ]
    }
  ]
}

