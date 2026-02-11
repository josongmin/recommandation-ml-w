RFC-TRAINING-DATA-015

Title: High-End Wine Recommendation — SOTA-Grade Training Data Preparation v1
Status: Draft v1.0
Scope: 학습 데이터 규모/품질/다양성/편향 제거를 SOTA급으로 끌어올리기 위한 데이터 준비 전략, 증강 기법, 품질 게이트, 실험 환경 구축 가이드
Depends On:
- RFC-DATASET-BENCH-005: 벤치/평가/재현 프로토콜
- RFC-DATASET-BUILDER-011: impression 기반 학습 데이터 생성
- RFC-FEATURE-MANIFEST-010: parity gate
- RFC-LOG-SCHEMA-009: 이벤트 로그 스키마
- RFC-SOTA-ROADMAP-012: 3년 연구-제품 통합 플랜

1. Executive Summary

1-1. 문제 정의
현재 seed data(와인 120종, 사용자 200명, impression 2000건)는 **프로토타입 검증용**이지, SOTA급 모델 학습용이 아님.

진짜 SOTA 실험 환경은:
- **규모**: 최소 수십만~수백만 상호작용
- **품질**: 노이즈/편향/누설 제거된 clean signal
- **다양성**: 희소/고가/신규 아이템 충분히 포함
- **재현성**: 고정 split + seed + 버전 관리
- **평가 혹독함**: counterfactual + long-horizon + domain-specific 태스크

1-2. 목표
본 RFC는 "어떻게 데이터를 준비해야 SOTA급 실험이 가능한가"를 고정함:
1. **데이터 규모 기준선**: 도메인별 최소 요구사항
2. **데이터 품질 게이트**: 편향/누설/노이즈 제거 프로토콜
3. **증강 전략**: 부족한 신호를 보완하는 합성/전이 학습
4. **실험 환경 설계**: 재현 가능한 벤치 + 혹독한 평가

2. SOTA급 데이터 준비의 5대 원칙

2-1. 원칙 1: Scale Matters (규모가 곧 성능)
**최소 규모 기준선** (RecSys 논문 기준):
- User: 10K+ (cold-start 평가용 1K+ 별도)
- Item: 10K+ (희소 아이템 1K+ 별도)
- Interaction: 100K+ (평가용 10K+ 별도)
- 하이엔드 특화: 고가(상위 10%) 아이템 1K+, 희소(노출 < 100) 아이템 500+

**현재 gap**:
- 와인 120종 → 10K+ 필요 (83배 부족)
- 사용자 200명 → 10K+ 필요 (50배 부족)
- impression 2000건 → 100K+ 필요 (50배 부족)

2-2. 원칙 2: Quality > Quantity (노이즈는 독)
**품질 게이트 필수 항목**:
1. **Temporal leakage 제거**: train < val < test 시간순 엄격 보장
2. **Position bias 제거**: 노출 위치에 따른 클릭 편향 보정
3. **Selection bias 제거**: 노출 기회가 있었던 후보만 평가
4. **Duplicate 제거**: 동일 user-item 중복 상호작용 정리
5. **Bot/Spam 필터링**: 비정상 패턴 제거

**현재 상태**:
- ✓ Temporal leakage gate 있음
- ✗ Position bias 보정 없음
- ✓ Selection bias (candidate_budget) 개념 있음
- ✗ Duplicate/Bot 필터링 없음 (seed data라 불필요)

2-3. 원칙 3: Diversity is Key (편향 제거)
**다양성 체크리스트**:
- Long-tail coverage: 노출 < 100 아이템이 전체의 30%+
- Price diversity: 가격 분포가 실제 시장 반영 (로그정규분포)
- Geographic diversity: 주요 산지 균형 (프랑스/이탈리아/미국/칠레/호주 등)
- Temporal diversity: 빈티지 분포 (2015~2024 고르게)
- User diversity: 신규/활성/휴면 사용자 균형

**현재 gap**:
- Long-tail: seed data는 인위적으로 균등 분포
- Price: 로그정규 분포로 생성됨 (✓)
- Geographic: 주요 산지 포함됨 (✓)
- Temporal: 빈티지 랜덤 (✓)
- User: 활동 패턴 단순 (개선 필요)

2-4. 원칙 4: Hard Negatives (쉬운 문제는 의미 없음)
**Negative sampling 전략**:
1. **Random negative**: 기본 (현재 구현됨)
2. **Hard negative**: 비슷하지만 선택 안 된 아이템
   - 같은 producer/region/variety but 다른 vintage
   - 같은 가격대 but 다른 스타일
3. **In-batch negative**: 같은 배치 내 다른 유저의 positive
4. **Popularity-aware negative**: 인기도 보정 샘플링

**현재 상태**:
- ✓ shown_but_no_action (노출됐지만 클릭 안 됨)
- ✗ Hard negative 없음
- ✗ In-batch negative 없음
- ✗ Popularity-aware 없음

2-5. 원칙 5: Reproducibility is Non-Negotiable (재현 필수)
**재현성 체크리스트**:
- ✓ Split seed 고정
- ✓ Negative sampling seed 고정
- ✓ Dataset manifest 생성
- ✓ Feature schema version
- ✓ Time-travel join 보장
- ✗ Propensity 추정 (counterfactual 평가용)
- ✗ Candidate budget spec (노출 기회 고정)

3. 데이터 규모 확장 전략

3-1. Phase 0: Seed Data (현재)
**목적**: 파이프라인 검증, 프로토타입
**규모**:
- 와인: 120종
- 사용자: 200명
- Impression: 2K
- Action: 1.4K
- Order: 165

**한계**: 모델 성능 평가 불가, 과적합 심각

3-2. Phase 1: Synthetic Scale-Up (합성 확장)
**목적**: 파이프라인 부하 테스트, 초기 모델 학습
**방법**:
1. **와인 확장** (120 → 10K):
   - 기존 120종을 template으로 사용
   - Producer/Region/Variety 조합 확장
   - Vintage variation (2010~2024)
   - 실제 분포 반영 (Zipf's law for popularity)

2. **사용자 확장** (200 → 10K):
   - 취향 프로필 클러스터링 (5~10 페르소나)
   - 페르소나별 행동 패턴 정의
   - 활동 빈도 분포 (파레토: 20%가 80% 활동)

3. **상호작용 확장** (2K → 100K):
   - User-wine affinity matrix 기반 생성
   - Temporal pattern 반영 (주말/저녁 집중)
   - Conversion funnel 반영 (impression → click → order)

**생성 규칙**:
```python
# 와인 생성
for producer in PRODUCERS:
    for region in producer.regions:
        for variety in region.varieties:
            for vintage in range(2010, 2025):
                create_wine_core(producer, region, variety, vintage)
                # 평균 2개 SKU per core
                create_skus(wine_core, merchants=[...])

# 사용자 생성 (페르소나 기반)
PERSONAS = {
    "collector": {"price_range": (100K, 500K), "freq": "monthly"},
    "enthusiast": {"price_range": (50K, 200K), "freq": "weekly"},
    "casual": {"price_range": (20K, 100K), "freq": "quarterly"},
    "gift_buyer": {"price_range": (50K, 150K), "freq": "seasonal"},
    "investor": {"price_range": (200K, 1M), "freq": "rare"},
}

for persona, config in PERSONAS.items():
    n_users = int(10000 * persona_distribution[persona])
    for i in range(n_users):
        create_user(persona, config)

# 상호작용 생성 (affinity 기반)
for user in users:
    affinity = compute_affinity(user, wines)  # 취향 매칭
    n_sessions = sample_session_count(user.persona)
    for session in range(n_sessions):
        candidates = sample_candidates(wines, affinity, k=10)
        create_impression(user, candidates)
        # 클릭 확률 = affinity * position_bias
        for wine in candidates:
            if random() < click_prob(affinity[wine], position):
                create_action(user, wine, "CLICK")
                if random() < conversion_rate(user.persona):
                    create_order(user, wine)
```

**품질 보장**:
- 실제 분포 통계 매칭 (KL divergence < 0.1)
- 시간 패턴 검증 (주중/주말, 시간대)
- 전환율 검증 (impression → click: 20%, click → order: 8%)

3-3. Phase 2: Real Data Integration (실제 데이터)
**목적**: 실전 성능 검증, 프로덕션 준비
**소스**:
1. **공개 데이터셋**:
   - WineSensed (897K 이미지, 824K 리뷰)
   - X-Wines (user-item interaction)
   - Wine Reviews 130K (전문가 리뷰)

2. **크롤링/수집**:
   - Vivino/Wine-Searcher (가격/평점)
   - Wine Enthusiast/Decanter (전문가 리뷰)
   - 경매 데이터 (Christie's, Sotheby's)

3. **파트너십**:
   - 와인 수입사 (재고/가격/스펙)
   - 소믈리에 패널 (전문가 라벨링)
   - 셀러 서비스 (보관 이력)

**통합 프로토콜**:
```python
# IR 매핑 표준 (RFC-DATASET-BENCH-005)
wine_core_master_v1:
    wine_core_id: str  # 내부 ID
    source_system: str  # "winesensed" | "vivino" | "manual"
    source_item_key: str  # 외부 ID
    canonical_name: str
    producer: str
    region: str
    variety: list[str]
    license_tag: str  # "research_only" | "commercial_ok"
    rights_store_raw: bool
    rights_display: bool
    mapping_confidence: float  # 0~1

# 중복 제거
dedup_strategy:
    - canonical_name fuzzy match (threshold=0.9)
    - producer + region + variety + vintage exact match
    - manual review for confidence < 0.8
```

3-4. Phase 3: Continuous Data Pipeline (지속 수집)
**목적**: 모델 drift 방지, 최신 트렌드 반영
**구성**:
1. **실시간 로그 수집**:
   - Impression/Action/Order 로그 (Kinesis)
   - Policy 로그 (propensity 추정용)
   - Feature 로그 (parity gate용)

2. **주기적 재학습**:
   - 일별: 증분 업데이트 (new impressions)
   - 주별: 전체 재학습 (drift 체크)
   - 월별: 데이터셋 버전 bump (manifest 갱신)

3. **품질 모니터링**:
   - Distribution shift 감지 (KL divergence)
   - Label drift 감지 (CTR/CVR 변화)
   - Propensity drift 감지 (탐험 정책 변화)

4. 데이터 품질 게이트 (Quality Gates)

4-1. Gate 1: Temporal Leakage (누설 방지)
**목적**: train/val/test 시간순 엄격 보장
**체크**:
```python
def check_temporal_leakage(df: pl.DataFrame) -> GateResult:
    splits = df.group_by("split").agg(
        pl.col("shown_ts").max().alias("max_ts"),
        pl.col("shown_ts").min().alias("min_ts"),
    )
    
    # train < val < test 검증
    train_max = splits.filter(pl.col("split") == "train")["max_ts"][0]
    val_min = splits.filter(pl.col("split") == "val")["min_ts"][0]
    val_max = splits.filter(pl.col("split") == "val")["max_ts"][0]
    test_min = splits.filter(pl.col("split") == "test")["min_ts"][0]
    
    violation = (train_max >= val_min) or (val_max >= test_min)
    
    return GateResult(
        gate_name="temporal_leakage",
        passed=not violation,
        metric_value=1.0 if violation else 0.0,
        threshold=0.0,
    )
```

**현재 상태**: ✓ 구현됨 (dataset_builder.py)

4-2. Gate 2: Label Distribution (라벨 균형)
**목적**: 극단적 불균형 방지
**체크**:
```python
def check_label_distribution(df: pl.DataFrame) -> GateResult:
    positive_rate = (df["label"] > 0).mean()
    
    # 하이엔드 도메인: 5~30% positive가 적정
    passed = 0.05 <= positive_rate <= 0.30
    
    return GateResult(
        gate_name="label_distribution",
        passed=passed,
        metric_value=positive_rate,
        threshold=(0.05, 0.30),
    )
```

**현재 상태**: 19% positive (✓ 적정 범위)

4-3. Gate 3: Coverage (커버리지)
**목적**: 아이템/사용자 충분히 포함
**체크**:
```python
def check_coverage(df: pl.DataFrame, total_items: int) -> GateResult:
    unique_items = df["wine_sku_id"].n_unique()
    coverage = unique_items / total_items
    
    # 최소 80% 아이템이 학습 데이터에 포함되어야 함
    passed = coverage >= 0.80
    
    return GateResult(
        gate_name="item_coverage",
        passed=passed,
        metric_value=coverage,
        threshold=0.80,
    )
```

**추가 필요**: 현재 미구현

4-4. Gate 4: Sparsity Distribution (희소성 분포)
**목적**: Long-tail 충분히 포함
**체크**:
```python
def check_sparsity_distribution(df: pl.DataFrame) -> GateResult:
    item_counts = df.group_by("wine_sku_id").len()
    
    # 노출 < 10인 아이템이 전체의 20% 이상이어야 함
    sparse_items = (item_counts["len"] < 10).sum()
    sparse_ratio = sparse_items / len(item_counts)
    
    passed = sparse_ratio >= 0.20
    
    return GateResult(
        gate_name="sparsity_distribution",
        passed=passed,
        metric_value=sparse_ratio,
        threshold=0.20,
    )
```

**추가 필요**: 현재 미구현

4-5. Gate 5: Propensity Coverage (반사실 평가용)
**목적**: Counterfactual 평가 가능성 보장
**체크**:
```python
def check_propensity_coverage(policy_log: pl.DataFrame) -> GateResult:
    # propensity 필드 누락률 체크
    missing_rate = policy_log["propensity"].is_null().mean()
    
    # 5% 이하 누락이어야 함
    passed = missing_rate <= 0.05
    
    return GateResult(
        gate_name="propensity_coverage",
        passed=passed,
        metric_value=1.0 - missing_rate,
        threshold=0.95,
    )
```

**추가 필요**: 현재 propensity 필드는 있으나 게이트 미구현

5. 데이터 증강 전략 (Augmentation)

5-1. Augmentation 1: Hard Negative Mining
**목적**: 모델이 어려운 negative를 학습
**방법**:
```python
def mine_hard_negatives(
    user_id: str,
    positive_item: str,
    all_items: list[str],
    embeddings: dict[str, np.ndarray],
    k: int = 5,
) -> list[str]:
    """유사하지만 선택 안 된 아이템 샘플링"""
    pos_emb = embeddings[positive_item]
    
    # 코사인 유사도 계산
    similarities = {
        item: cosine_similarity(pos_emb, embeddings[item])
        for item in all_items
        if item != positive_item
    }
    
    # 상위 k개 유사 아이템 중 랜덤 샘플
    top_similar = sorted(similarities.items(), key=lambda x: -x[1])[:k*2]
    return random.sample([item for item, _ in top_similar], k)
```

**적용 시점**: Phase 2 (실제 데이터 통합 후)

5-2. Augmentation 2: Counterfactual Synthesis
**목적**: "만약 다른 와인을 추천했다면?" 시뮬레이션
**방법**:
```python
def synthesize_counterfactual(
    impression: dict,
    alternative_policy: Callable,
    propensity_model: Callable,
) -> dict:
    """대안 정책으로 추천했을 때의 결과 합성"""
    # 대안 정책으로 후보 생성
    alt_candidates = alternative_policy(impression["user_id"])
    
    # Propensity 추정
    propensity = propensity_model(
        user=impression["user_id"],
        candidates=alt_candidates,
        context=impression["context"],
    )
    
    # 합성 impression 생성
    return {
        "impression_id": f"cf_{impression['impression_id']}",
        "user_id": impression["user_id"],
        "items": alt_candidates,
        "propensity": propensity,
        "is_synthetic": True,
    }
```

**적용 시점**: Phase 3 (지속 수집 파이프라인)

5-3. Augmentation 3: Cross-Domain Transfer
**목적**: 다른 도메인 지식 전이
**방법**:
```python
# 예: 음식 추천 → 와인 추천
# "스테이크 좋아함" → "카베르네 소비뇽 추천"
def transfer_from_food_domain(
    user_food_prefs: list[str],
    food_wine_mapping: dict[str, list[str]],
) -> list[str]:
    """음식 취향으로부터 와인 추천 부트스트랩"""
    wine_prefs = []
    for food in user_food_prefs:
        wine_prefs.extend(food_wine_mapping.get(food, []))
    return list(set(wine_prefs))

# 예: 책/음악 취향 → 와인 스타일
# "클래식 음악" → "우아한 부르고뉴"
# "재즈" → "복잡한 론 와인"
```

**적용 시점**: Phase 2 (cold-start 완화용)

5-4. Augmentation 4: Temporal Perturbation
**목적**: Drinking window 변화 시뮬레이션
**방법**:
```python
def perturb_temporal_features(
    wine: dict,
    current_year: int,
    perturbation_years: list[int],
) -> list[dict]:
    """시간 경과에 따른 와인 상태 변화 시뮬레이션"""
    perturbed = []
    for delta in perturbation_years:
        new_year = current_year + delta
        new_stage = estimate_drinking_stage(wine, new_year)
        perturbed.append({
            **wine,
            "as_of_year": new_year,
            "drinking_stage": new_stage,
            "is_perturbed": True,
        })
    return perturbed
```

**적용 시점**: Phase 2 (temporal-aware 모델 학습용)

6. SOTA급 실험 환경 설계

6-1. 벤치마크 Suite (RFC-DATASET-BENCH-005 기반)
**필수 벤치**:
1. **B0: Baseline RS**
   - Matrix Factorization (ALS)
   - BPR (Bayesian Personalized Ranking)
   - 목적: 최소 기준선 고정

2. **B1: Two-Stage Industrial**
   - Candidate: Two-Tower + ANN
   - Ranking: DeepFM/DLRM
   - 목적: 산업 표준 재현

3. **B2: Graph-Enhanced**
   - LightGCN / Hetero GNN
   - Producer/Region propagation
   - 목적: 희소성 해결

4. **B3: High-End Specialized**
   - 고가(상위 10%) 필터
   - 희소(노출 < 100) 중심
   - 목적: 도메인 특화 평가

5. **B4: Temporal-Aware**
   - Drinking window 반영
   - Vintage aging 모델링
   - 목적: 시간 의존성 평가

**평가 지표**:
- Offline: Recall@K, NDCG@K, MAP, Coverage, Novelty
- Counterfactual: IPS, SNIPS, DR
- Long-horizon: 7일/30일 재구매율, Cellar-building, 반품율
- Domain-specific: Expert-weighted NDCG, Sparse-item Recall, Peak-proximity

6-2. 도메인 특화 태스크 (Challenge Tracks)
**Track A: Extreme Sparsity**
- 조건: 노출 < 50인 와인만
- 평가: Cold-start NDCG@10
- 목적: 인기 편향 모델 감점

**Track B: Temporal Fit**
- 조건: Drinking window 적합성
- 평가: Peak-proximity score
- 목적: 시간 의존성 평가

**Track C: Expert Alignment**
- 조건: 전문가 리뷰 가중
- 평가: Authority-weighted NDCG
- 목적: 권위 신호 효과 검증

**Track D: Multimodal Retrieval**
- 조건: 텍스트 + 이미지 쿼리
- 평가: Cross-modal Recall@K
- 목적: 멀티모달 효과 검증

6-3. 실험 관리 프로토콜
**버전 관리**:
```yaml
experiment_manifest_v1:
  experiment_id: "exp_20260212_001"
  dataset_version: "ds_v1"
  feature_set_version: "fs_v1"
  model_version: "two_tower_v2"
  hyperparameters:
    embedding_dim: 128
    learning_rate: 0.001
    batch_size: 512
  training:
    train_examples: 5343
    val_examples: 1145
    test_examples: 1146
    epochs: 50
    early_stopping: true
  evaluation:
    offline_metrics:
      recall@10: 0.234
      ndcg@10: 0.189
    counterfactual_metrics:
      ips_reward: 0.156
      snips_reward: 0.162
      dr_reward: 0.159
    domain_metrics:
      sparse_item_recall@10: 0.112
      expert_weighted_ndcg@10: 0.201
  quality_gates:
    - gate: temporal_leakage
      passed: true
    - gate: label_distribution
      passed: true
    - gate: propensity_coverage
      passed: true
  created_at: "2026-02-12T00:00:00Z"
```

**재현 체크리스트**:
- [ ] Dataset manifest 고정
- [ ] Split seed 고정
- [ ] Negative sampling seed 고정
- [ ] Feature schema version 고정
- [ ] Model architecture 고정
- [ ] Hyperparameter 고정
- [ ] Training procedure 고정
- [ ] Evaluation protocol 고정

7. 실행 로드맵

7-1. Week 1-2: Synthetic Scale-Up (Phase 1)
**목표**: 10K 와인, 10K 사용자, 100K impression
**작업**:
1. 와인 생성 스크립트 작성
   - Producer/Region/Variety 조합 확장
   - Vintage variation
   - 실제 분포 매칭

2. 사용자 페르소나 정의
   - Collector/Enthusiast/Casual/Gift/Investor
   - 행동 패턴 모델링

3. 상호작용 생성
   - Affinity matrix 기반
   - Temporal pattern 반영
   - Conversion funnel 반영

4. 품질 게이트 구현
   - Coverage gate
   - Sparsity distribution gate
   - Label distribution gate

**산출물**:
- `scripts/generate_synthetic_data.py`
- `data/synthetic_v1/` (100K+ examples)
- Quality gate report

7-2. Week 3-4: 증강 기법 구현 (Augmentation)
**목표**: Hard negative, Counterfactual synthesis
**작업**:
1. Hard negative mining
   - Embedding 기반 유사도 계산
   - Top-K similar 샘플링

2. Counterfactual synthesis
   - Alternative policy 정의
   - Propensity 추정

3. Temporal perturbation
   - Drinking stage 변화 시뮬레이션

**산출물**:
- `src/wine_rec/augmentation/` 모듈
- Augmented dataset (150K+ examples)

7-3. Week 5-6: 벤치마크 구현 (B0~B4)
**목표**: 5개 벤치 + 4개 트랙 구현
**작업**:
1. Baseline 모델 (B0)
   - ALS, BPR 구현

2. Industrial 모델 (B1)
   - Two-Tower, DeepFM 구현

3. Graph 모델 (B2)
   - LightGCN 구현

4. Domain-specific 평가
   - Track A~D 평가 스크립트

**산출물**:
- `src/wine_rec/models/baselines/` 확장
- `src/wine_rec/evaluation/benchmark_suite.py`
- Benchmark report (JSON)

7-4. Week 7-8: Counterfactual 평가 (IPS/SNIPS/DR)
**목표**: 반사실 평가 프로토콜 구현
**작업**:
1. Propensity 추정 모델
   - Logged policy 기반

2. IPS/SNIPS/DR 계산
   - Off-policy evaluation

3. Quality gate 통합
   - Propensity coverage gate

**산출물**:
- `src/wine_rec/evaluation/counterfactual.py` (이미 있음, 확장)
- Counterfactual metrics in benchmark report

7-5. Week 9-10: 실제 데이터 통합 (Phase 2)
**목표**: WineSensed, X-Wines 통합
**작업**:
1. 데이터 다운로드 및 전처리
2. IR 매핑 (source_system, license_tag)
3. 중복 제거 (dedup)
4. 통합 데이터셋 생성 (500K+ examples)

**산출물**:
- `data/integrated_v1/`
- Integration report

7-6. Week 11-12: 지속 수집 파이프라인 (Phase 3)
**목표**: 실시간 로그 → 학습 데이터 자동화
**작업**:
1. Kinesis → S3 → Parquet 파이프라인
2. 일별 증분 업데이트
3. 주별 전체 재학습
4. Distribution shift 모니터링

**산출물**:
- `src/wine_rec/pipeline/continuous_training.py`
- Monitoring dashboard

8. 성공 기준 (Definition of Done)

8-1. 데이터 규모
- [ ] 와인: 10K+ (현재 120 → 83배 증가)
- [ ] 사용자: 10K+ (현재 200 → 50배 증가)
- [ ] Impression: 100K+ (현재 2K → 50배 증가)
- [ ] 희소 아이템: 1K+ (노출 < 100)
- [ ] 고가 아이템: 1K+ (상위 10%)

8-2. 데이터 품질
- [ ] Temporal leakage: 0% violation
- [ ] Label distribution: 5~30% positive
- [ ] Item coverage: 80%+
- [ ] Sparsity distribution: 20%+ long-tail
- [ ] Propensity coverage: 95%+

8-3. 벤치마크
- [ ] B0~B4 벤치 구현 완료
- [ ] Track A~D 평가 완료
- [ ] Counterfactual 평가 (IPS/SNIPS/DR) 필수 포함
- [ ] Long-horizon 지표 (7일/30일 재구매) 포함

8-4. 재현성
- [ ] Dataset manifest 생성
- [ ] Experiment manifest 생성
- [ ] Quality gate report 생성
- [ ] Benchmark report 생성
- [ ] 외부 재현 가능 (README + 스크립트)

9. Conclusion

본 RFC는 "SOTA급 실험 환경"을 위한 데이터 준비 전략을 고정함:

1. **규모**: 10K+ 와인, 10K+ 사용자, 100K+ impression (현재 대비 50~83배)
2. **품질**: 5개 quality gate (temporal/label/coverage/sparsity/propensity)
3. **증강**: Hard negative, Counterfactual, Temporal perturbation
4. **평가**: 5개 벤치 + 4개 트랙 + Counterfactual + Long-horizon
5. **재현**: Manifest + Seed + Version + Protocol 고정

이 기준을 충족하면, "프로토타입"이 아니라 **"SOTA 규정자(Definer)"** 수준의 실험 환경이 됨.

**핵심 메시지**:
- 데이터 규모가 부족하면 → Synthetic scale-up (Phase 1)
- 데이터 품질이 낮으면 → Quality gates (Section 4)
- 평가가 약하면 → Counterfactual + Long-horizon (Section 6)
- 재현이 안 되면 → Manifest + Seed 고정 (Section 6-3)

**다음 단계**:
1. Week 1-2: Synthetic scale-up 스크립트 작성
2. Week 3-4: Augmentation 모듈 구현
3. Week 5-6: Benchmark suite 구현
4. Week 7-8: Counterfactual 평가 통합
5. Week 9-10: 실제 데이터 통합
6. Week 11-12: 지속 수집 파이프라인

이 로드맵을 따르면 12주 내에 SOTA급 실험 환경 구축 완료.
