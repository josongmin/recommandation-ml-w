RFC-SOTA-ROADMAP-012

Title: High-End Wine Recommendation — SOTA Roadmap v2 (3-Year Research↔Product Integrated Plan)
Status: Draft v1.0
Scope: “SOTA를 굳히는 수준”을 넘어, 외부에서 인용 가능한 레퍼런스 스택(벤치/데이터/프로토콜/베이스라인)을 3년 플랜으로 고정한다.
Depends On:
- RFC-E2E-PIPELINE-006: E2E 파이프라인 Non-Negotiable(SSOT/lineage/manifest/time-travel)
- RFC-IR-SCHEMA-007: 저장 스키마 계약(Logs/Gold-A/B/C/Dataset manifest)
- RFC-DATASET-BENCH-005: 벤치/태스크/평가/재현 프로토콜
- RFC-DATASET-BUILDER-011__Impression-Centric-Dataset-Builder-v1.md: impression 기반 학습 데이터 재현
- RFC-FEATURE-MANIFEST-010__Feature-Manifest-and-Parity-Gate-v1.md: parity gate(offline/online)
- RFC-LOG-SCHEMA-009__Event-and-SSOT-Log-Schema-v1.md: policy/impression/action 로그 계약
- RFC-REC-EXT-004: high-end 신호(temporal/expert/graph/market/condition)

1. 한줄 요약

지금 구조는 이미 상위권 설계임. SOTA로 "굳히기"가 아니라 SOTA를 규정하는 레퍼런스 스택이 되려면
(1) 평가 프로토콜을 더 혹독하게 고정하고,
(2) 데이터·피처·모델보다 반증 가능한 실험 체계를 SSOT로 끌어올리고,
(3) 와인 도메인 고유 신호를 "연구 난제급 문제"로 재정의해야 함.

1-1. SOTA 규정자(Definer) 5조건 (정본: RFC-DATASET-BENCH-005 §7-4)

"잘 만든 추천 시스템"이 아니라 "와인 추천 SOTA를 규정하는 레퍼런스 스택"이 되기 위한 5개 충족 조건:

1. **재현 가능한 데이터/평가 프로토콜**: dataset_manifest + time_split + seed + candidate_budget 전부 고정
2. **반사실 평가 기본 탑재**: IPS/SNIPS/DR이 모든 벤치에 필수. 오프라인 반사실 평가 없이 SOTA 주장 불가
3. **도메인 고유 난제 정의**: extreme sparsity / drinking window / expert consensus 등 와인만의 정식 태스크
4. **외부 검증 루프 존재**: 외부 재현/비교/반증 가능한 리더보드 최소 1개 상시 운영
5. **Long-horizon 중심 목적함수**: 7일/30일 재구매, cellar-building, 반품율이 승자 판정 1급 기준

이 5개가 본 로드맵의 "최종 달성 기준"이다. 아래 모든 Phase는 이 5조건을 충족시키기 위한 경로이다.

2. 목표 정의 (3년)

2-1. 목표 A: 레퍼런스 스택 고정
- 재현 가능한 dataset manifest + 고정 split + 누설 방지 + 공개 가능한 baseline을 갖춘 “프레임워크”로 고정

2-2. 목표 B: 문제 재정의(하이엔드 난제화)
- 단기 CTR 최적화가 아니라 장기 취향 형성 + 희소/고가 도메인 최적화를 1급 목표로 승격

2-3. 목표 C: 외부 검증 루프
- 내부 성과가 아니라 외부 재현/리더보드/챌린지(가능한 범위에서)로 SOTA를 증명

3. 지금 설계의 SOTA 포지션 진단

3-1. 이미 SOTA에 근접한 축
- impression 단위 SSOT + 노출 기반 학습 정의 (프로토콜 상위권)
- time-travel join + lineage 3단 키 + manifest 고정 (재현성/누설 방지 SOTA급)
- Master/IR 분리 + wine_core vs wine_sku 분리 (ID 안정성 문제 구조적 해결)
- Graph/Temporal/Expert-aware 신호 (도메인 특화 SOTA 방향)

3-2. 다음 차별화 포인트
- 평가(특히 반사실) + 문제정의 + 데이터 과학 난이도(난제)에서 나온다.

4. 혹독한 SOTA 제안 (핵심)

4-1. 평가를 SOTA로 끌어올리기
- Counterfactual Evaluation 기본 탑재
  - IPS / SNIPS / DR 기반 오프라인 평가를 표준 프로토콜로 고정
  - policy_log 기반 propensity 추정 가능 필드/버전 필수화
- Challenge-style Benchmark 운영(가능 범위)
  - high-end only, cold-start only, expert-aware, temporal-fit 등 트랙 분리
  - extreme sparsity split(고가·희소만) 별도 유지
- Long-horizon metric 도입
  - 7일/30일 재구매율, cellar-building 패턴, 장기 만족/반품율
  - 단기 CTR 최적화 모델은 감점(하이엔드는 장기 취향 형성이 핵심)

4-2. 데이터 레벨 SOTA
- Sensory Ground Truth 강화(자체 GT)
  - sommelier 패널 기반 pairwise similarity, style clustering, maturity stage 라벨링
- Terroir physics 모델링(단순 feature → 잠재 변수)
  - vintage별 latent terroir factor 추정
- Storage/Aging 데이터 수집
  - 보관 조건 로그(온도/습도) 연동
  - 동일 와인의 “보관 상태별 취향 차이” 모델링

4-3. 모델링 SOTA
- Multi-objective RL/Bandit Ranker
  - 만족도/장기 LTV/재구매/탐험 가치를 보상으로 정의
  - contextual bandit → full RL로 확장
- Uncertainty-aware recommendation
  - confidence/uncertainty 출력
  - high-variance 와인은 “모험적 추천”으로 포지셔닝
- Cross-modal joint space 고도화
  - 텍스트+이미지+구조화+그래프를 shared latent space로 학습
  - “분위기 기반 검색”을 1급 태스크로 승격

4-4. 과감한 문제 재정의
- “Best Wine”이 아니라 “Best Wine For This Life Moment”
  - 기념일/선물/셀러용/지금 마실용 분리
- 추천을 Discovery Engine으로 정의
  - 유저가 모르는 고급 생산자 발굴이 목표
  - 인기 편향 모델은 감점
- Explainability를 연구 주제로 승격
  - 설명 품질을 human study로 평가
  - “설명 설득력 점수”를 KPI/벤치로 둠

5. 3년 리서치-제품 통합 로드맵

5-1. Year 0~0.5 (0~6개월): SOTA 기초 인프라를 "논문 레벨"로 고정 → 규정자 5조건 중 #1, #2 달성

고정 산출물(SSOT급)
- A1) dataset_manifest_v1 불변 스펙 완성(라벨/네거티브/윈도우/스플릿/조인 규칙 + **negative sampling seed** + **버전 전파 규칙**)
- A2) feature_manifest_v1 + parity gate를 CI 강제(critical tier 20개부터 diff=0, **분기별 coverage 증가 목표 설정**)
- A3) policy_log를 "오프라인 반사실 평가"까지 쓰도록 필드/버전 확정(후보집합/점수/버전/제약/propensity + **propensity 누락률 모니터링 게이트**)
- A4) 벤치 시나리오 스위트(B0~B3)를 "결과가 아니라 절차"로 고정 + **모든 벤치에 IPS/SNIPS/DR 필수 포함**
- A5) **join_proof를 정식 artifact로 보관** + **leakage 위반 사례 샘플 자동 저장** (Dataset Builder 연구 자산화)
- A6) **dataset_manifest diff tool** 제공 (실험 추적 SSOT)

최소 외부 공개 가능 패키지(1차)
- P0) 공개 가능한 subset(라이선스 안전) + 완전 재현 가능한 baseline 코드
- P1) 리더보드 지표 세트(Recall/NDCG + cold-start + high-end slice)

베이스라인(고정)
- RS: MF/BPR, Two-Tower+ANN, LightGCN, DeepFM/DLRM
- 멀티모달: text embedding 후보 + simple fusion ranker

5-2. Year 0.5~1.5 (6~18개월): 하이엔드 난제를 "정식 문제"로 만들고 외부 검증 루프 개시 → 규정자 5조건 중 #3, #4, #5 달성

핵심 연구 문제 3종(챌린지 트랙화 가능)
- (R1) Extreme-sparsity recommendation
  - impression 기반 negative 우주 고정 + cold-start split 고정
- (R2) Expert-aware preference modeling
  - authority-weighted aggregate + consensus/discrepancy를 1급 피처로 고정
- (R3) Temporal drinking-window fit
  - stage/confidence를 모델 입력+설명 SSOT로 고정

외부 검증 루프(2차)
- C1) High-end slice 리더보드
- C2) Cold-start only 트랙
- C3) Expert-aware 트랙

제품화 병행
- S1) Multi-recall + 2-stage rerank + post-rank 표준 형태 고정
- S2) 설명 시스템(temporal/expert/scarcity/price) 템플릿/버전 고정
- S3) **Long-horizon 승자 판정 규칙 운영 개시**: 7일/30일 재구매율 하락 모델은 배포 불가 (규정자 조건 #5)
- S4) **parity coverage Q2 목표 달성**: critical 40개 + important 20개 diff=0

5-3. Year 1.5~3 (18~36개월): "SOTA를 규정하는" 단계 → 규정자 5조건 전부 충족 + 유지

Counterfactual/causal evaluation을 1급 시민으로
- O1) IPS/SNIPS/DR 기반 정책 평가 프로토콜 고정
- O2) propensity 추정 가능 policy_log 필드 필수화(노출/후보/점수/제약/버전/탐험 정책)

Exploration-aware ranker
- R1) 장기 취향 학습 보상
- R2) uncertainty-aware 추천
- R3) discovery KPI 트랙 분리(인기 편향 억제)

멀티모달+그래프 최종 통합
- M1) shared latent space 학습
- M2) 분위기 기반 검색/추천을 벤치 포함
- M3) sensory similarity supervision을 자체 GT로 강화(소규모라도 사람 라벨)

챌린지 운영(“기준이 되는” 방법)
- K1) 매년 1회 트랙 3개(희소/권위/시간) 정기 개최(가능 범위)
- K2) 베이스라인/데이터/프로토콜 공개 가능한 형태 유지
- K3) 내부 제품 모델도 동일 manifest/lineage/time-travel 규칙 위에서만 움직이게 강제

6. 바로 실행 가능한 다음 액션 12개 (SSOT로 승격)

0~4주 (규정자 조건 #1, #2 기초)
1) dataset_manifest_v1에 벤치 트랙(희소/권위/시간) 메타 추가 + **negative sampling seed 고정** + **버전 전파 규칙 적용**
2) parity gate critical tier 20개부터 diff=0 강제 + **분기별 coverage 증가 목표 문서화**
3) policy_log에 propensity 추정 최소 필드셋 확정 + **propensity 누락률 모니터링 게이트(>5% 경보, >20% 차단) 설정**
4) high-end slice 정의(가격 상위 N%, 생산량 하위 M%, 노출수 하위 K%) 고정
5) cold-start split(새 생산자/새 빈티지/새 sku) 3종 고정

4~12주 (규정자 조건 #3 기초)
6) baseline 4종(MF/BPR, Two-tower, LightGCN, DLRM)을 동일 manifest에서 재현
7) expert-aware aggregate IR 1차(가중 평균/합의도/분산)
8) temporal IR 1차(stage/confidence)
9) 공개 가능한 subset 구축(권리/라이선스)
10) 리더보드 지표 세트 고정(일반 + cold-start + high-end)
11) **join_proof artifact 보관 파이프라인 구축** + **leakage 위반 사례 자동 저장 게이트 도입**
12) **manifest PR 필수 프로세스 도입** (feature 추가/변경 시 manifest PR 선행)

3~6개월 (규정자 조건 #2, #4, #5 기초)
13) counterfactual 평가(IPS/SNIPS/DR) 파이프라인 1차 도입 + **모든 벤치 리포트에 필수 포함 강제**
14) 챌린지 운영 문서(규칙/데이터/베이스라인/리더보드) 초안 작성
15) **Long-horizon 승자 판정 규칙 초안 작성** (7일/30일 재구매율 하락 = 배포 불가)
16) **dataset_manifest diff tool 1차 구현**
17) **parity diff histogram 리포트 자동 생성 + drift 원인 자동 분류 도입**
