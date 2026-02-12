RFC-REC-EXT-004

Title: High-End Wine Recommendation — SSOT/IR 확장 및 Graph·Temporal·Expert-Aware 설계
Status: Draft v1.0
Scope: Wine Master/IR v1 확장, Review IR 강화, 후보생성·랭킹 고도화, 하이엔드 도메인 특화 신호 통합
Base RFCs: Wine Master/IR v1, Review Master/IR v1, 2-Stage RS, LightGCN, BPR, Wide&Deep/DeepFM/DLRM

1. Executive Summary

1-1. 목표
하이엔드 와인 추천에 맞춰 기존 SSOT/IR 분리 설계를 유지하면서 아래 4축을 추가 강화함

Expert-aware Review Modeling

Temporal Value Modeling(Drinking Window)

Heterogeneous Wine Graph

Multi-objective Ranking(Price·Scarcity 포함)

1-2. 핵심 원칙

Master = 정체성·권리·리니지 SSOT

IR = 전적으로 파생·버전드·재생성 가능 계층

모든 고도화는 IR 및 모델 레이어에서 처리, Master 오염 금지

2. Domain-Specific Extensions
2-1. Expert-Aware Review Modeling
2-1-1. 문제

하이엔드 시장에서 리뷰는 동등하지 않음

Critic 95점 vs 일반 유저 5점은 정보 가치 비대칭

2-1-2. 설계

(1) Author Authority Weight
review_master_v1.author_type 기반 가중치 체계 도입

예시

critic: 3.0

expert: 2.0

user: 1.0

anonymous: 0.5

이 값은 SSOT가 아닌 ranking-time weight config로 관리

(2) Aggregate IR 반영
wine_review_aggregate_ir_v1 생성 시:

weighted_rating_mean

weighted_taste_tag_distribution

authority_weighted_centroid_embedding

authority_weighted_count: 권위자 리뷰 수 집계

critic_consensus_score: 전문가들 간 의견 일치도(분산의 역수)

discrepancy_note: 특정 권위자가 유독 낮게/높게 평가한 경우의 플래그

language_centroid_refs: 언어별 리뷰 중심점 분리 관리(글로벌 대응, ko/en 등)

추가

보완 이유: 의견이 갈리는 와인은 유저에게 '모험적 추천'이 될 수 있고, 일치하는 와인은 '안전한 추천'이 됩니다. 이를 랭킹 모델의 confidence로 활용할 수 있습니다.

2-1-3. Wine Ontology Tagger

review_taste_tag_ir_v1 확장:

필드	설명
ontology_version	와인 온톨로지 버전
tag_source	generic / wine_ontology
expertise_level	basic / advanced / sommelier
aroma_category	string	Primary(과실/꽃), Secondary(양조/오크), Tertiary(숙성/부케)
intensity_score	float	특정 향의 강도(0~1)
evolution_stage	string	해당 리뷰가 와인의 어느 숙성 단계에서 작성되었는지 기록
sensory_layer_tags	json	아로마 휠 계층(1차/2차/3차) 매핑 결과

전문가 어휘(tertiary aromas, minerality, petrichor 등)를 1급 신호로 취급

하이엔드 유저는 "단순히 과일향이 나는 와인"이 아니라 "3차 숙성향(Tertiary aromas)이 발달하기 시작한 와인"을 찾기 때문에 계층형 온톨로지 구조가 필수임.

2-2. Temporal Wine Modeling
2-2-1. 문제

와인은 시간에 따라 품질·스타일이 변화함
→ “지금 마시기 좋은가”는 추천 품질의 핵심

2-2-2. 신규 IR

wine_temporal_ir_v1

필드	설명
wine_core_id	FK
vintage_year	빈티지
drink_from_year	권장 시작
drink_to_year	권장 종료
current_stage	too_young / early / peak / past
estimation_method	rule/model/expert
temporal_version	규칙 버전
as_of_ts	timestamp	평가 시점(관측 시점 고정)
observation_window	string	관측 기간(예: "2024-01-01 to 2024-12-31")
storage_correction_factor	float	보관 상태에 따른 음용 적기 보정 계수(0~1)
confidence	float	신뢰도 점수(0~1)

2-2-3. 활용

Candidate filtering: past는 기본 감점

Ranking feature: peak proximity score

Explanation: “현재 최적 음용 시기”

2-3. Multimodal Wine Representation
2-3-1. 목적

라벨 기반 탐색, 분위기 기반 추천 지원

2-3-2. 신규 IR

wine_image_ir_v1

필드	설명
wine_core_id	FK
label_embedding_ref	벡터 키
embedding_model	모델
style_tags	classic/minimal/luxury 등
image_version	버전
2-3-3. Joint Embedding

text_embedding ⊕ image_embedding

late fusion 또는 projection head 기반 joint space

Query:

label image + “rich bordeaux style”

분위기 기반 탐색 가능

3. Graph of Wine (Heterogeneous Graph)
3-1. 노드 타입

User

Wine_Core

Producer

Region

Variety

Sommelier_Tag

3-2. 엣지 타입

PURCHASED

REVIEWED

PRODUCED_BY

LOCATED_IN

HAS_VARIETY

TAGGED_AS

3-3. 효과

Sparse high-end 와인 cold-start 완화

Producer/Region 기반 embedding propagation

Terroir 기반 유사도 반영

3-3-1. Terroir를 잠재 변수로 모델링 (연구 난제 포지션)

단순 Region/Variety feature를 넘어, terroir를 **latent factor**로 모델링한다.

- **latent terroir factor**: 지역(Region) + 토양(Soil) + 기후(Climate)를 잠재 공간으로 학습
  - 관측 가능한 변수: GDD, 강수량, 일교차, 토양 pH, 배수 등급
  - 잠재 변수: 이들의 조합이 만드는 "terroir 시그니처"
- **vintage-condition interaction**: 동일 terroir에서도 빈티지별 기후 편차에 따라 와인 성격이 달라짐
  - 모델 입력: terroir_factor × vintage_climate_deviation
  - 이 interaction은 "올해 이 지역 와인은 평년보다 더 산미가 높다" 같은 추론을 가능하게 함
- **위치**: IR 레이어(wine_terroir_ir_v1)에서 관리. Master 오염 금지.

이것은 와인 도메인에서 진짜 연구 난제 포지션이 가능한 축이다.
(연결: RFC-DATASET-BENCH-005 §4-5 테루아·기후 축, RFC-SOTA-ROADMAP-012 §4-2)

3-4. IR 정의

wine_hetero_graph_ir_v1

필드	설명
node_id	노드
node_type	타입
neighbor_ids	이웃
edge_types	엣지 타입
weights	가중치
graph_version	버전

LightGCN 또는 R-GCN 계열 모델 소비 전용

4. Price & Scarcity Modeling
4-1. Price IR 확장

wine_attr_ir_v1 확장:

필드	설명
median_price_by_market	중앙값
price_volatility	변동성
price_trend	up/down/stable

Explainability:
“최근 가격 상승 중인 와인”

4-2. Scarcity IR

wine_scarcity_ir_v1

필드	설명
wine_core_id	FK
production_volume_est	추정 생산량
allocation_score	할당 난이도
rarity_score	희소성 점수
scarcity_version	버전
market_scope	string	희소성 의미는 시장별로 달라짐(예: "KR", "US", "global")
availability_proxy	float	노출 가능성 근사(0~1)
market_scope_liquidity	float	특정 국가/시장 내 재판매 유동성 지수

4-3. Market & Liquidity IR (하이엔드 특화)

wine_market_ir_v1 (신규)

필드	설명
wine_core_id	FK
secondary_market_volume	int	경매 및 2차 시장 거래 빈도
global_search_trend	float	와인 서처(Wine-Searcher) 등에서의 검색 트렌드
liquidity_score	float	재판매 용이성(0~1)
market_version	버전

보완 이유: 하이엔드 와인 추천은 단순 소비를 넘어 '자산'으로서의 가치를 포함하는 경우가 많습니다.
5. Ranking Objective 고도화
5-1. Multi-Task Learning

기본:

L = L_BPR
 + λ1 L_price_satisfaction
 + λ2 L_scarcity_preference
 + λ3 L_authority_alignment

5-2. 직관

좋아할 확률

가격 대비 만족

희소성 선호

전문가 취향 일치

동시 최적화

5-3. Uncertainty-aware Recommendation (하이엔드 특화)

하이엔드 와인은 정보가 불완전한 경우가 많다(희소 리뷰, 새 빈티지, 소생산자).
이때 모델의 **confidence/uncertainty를 추천에 활용**한다.

- **모델 출력에 confidence score 추가**: 예측 신뢰도를 0~1로 출력
- **high-variance 와인 = "모험적 추천"**: uncertainty가 높은 와인은 유저에게 "탐험적 선택"으로 포지셔닝
  - 이미 discrepancy_note(전문가 의견 갈림)가 있으므로, 이것과 model uncertainty를 결합
- **low-variance 와인 = "안전한 추천"**: uncertainty가 낮은 와인은 "확실한 선택"으로 포지셔닝
- **유저 노출 설계**:
  - confidence score를 설명 payload에 포함 (Phase 3+)
  - "이 추천은 [확신도 높음/모험적 선택]" 형태로 UX 반영
  - discovery 엔진 포지셔닝과 자연스럽게 결합됨

(연결: RFC-SOTA-ROADMAP-012 §4-3 Uncertainty-aware recommendation)

6. Cold-Start 대응 전략
6-1. Item Cold-Start

우선 신호 순서:

Text IR embedding

Image IR embedding

Producer/Region Graph

Variety similarity

6-2. User Cold-Start

onboarding preference quiz

taste tag 선택

price sensitivity 입력

→ pseudo-profile 생성

7. Governance & Versioning
7-1. 필수 원칙

모든 IR은 versioned

재생성 가능해야 함

Master에는 모델 산출물 저장 금지

7-2. Merge/Split 이벤트

wine_core_identity_event_v1

필드	설명
event_type	merge/split
source_ids	이전 ID
target_ids	이후 ID
decision_version	규칙 버전
ts	시각
8. 하이엔드 특화 보완 사항

8-1. 보관 상태 및 이력(Provenance) 데이터 확충

하이엔드 와인은 제품 그 자체만큼이나 "어떻게 관리되었는가"가 가치와 맛을 결정합니다.

wine_condition_ir_v1 (신규):

필드	설명
wine_core_id	FK
wine_sku_id	FK (특정 SKU의 보관 상태)
storage_history	string	전문 셀러 보관 여부, 엑스-샤토(Ex-Chateau) 여부 등
ullage_level	string	액면 높이(하이엔드 올드 빈티지의 핵심 지표)
label_condition	string	라벨 파손 상태(이미지 IR과 연동)
provenance_score	float	출처 신뢰도 점수(0~1)
condition_version	버전

보완 이유: 똑같은 wine_sku_id라도 보관 상태에 따라 추천 우선순위와 음용 적기(drink_to_year)가 완전히 달라지기 때문입니다.

wine_temporal_ir_v1의 storage_correction_factor와 연동하여 보관 상태에 따른 음용 적기 보정을 수행함.

8-2. 가격 편향 완화 전략

가격은 "선호 신호"이면서 동시에 "노출/유통/재고/희소성"의 결과임.

고가/희소 와인은 관측 편향(노출, 구입 기회)이 강함 → price/rarity를 단순 feature로만 쓰면 모델이 편향을 학습할 수 있음.

해결: scarcity/availability를 별도 IR로 분리하고, 평가 태스크에서도 "기회가 있었던 후보셋"을 고정하는 프로토콜이 필요함.

8-3. 언어 혼재 처리

와인 리뷰는 "어휘가 계층적이고 전문용어가 정보량을 운반"함.

언어 혼재(ko/en)에서 의미 보존이 중요하므로 language별 정규화/임베딩을 허용하고, aggregate에서 언어별 centroid를 병렬 관리하는 것이 실전에서 더 안전함(하이엔드 리뷰는 번역 품질이 성능을 흔들 수 있음).

9. Non-Goals

실시간 동적 가격 예측

투자/경매 전용 valuation 모델

재고 최적화

(별도 RFC 영역)

10. Rollout Plan (High-Level)

Phase 1

Expert weighting

Temporal IR

Price/Scarcity IR

Phase 2

Heterogeneous graph

Multimodal IR

Phase 3

MTL ranking

Joint embedding

Uncertainty-aware recommendation (confidence score 도입)

Phase 4 (하이엔드 특화)

보관 상태 IR (wine_condition_ir_v1)

시장 유동성 IR (wine_market_ir_v1)

아로마 휠 계층화 완성

합의 엔진 (consensus scoring)

Latent terroir factor 모델링 (vintage-condition interaction)

11. Conclusion

본 RFC는 기존 Wine Master/IR v1을 훼손하지 않고:

하이엔드 도메인 특화 신호

멀티모달 확장성

그래프 기반 SOTA 추천

Future-proof IR 구조

를 추가하는 확장 RFC임.

결과적으로
“데이터 구조는 안정, 모델은 자유롭게 진화”하는 구조를 유지함.
