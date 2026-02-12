RFC-DATASET-BENCH-005

Title: High-End Wine Recommendation — Dataset Expansion & Benchmark Framework
Status: Draft v1.0
Scope: 데이터셋 확장 전략, IR 매핑 규격, 벤치 시나리오, 평가 체계, 권리/재현성 가이드
Depends On: Wine Master/IR v1, RFC-REC-EXT-004

1. Executive Summary

1-1. 목적
하이엔드 와인 추천에서 공신력 있는 데이터 근거 + 재현 가능한 벤치 체계를 고정함.

연구용 공개 데이터로 알고리즘 검증

상용 데이터로 품질 고도화

SSOT/IR 분리 원칙 하에 권리·라이선스 추적

1-2. 결과물

데이터셋 카탈로그(용도별)

IR 매핑 스펙

표준 벤치 시나리오

평가 지표 세트

라이선스/권리 집행 규칙

2. 전제 정리 및 팩트 정정

2-1. WineSensed가 제공하는 "검증 가능한" 핵심 모달리티

WineSensed는 라벨 이미지(약 897k), 리뷰(약 824k), 빈티지 단위 메타(연도/지역/평점/도수/가격/포도 구성)와, 일부 서브셋에 대해 사람 기반 "풍미 유사도 거리"(pairwise flavor distances)를 포함하는 멀티모달 데이터셋임.

즉, pH/총산도/잔당/SO2 같은 "화학 패널"은 WineSensed 기본 메타에 명시되어 있지 않음(이 축은 별도 Raw 수급이 필요함).

2-2. "화학적/기술적 피처가 품질(감각 평가)에 유의미"하다는 공신력 근거

UCI Wine Quality(Cortez et al. 2009)는 물리화학 지표(산도, 잔당, SO2 등)로 전문가 품질 점수를 모델링하는 표준 데이터셋 축임.

또한 물리화학 지표와 감각/품질의 상관 및 예측을 다루는 연구 축이 지속적으로 존재함(예: 물리화학 지표와 품질의 상관/인과 분석).

3. 학계·업계 SOTA 근거 기반 "Feature 축" 재정의

아래는 "예측 성능 또는 추천 품질에 기여"가 논문·운영 사례로 뒷받침되는 축을, physicochemical/terroir/multimodal/expert 관점으로 재정렬한 것임.

3-1. Multimodal + Sensory Similarity(와인 도메인 최상급 축)

3-1-1. Raw(데이터셋으로 즉시 가능)

Label image(라벨 시각 정보)

Review text(대규모)

Vintage metadata: year, region, rating, alcohol %, price, grape composition

Flavor similarity distances(부분 서브셋)

WineSensed가 이 구성을 "대규모 + 동일 키(vintage)"로 제공한다는 점 자체가 연구 근거축임.

3-1-2. Derived(IR로 만들어야 하는, 성능 기여가 기대되는 표준형)

Visual embedding(라벨) + Text embedding(리뷰/노트) + Meta feature(도수/가격/포도구성) late-fusion 또는 joint-space

Flavor-profile vector(Primary/Secondary/Tertiary 분리): "텍스트 신호를 구조화해 추천에 넣는다"는 방향은 리뷰-토픽 결합 계열(RecSys 2013)로 정당화 가능함.

Sensory-similarity supervision: WineSensed의 flavor distance를 "유사도 학습"에 직접 쓰는 것이 이 데이터셋의 핵심 기여 포인트임.

3-2. Review text의 "유의미 기여" 축(RecSys 정석)

3-2-1. 근거

평점 모델이 리뷰 텍스트를 버리면 해석 가능성과 예측력이 떨어진다는 문제의식에서, latent factor + review topic 결합이 성능·해석을 동시에 개선하는 대표 축을 제시함.

3-2-2. SSOT/IR 설계에 그대로 매핑되는 실행 결론

Review Master는 원문·권리·출처 SSOT

Review IR에서 정규화/토픽/임베딩/태그/집계를 버전 관리

이 구조가 "리뷰 신호를 모델에 넣는 표준 접근"과 정합임.

3-3. Context/Temporal(빈티지·상황) 축(RecSys survey 정석)

3-3-1. 근거

Context-aware RS는 상황(시간/장소/동반자/목적 등)을 추천의 입력으로 포함해 적합도를 높이는 축으로 정리되어 있음. 와인의 "음용 적기/계절/행사"는 이 범주에 직접 해당함.

3-3-2. 와인 도메인에서의 구체화

Drinking window stage(too_young/peak/past)

Vintage climate deviation(해당 지역의 장기 평균 대비 편차)

이 2개는 "시간에 따라 성격이 변한다"는 도메인 특성을 모델 입력으로 공식화하는 장치임.

3-4. Graph(희소성·콜드스타트) 축(업계 운영 성공 근거)

3-4-1. 근거(운영까지 증명된 그래프 추천)

Pinterest PinSage는 그래프+노드 피처를 결합해 웹 스케일에서 학습/서빙하고 오프라인/유저스터디/A-B 테스트로 효용을 보고한 대표 사례임. "희소한 아이템도 관계로 전파"가 작동한다는 업계 근거로 쓰기 좋음.

3-4-2. 와인에 그대로 대응

Heterogeneous graph(User, Wine_Core, Producer, Region, Variety, Tag)로 cold-start를 producer/region/variety 경유 전파로 완화하는 설계는 위 운영 근거와 논리적으로 정합임.

3-5. Physicochemical/Technical("품질"의 객관 축)

3-5-1. 근거(데이터셋 레벨)

UCI Wine Quality는 물리화학 지표로 전문가 품질 점수를 예측하는 대표 기준점임. 여기서 "pH/산도/잔당/SO2" 류가 유효 입력축이라는 근거를 확보할 수 있음.

3-5-2. 주의

이 축은 WineSensed로는 충족되지 않으므로, 상용 Raw 소스로 "테크시트/랩테스트/수입사 스펙"을 별도 수급해야 함.

4. Dataset Catalog (Purpose-Oriented)

4-1. RS 벤치/상호작용 중심

(1) X-Wines (2023)
용도

2-Stage RS 베이스라인

CF/BPR/LightGCN 비교

오프라인 재현 벤치

강점

대규모 user–item 상호작용

와인 도메인 특화

제약

실제 상용 로그와 분포 차이 가능

IR 매핑

user_id → user node

wine_id → wine_core_id (via source_link)

rating/event → interaction edge

4-2. 멀티모달 학습

(2) WineSensed (NeurIPS D&B)
용도

텍스트+이미지 멀티모달 추천

라벨 기반 검색

설명 생성 실험

강점

라벨 이미지 대규모(약 897k)

리뷰 텍스트 대규모(약 824k)

빈티지 단위 메타(연도/지역/평점/도수/가격/포도 구성)

일부 서브셋에 대한 풍미 유사도 거리

제약

Vivino 기원 데이터 포함 가능성

상용 결합 시 rights 엄격 관리

화학 패널(pH/총산도/잔당/SO2) 미포함

IR 매핑

이미지 → wine_image_ir_v1

리뷰 → review_master_v1 + IR

속성 → wine_attr_ir_v1

풍미 유사도 → flavor similarity supervision

4-3. 텍스트/온톨로지 부트스트랩

(3) Wine Reviews 130k(와인 매거진류)
용도

전문가 어휘 사전 구축

taste tag 추출기 학습

NLP 파이프라인 검증

온톨로지 태거/향미 태그 추출기 부트스트랩에 적합

강점

전문가 리뷰 중심

지역/품종/가격 메타 풍부

variety/location/winery/price/description 포함된 대규모 리뷰 코퍼스

제약

user interaction 부족

IR 매핑

review_text_ir_v1

review_taste_tag_ir_v1

4-4. 물리화학·품질 축

(4) UCI Wine Quality
용도

acidity/sweetness/body 추정 보조 모델

구조 점수 회귀

물리화학 지표로 전문가 품질 점수 예측

IR 매핑

wine_attr_ir_v1 구조 스코어 보조

4-5. 테루아·기후 축(구축형)

(5) 오픈 기후 데이터 + 연구 축
용도

테루아/빈티지 분리 모델링

기후 변수로 와인 품질/지역 모델

강점

GDD/강수/기온 등은 NOAA GHCN-D 같은 글로벌 일별 기후 데이터로 수급 가능(빈야드/지역 좌표 매핑 필요)

제약

"즉시 가져다 쓰는 단일 공개 와인데이터셋"이라기보다, 지역 좌표 기반으로 기후/토양 레이어를 조합해 만드는 쪽이 현실적임

IR 매핑

wine_terroir_ir_v1 (climate/soil fingerprint embedding)

3. IR Mapping Standard

3-1. 원칙

Raw → Master

정제/임베딩/집계 → IR

모든 IR은 재생성 가능

3-2. 필수 필드

source_system

source_item_key

license_tag

rights_store_raw

rights_display

mapping_confidence

3-3. Versioning

clean_version

embedding_model

ontology_version

graph_version

4. Benchmark Scenario Suite
4-1. B0 Baseline RS

구성

Matrix Factorization

BPR Loss

Recall@K / NDCG@K

목적

최소 기준선 고정

4-2. B1 Two-Stage Industrial

구성

Candidate: Two-Tower + ANN

Ranking: DeepFM/DLRM

평가

NDCG@10

HitRate@10

4-3. B2 Graph-Enhanced

구성

LightGCN / Hetero GNN

Producer/Region propagation

평가

Cold-start NDCG

Sparse-item Recall

4-4. B3 High-End Specialized

조건

가격 상위 N%만 필터

생산량 낮은 와인 중심

평가

High-price segment NDCG

Expert-aligned ranking score

4-5. B4 Temporal-Aware

조건

drinking window 반영

평가

“현재 peak” 와인 노출 비율

User satisfaction proxy

4-6. 하이엔드 도메인 벤치 태스크(SSOT 고정)

도메인 벤치(하이엔드): 아래 태스크 3~4개를 정의만이라도 SSOT로 고정

T1: 희소 아이템 추천(노출 가능 후보셋 고정)

목적: 희소한 하이엔드 와인의 cold-start 완화 능력 평가

후보셋: 노출 가능한 희소 와인만 포함(관측 편향 제거)

평가지표: Sparse-item Recall@K, Cold-start NDCG@K

T2: drink-window 적합 추천(as_of_ts 기준)

목적: 시간에 따른 와인 품질 변화를 반영한 추천 정확도 평가

후보셋: as_of_ts 기준으로 평가 시점 고정

평가지표: Peak-proximity score, Temporal-aligned NDCG@K

T3: critic-alignment(권위 가중 집계가 실제로 이득인지)

목적: 전문가 리뷰 가중치가 추천 품질에 미치는 영향 평가

후보셋: 전문가 리뷰가 있는 와인 집합

평가지표: Expert-weighted NDCG@K, Authority alignment score

T4: 멀티모달 탐색(라벨 이미지 기반 탐색 + 텍스트 쿼리)

목적: 멀티모달 신호 결합의 효과 평가

후보셋: 라벨 이미지와 리뷰 텍스트가 모두 있는 와인

평가지표: Multimodal retrieval Recall@K, Cross-modal alignment score

4-7. Challenge-style Benchmark (외부 검증 지향; 운영 가능 범위에서)

목표: “내부 결과”가 아니라, 외부에서 반증 가능한 프로토콜/리더보드 형태로 성능을 고정한다.

- Track A: High-End Slice (고가/희소)
- Track B: Cold-start Only (새 생산자/새 빈티지/새 SKU)
- Track C: Expert-aware (권위자 가중 + 합의/분산)
- Track D: Temporal Fit (drinking window 적합)

Extreme Sparsity Split(별도 유지)

- 정의: 고가·희소 와인만으로 구성된 “극단 희소성” 분할
- 목적: 인기/노출 편향에 기대는 모델을 구조적으로 감점하고, 관계/도메인 신호를 활용하는 모델을 분리 평가

5. Evaluation Metrics Standard

5-1. Offline

Recall@K

NDCG@K

MAP

Coverage

Novelty

5-2. High-End 특화

Expert-weighted NDCG

Price-satisfaction score

Scarcity-aware utility

5-3. Online (참고)

CTR

CVR

AOV uplift

5-4. Counterfactual / Off-policy Evaluation (SOTA 필수 — 옵션 아님)

목표: "A/B 결과만 진실" 구조에서 탈피하고, policy_log를 이용해 오프라인에서 정책 비교가 가능하도록 표준 프로토콜을 고정한다.

강제 규칙 (Non-Negotiable)

- **모든 벤치 리포트(B0~B4, T1~T4)에 IPS/SNIPS/DR 중 최소 1개를 필수 포함한다.**
  - Counterfactual 지표 없는 벤치 리포트는 "미완료(incomplete)"로 분류하고 SOTA claim에 사용할 수 없다.
- **오프라인 반사실 평가 없이 SOTA 주장 불가.** 이 규칙은 예외 없이 적용한다.

지표

- IPS (Inverse Propensity Scoring)
- SNIPS (Self-Normalized IPS)
- DR (Doubly Robust)

필수 조건

- policy_log에 propensity 추정이 가능한 최소 필드셋(탐험 정책/확률/후보집합/점수/제약/버전)이 남아야 함
- propensity 추정 방식(또는 정책)과 버전은 벤치 리포트에 함께 기록
- propensity 필드 누락률은 quality_gate_report_v1에서 모니터링하며, 누락률 > 5%이면 경보 발생

5-5. Long-horizon Metrics (하이엔드 시장 특화 — 승자 판정 기준)

목표: 단기 CTR 최적화를 감점하고, 장기 취향 형성/셀러 구축을 1급 성과로 만든다.

지표

- 7일/30일 재구매율(재방문/재구매)
- cellar-building 패턴(저장/재구매/빈티지 축적)
- 반품/취소율(만족도 proxy)
- 장기 만족도 설문(가능 시; human feedback)

강제 규칙 (승자 판정)

- **Long-horizon 지표 개선 없이 short-term CTR만 개선된 모델은 "승자 아님"으로 판정한다.**
- 구체적으로: 7일/30일 재구매율이 기존 대비 하락하면, CTR/NDCG가 올라도 배포 승인 불가.
- short-term CTR 최적화에만 집중한 모델에는 벤치 리포트에 "short-term only" 태그를 부여하여 구분한다.
- 하이엔드 도메인의 핵심은 "지금 클릭"이 아니라 "장기 취향 형성"이므로, 이 규칙은 도메인 차별화의 핵심이다.

6. Rights & Compliance Rules

6-1. 데이터 계층 분리

학습 가능

저장 가능

노출 가능
각각 독립 플래그

6-2. 공개 데이터셋 정책

연구/부트스트랩 전용

상용 모델과 논리적 분리

6-3. Lineage 추적

모든 파생 IR은 source_link 참조

7. Reproducibility Protocol

7-1. 고정 요소

train/val/test split seed

negative sampling 규칙 + **negative sampling seed** (재현을 위해 seed를 dataset_manifest에 명시 고정)

feature schema 버전

as_of_ts(평가 시점) 고정: 시간축이 흔들리지 않도록 관측 시점 명시

"기회가 있었던 후보셋" 고정: 가격/희소성 편향 완화를 위한 프로토콜. **이 후보셋 정의(candidate_budget_spec)를 논문급 프로토콜로 명문화한다.**

counterfactual 평가 프로토콜 고정: IPS/SNIPS/DR 계산 규칙 + propensity(또는 추정) 버전

attribution rule version: 라벨 attribution 규칙 버전

**버전 전파 규칙 (Non-Negotiable)**

- 아래 항목 중 하나라도 변경되면, dataset_version을 반드시 변경(bump)한다:
  - negative sampling seed 또는 규칙
  - candidate_budget_spec_version
  - feature_set_version
  - embedding_versions
  - join_rules (as_of_ts/published_at)
  - attribution_spec
  - split 기간
- 이 규칙은 "같은 dataset_version인데 내용이 다른" 상황을 구조적으로 차단한다.

7-2. 산출물

벤치 리포트 JSON

모델/IR 버전 매트릭스

하이엔드 태스크별 상세 리포트(T1~T4)

7-3. SOTA Claim Checklist

"SOTA 결과물"로 자랑하기 위한 최소 요구사항:

평가 프로토콜 고정: 재현 가능한 벤치 시나리오 정의

강한 베이스라인: B0~B4 벤치에서 표준 알고리즘 비교

도메인 특수 태스크 개선: T1~T4 하이엔드 태스크에서 성능 향상 입증

근거축 보강: 최신 트렌드 + 정통 연구 동시 만족

IR 필드 보강: 하이엔드 도메인 특수성 반영

Counterfactual 평가: IPS/SNIPS/DR 기반 off-policy 평가가 **모든** 벤치 리포트에 필수 포함

Challenge 트랙: high-end slice / cold-start only / expert-aware / temporal-fit 분리 리더보드(가능 범위)

Long-horizon 승자 판정: 7일/30일 재구매율 하락 모델은 CTR 상승과 무관하게 승자 아님

7-4. SOTA 규정자(Definer) 5조건

"잘 만든 추천 시스템"이 아니라 "와인 추천 SOTA를 규정하는 레퍼런스 스택"이 되기 위한 5개 충족 조건:

1. **재현 가능한 데이터/평가 프로토콜**: dataset_manifest + time_split + seed + candidate_budget 전부 고정되어, 누구든 동일 조건에서 동일 결과를 재현 가능
2. **반사실 평가 기본 탑재**: IPS/SNIPS/DR 중 최소 1개가 모든 벤치에 포함. propensity 추정 방식/버전 명시. 오프라인 반사실 평가 없이 SOTA 주장 불가
3. **도메인 고유 난제 정의**: extreme sparsity / drinking window / expert consensus 등 와인 도메인만의 "어려운 문제"를 정식 태스크로 정의하고 벤치에 포함
4. **외부 검증 루프 존재**: 내부 A/B만이 아니라, 외부에서 재현/비교/반증 가능한 리더보드 또는 챌린지 트랙이 최소 1개 상시 운영
5. **Long-horizon 중심 목적함수**: 단기 CTR 아닌 7일/30일 재구매, cellar-building, 반품율 등 장기 지표가 승자 판정의 1급 기준

이 5개를 모두 충족하면, "추천 시스템"이 아니라 "레퍼런스 스택"으로 포지셔닝된다.

8. Raw/Derived 강화 로드맵(SSOT/IR 원칙 준수)

아래는 "논문/운영 근거가 있는 축"을 우선순위로, Raw 수급 → IR 파생 → 모델 투입 순서로 고정한 로드맵임.

8-1. Phase 0: 기준선 고정(재현 가능한 벤치)

WineSensed 기반 멀티모달 IR 생성(텍스트/이미지/메타) + flavor distance 활용 가능성 평가

리뷰 텍스트 기반 IR(정규화/임베딩/토픽) 생성 파이프라인을 RecSys 2013 축에 맞춰 고정

X-Wines 기반 B0~B2 벤치

8-2. Phase 1: Expert/Authority 신호(하이엔드 1순위)

Raw: author_type/critic metadata(가능 범위)

Derived: authoritative weighting, consensus vs controversy(분산)

리뷰 텍스트가 유효 신호라는 근거 위에 "작성자 신뢰도"를 곱하는 전략임.

8-3. Phase 2: Temporal/Context(음용 적기·빈티지)

Derived: drinking window stage, peak proximity score

Derived: vintage climate deviation(지역 평균 대비 편차)

Context-aware RS 축으로 정당화 가능하고, 와인 도메인 오류(지금 마시기 부적절 추천)를 구조적으로 줄이는 장치임.

기후 원천은 GHCN-D 등 오픈 기후 데이터 레이어를 사용 가능함.

8-4. Phase 3: Graph of Wine(희소·콜드스타트 돌파)

Raw: User–Wine, Wine–Producer, Wine–Region, Wine–Variety, Wine–Tag 엣지 구축

Derived: hetero graph embedding / propagation IR

PinSage류 운영 근거를 그대로 가져오는 단계임.

8-5. Phase 4: Physicochemical(객관 품질 축, 상용 Raw 수급 필요)

Raw: tech sheet(산도/잔당/SO2/오크 숙성 개월 등), 또는 랩테스트

Derived: balance index, aging potential score 같은 파생 지표

이 축의 "유효성"은 Wine Quality 데이터셋 계열로 근거 확보 가능하나, 상용 서비스에서는 실제 병입/로트별 수급 전략이 필요함.

8-6. 즉시 결론(실행 우선순위)

지금 당장 "근거가 가장 강하고, 데이터 확보가 쉬운" 순서:

WineSensed 멀티모달 IR(텍스트/이미지/메타 + flavor distance 실험)

리뷰 텍스트 IR(RecSys 2013 축 정렬)

Graph(Producer/Region 연결)로 하이엔드 희소성 해결(PinSage 운영 근거)

Physicochemical은 "효과 근거는 강함"이나, WineSensed에 없으므로 상용 Raw 수급 설계가 선행되어야 함

9. 스키마 보완(최소 추가안, Master 오염 방지)

9-1. Raw(SSOT 외부, 수급 레이어)

wine_techsheet_raw_v1: pH/TA/RS/SO2/blend_ratio/oak_months 등(권리/출처 포함)

vineyard_climate_raw_v1: region_geo + day/month aggregation(GDD/강수/일교차 등)

critic_profile_raw_v1: critic_id + 평균 점수/커버 지역/연도별 편향(가능 범위)

9-2. Derived(IR)

wine_temporal_ir_v1: drinking window stage + confidence + version

wine_terroir_ir_v1: climate/soil fingerprint embedding + version

review_authority_ir_v1: W_auth + controversy index + version

wine_multimodal_joint_ir_v1: text/image/meta fusion embedding + version

10. 하이엔드 특화 보완 사항

10-1. 보관 상태 및 이력(Provenance) 데이터 확충

하이엔드 와인은 제품 그 자체만큼이나 "어떻게 관리되었는가"가 가치와 맛을 결정합니다.

wine_condition_ir_v1 (신규):

storage_history: 전문 셀러 보관 여부, 엑스-샤토(Ex-Chateau) 여부 등.

ullage_level: 액면 높이(하이엔드 올드 빈티지의 핵심 지표).

label_condition: 라벨 파손 상태(이미지 IR과 연동).

보완 이유: 똑같은 wine_sku_id라도 보관 상태에 따라 추천 우선순위와 음용 적기(drink_to_year)가 완전히 달라지기 때문입니다.

10-2. 감각 데이터의 계층화: '아로마 휠' 온톨로지 고도화

현재 taste_tags는 단순 어레이 형태입니다. 전문가의 복합적인 표현을 정교하게 학습하려면 계층형 온톨로지 구조가 IR에 명시되어야 합니다.

review_taste_tag_ir_v1 확장:

aroma_category: Primary(과실/꽃), Secondary(양조/오크), Tertiary(숙성/부케)로 구분.

intensity_score: 특정 향의 강도(0~1).

evolution_stage: 해당 리뷰가 와인의 어느 숙성 단계에서 작성되었는지 기록.

보완 이유: 하이엔드 유저는 "단순히 과일향이 나는 와인"이 아니라 "3차 숙성향(Tertiary aromas)이 발달하기 시작한 와인"을 찾기 때문입니다.

10-3. 시장 유동성 및 희소성 데이터의 동적 반영

wine_scarcity_ir_v1에서 '시장 범위'에 따른 희소성을 정의한 점은 훌륭합니다. 여기에 유동성(Liquidity) 개념을 추가하면 '투자 가치' 기반 추천이 가능해집니다.

wine_market_ir_v1 (신규/확장):

secondary_market_volume: 경매 및 2차 시장 거래 빈도.

global_search_trend: 와인 서처(Wine-Searcher) 등에서의 검색 트렌드.

liquidity_score: 재판매 용이성.

보완 이유: 하이엔드 와인 추천은 단순 소비를 넘어 '자산'으로서의 가치를 포함하는 경우가 많습니다.

10-4. 데이터 리니지 및 갈등 관리 (Consensus Engine)

전문가들 사이에서도 시음 적기나 평점은 갈릴 수 있습니다. IR 레이어에서 이를 '합의'하는 로직이 데이터 필드로 존재해야 합니다.

wine_review_aggregate_ir_v1 보완:

critic_consensus_score: 전문가들 간 의견 일치도(분산의 역수).

discrepancy_note: 특정 권위자가 유독 낮게/높게 평가한 경우의 플래그.

보완 이유: 의견이 갈리는 와인은 유저에게 '모험적 추천'이 될 수 있고, 일치하는 와인은 '안전한 추천'이 됩니다. 이를 랭킹 모델의 confidence로 활용할 수 있습니다.

10-5. 보완된 데이터 구조 예시 (Diff)

IR 테이블	추가/변경 필드	설명
wine_temporal_ir	storage_correction_factor	보관 상태에 따른 음용 적기 보정 계수
wine_scarcity_ir	market_scope_liquidity	특정 국가/시장 내 재판매 유동성 지수
review_text_ir	sensory_layer_tags	아로마 휠 계층(1차/2차/3차) 매핑 결과
wine_review_agg	language_centroid_refs	언어별 리뷰 중심점 분리 관리 (글로벌 대응)

11. Conclusion

본 RFC는

전제 정리 및 팩트 정정

학계·업계 SOTA 근거 기반 Feature 축 재정의

데이터셋 선택 기준 및 확장 전략

IR 매핑 표준

벤치 시나리오

권리/재현성 가이드

Raw/Derived 강화 로드맵

스키마 보완 및 하이엔드 특화 보완

를 고정하여,
하이엔드 와인 추천을 근거 기반·재현 가능·확장 가능한 체계로 운영하기 위한 기준선임.
