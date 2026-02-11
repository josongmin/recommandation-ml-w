RFC-SSOT-IR-001

Title: 하이엔드 와인 추천 — Wine Master/IR v1 + Review Master/IR v1 (SSOT/파생 계층 확정)
Status: Draft v1.0
Scope: 추천 시스템의 장기 확장성을 위해 “정체성/권리/조인키”는 Master(SSOT), “학습/검색/랭킹 표현층”은 IR(파생, 버전드)로 분리한다.

1. 근거로 채택할 “공신력 축” 정리
1-1. 추천 시스템 구조 근거(업계 표준 + 학계 인용 최상위)

2-Stage(후보 생성/랭킹) 분리 아키텍처: YouTube 추천 시스템 논문이 대표 산업 레퍼런스로 정식화함

implicit feedback를 신뢰도(confidence)로 모델링: Hu/Koren/Volinsky가 대표 정석 베이스라인을 제시함

implicit에서의 ranking 목적함수: BPR(UAI 2009)가 표준 기준점 역할임

그래프 기반 CF SOTA: LightGCN이 추천용 GCN 단순화로 강한 SOTA 기준점임

랭킹에서 sparse feature 처리: Wide&Deep, DeepFM, DLRM 계열이 산업/학계 표준 레퍼런스임

리뷰 텍스트를 추천 신호로 결합: McAuley & Leskovec(RecSys 2013)가 “rating+review text 결합”의 대표 근거임

1-2. 와인 도메인 데이터셋 근거(와인 특화, 연구용/벤치용)

X-Wines(2023): 와인 추천 실험을 위한 대규모 와인 데이터셋 제시

WineSensed(NeurIPS 2023 D&B): 라벨 이미지+리뷰 텍스트+메타+인간 감각 유사도(부분)까지 포함하는 멀티모달 와인 데이터셋

Context-aware RS(Adomavicius & Tuzhilin): 컨텍스트를 추천에 반영하는 정리/레퍼런스

2. 확정 목표: “와인마스터 + 와인 IR”, “리뷰마스터 + 리뷰 IR”
2-1. 설계 원칙(확장성)

Master는 SSOT(정체성/출처/버전/권리/조인키)만 담음

IR은 학습/검색/랭킹을 위한 표현층이며, 버전드 파생물로 관리함

Raw 원문 보존 가능 여부는 license/rights로 분리하여 추적함

2-2. 엔티티 분리(핵심)

wine_core_id: 취향 학습의 안정 단위

wine_sku_id: 판매/재고/가격/국가별 변형 단위

이 분리는 2-Stage 추천에서 “ID가 변하면 모델/로그/인덱스가 무너짐” 문제를 구조적으로 차단하는 장치임

3. Wine Master v1 (SSOT)
3-1. wine_core_master_v1 (정체성 고정)
필드	타입	설명
wine_core_id	string(ULID/UUID)	내부 SSOT 키
producer_id	string	생산자 SSOT
wine_name_canonical	string	정규화된 와인명
region_path_ids	array<string>	국가/지역/서브지역 계층
primary_variety_ids	array<string>	주 품종(복수)
style_tags	array<string>	red/white/sparkling/fortified 등
aliases_canonical	array<string>	검색/매핑용 별칭(정규화)
created_at	ts	생성 시각
updated_at	ts	갱신 시각

3-2. wine_sku_master_v1 (판매 변형)
필드	타입	설명
wine_sku_id	string	내부 SSOT 키
wine_core_id	string	FK
vintage_year	int nullable	빈티지
bottle_size_ml	int	750 등
package_type	enum	bottle/box/giftset
market	string(ISO)	KR/US 등
importer_id	string nullable	수입사/유통사
barcode_list	array<string> nullable	GTIN/EAN
created_at	ts	생성
updated_at	ts	갱신

3-3. wine_source_link_v1 (외부 소스 결합 키)
필드	타입	설명
source_system	enum	vivino/partner/media/dataset 등
source_item_key	string	원천 ID(예: dataset wine_id)
target_kind	enum	core/sku
wine_core_id	string nullable	매핑 결과
wine_sku_id	string nullable	매핑 결과
mapping_confidence	float	0~1
mapping_method	enum	exact/barcode/fuzzy/manual
ingested_at	ts	수집

근거 포인트

X-Wines/WineSensed처럼 “외부 데이터셋 키”가 들어오는 경우를 공식 지원해야 데이터 확장이 쉬움

4. Wine IR v1 (추천/학습/검색 표현층)
4-1. wine_attr_ir_v1 (구조화 IR, 랭킹용)
필드	타입	설명
wine_core_id	string	FK
abv	float nullable	알코올
sweetness	float nullable	0~1 정규화
acidity	float nullable	0~1
tannin	float nullable	0~1
body	float nullable	0~1
oak	float nullable	0~1 또는 tag
price_band_by_market	map<market,band>	가격대 버킷
feature_version	string	IR 버전

근거 포인트

Wide&Deep/DeepFM/DLRM 같은 랭킹 모델은 sparse+dense feature를 정형 입력으로 받는 구조가 표준임

4-2. wine_text_ir_v1 (텍스트 IR, cold-start/유사도/후보생성)
필드	타입	설명
wine_core_id	string	FK
text_corpus	json	expert_note/user_reviews/product_desc 분리
language_mix	array<string>	ko/en 등
clean_version	string	정규화 규칙 버전
embedding_model	string	임베딩 모델명
embedding_ref	string	벡터 스토어 키
embedding_dim	int	차원
embedding_ts	ts	생성 시각

근거 포인트

리뷰 텍스트를 latent factor와 결합하면 예측 성능 및 해석 가능성이 개선된다는 대표 근거가 존재함

WineSensed는 “텍스트/이미지/메타를 함께” 학습/표현하는 연구 축을 제공함

4-3. wine_graph_ir_v1 (그래프 IR, 상호작용 누적 후 SOTA)
필드	타입	설명
wine_core_id	string	노드
neighbor_core_ids	array<string>	유사 와인
edge_weights	array<float>	가중치
graph_version	string	생성 규칙 버전

근거 포인트

user–item 그래프 기반 embedding propagation이 강한 성능을 내는 표준 축임

5. Review Master v1 (SSOT)
5-1. review_master_v1 (원문/출처/권리/대상 고정)
필드	타입	설명
review_id	string(ULID)	내부 SSOT
source_system	enum	first_party/partner/dataset/media
source_review_key	string nullable	원천 ID
author_type	enum	user/expert/critic/anonymous
author_key	string nullable	가능 시
created_at	ts nullable	원문 작성 시각
ingested_at	ts	수집 시각
language	string(BCP-47)	ko/en 등
market	string(ISO)	KR/US 등
target_kind	enum	sku/core
wine_core_id	string nullable	매핑 결과
wine_sku_id	string nullable	매핑 결과
mapping_confidence	float	0~1
mapping_method	enum	exact/barcode/fuzzy/manual
rating_value	float nullable	평점
rating_scale	enum	5star/100pt/10pt/none
title_raw	string nullable	원문
body_raw	string	원문
rights_store_raw	bool	원문 저장 허용
rights_display	bool	화면 노출 허용
license_tag	string	라이선스 추적

근거 포인트

리뷰 텍스트는 추천에 유효한 신호이므로 “원문 보존 + 파생물 분리”가 장기적으로 안전함

6. Review IR v1 (추가 IR: 정규화/임베딩/태그/집계)
6-1. review_text_ir_v1 (학습 입력용 정규화 텍스트)
필드	타입	설명
review_id	string	FK
body_clean	string	정규화 텍스트
clean_version	string	규칙 버전
token_count	int	길이
pii_redacted	bool	PII 제거 여부

6-2. review_embedding_ir_v1 (리뷰 임베딩)
필드	타입	설명
review_id	string	FK
embedding_model	string	모델
embedding_ref	string	벡터 키
embedding_dim	int	차원
embedding_ts	ts	생성

6-3. review_taste_tag_ir_v1 (감각/구조 태그)
필드	타입	설명
review_id	string	FK
taste_tags	array<string>	cherry, vanilla 등
structure_scores	json	body/acidity/tannin/sweetness 0~1
tagger_version	string	추출 규칙/모델 버전

6-4. wine_review_aggregate_ir_v1 (아이템 집계 IR, 추천에 가장 실용적)
필드	타입	설명
wine_core_id	string	FK
review_count_total	int	총 수
rating_mean	float nullable	평균
rating_var	float nullable	분산(논쟁성)
top_taste_tags	array<{tag,weight}>	대표 태그
centroid_embedding_ref	string	리뷰 임베딩 중심
last_review_at	ts	최신

근거 포인트

후보 생성/랭킹 분리 체계에서는 “아이템 대표 벡터/대표 피처”가 운영적으로 안정적임

리뷰 신호를 latent factor와 결합하는 계열 연구들이 “리뷰를 집계/토픽화해 신호를 안정화”하는 방향을 취함

7. “이 IR에 맞춰 리뷰를 콜렉팅/재편집” 실행 규칙 v1
7-1. 수집 우선순위(확장성 관점)

first_party 리뷰(권리/표시/학습 모두 안정)

파트너/미디어(계약 기반, rights 필드로 통제)

공개 데이터셋(초기 부트스트랩/연구 검증용, X-Wines/WineSensed)

7-2. 재편집 원칙

body_raw는 절대 overwrite 금지, clean/요약/번역은 IR로만 생성

중복은 duplicate_group_id로 묶고 대표 원문 1개를 SSOT로 지정(파생물은 링크)

언어 혼재는 language를 명시하고, language별 임베딩 생성 허용

7-3. 매핑 정책(와인 엔티티 결합)

barcode/sku 명시 > producer+exact name+vintage > producer+name(core) > fuzzy+region/variety > manual

매핑 실패는 허용하되 candidate list를 남기고 후행 backfill 경로를 보장함

하이엔드 와인추천을 위한 데이터셋 정리중임. 의견있나

