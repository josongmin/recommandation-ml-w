# Wine-Rec 빠른 시작 가이드

## 🚀 원클릭 설정

### 전체 초기화 (처음 시작)
```bash
just init-all
```
- Python 환경 설정
- AWS 리소스 생성
- 데이터 생성

### 데이터만 재생성
```bash
just data-reset
```

### AWS만 재생성
```bash
just aws-reset
```

## 📋 주요 명령어

### 데이터 관리
```bash
just data-init      # 데이터 초기화 (seed + training)
just data-clean     # 데이터 삭제
just data-reset     # 데이터 재생성 (clean + init)
just data-retrain   # 학습 데이터만 재생성
just data-stats     # 데이터 통계 확인
```

### AWS 관리
```bash
just aws-init       # AWS 리소스 생성
just aws-destroy    # AWS 리소스 삭제
just aws-reset      # AWS 리소스 재생성
just aws-status     # AWS 리소스 상태 확인
just aws-setup      # AWS credentials 설정
```

### 전체 환경
```bash
just init-all       # 전체 초기화
just clean-all      # 전체 삭제
just reset-all      # 전체 재생성
just status         # 전체 상태 확인
```

### 개발
```bash
just serve          # API 서버 시작
just test           # 테스트 실행
just lint           # 린트 체크
just fmt            # 포맷팅
```

## 🔄 일반적인 워크플로우

### 처음 시작할 때
```bash
# 1. 전체 초기화
just init-all

# 2. AWS credentials 설정 (필요시)
just aws-setup

# 3. 상태 확인
just status

# 4. API 서버 시작
just serve
```

### 데이터 변경 후
```bash
# 학습 데이터만 재생성
just data-retrain

# 또는 전체 재생성
just data-reset
```

### 깨끗하게 다시 시작
```bash
# 전체 재생성
just reset-all
```

## 📊 상태 확인

### 전체 상태
```bash
just status
```

출력 예시:
```
🔍 시스템 상태 확인

=== Python 환경 ===
✓ Python: Python 3.11.0
✓ uv: uv 0.1.0

=== AWS 환경 ===
✓ AWS CLI: aws-cli/2.15.0
✓ AWS Config: .aws/config
✓ AWS Credentials: .aws/credentials

=== Terraform ===
✓ Terraform: Terraform v1.9.8

📊 데이터 통계:

=== Seed Data ===
✓ 와인: 120 종
✓ 사용자: 200 명
✓ Impression: 2000 건

=== Training Data ===
✓ Total: 7634 examples
  - Train: 5343
  - Val: 1145
  - Test: 1146
  - Positive: 1452 (19.0%)

📊 AWS 리소스 상태:
wine-rec-dev-data
wine-rec-dev-features-online-v1
wine-rec-dev-wine-events-stream
```

### 데이터만 확인
```bash
just data-stats
```

### AWS만 확인
```bash
just aws-status
```

## 🛠️ 트러블슈팅

### AWS credentials 없음
```bash
just aws-setup
# 또는
aws configure --profile wine-rec-dev
```

### 데이터 오류
```bash
# 데이터 재생성
just data-reset
```

### 전체 환경 오류
```bash
# 전체 재생성
just reset-all
```

### Terraform 오류
```bash
# Terraform 재초기화
just tf-init

# AWS 리소스 재생성
just aws-reset
```

## 📦 디렉토리 구조

```
data/
├── gold_a/              # Master data
│   ├── wine_core_master_v1/
│   ├── wine_sku_master_v1/
│   └── review_master_v1/
├── bronze/              # Event logs
│   ├── impression_log_v1/
│   ├── action_log_v1/
│   ├── order_log_v1/
│   └── policy_log_v1/
├── gold_b/              # IR data
│   ├── wine_review_aggregate_ir_v1/
│   ├── wine_temporal_ir_v1/
│   ├── wine_scarcity_ir_v1/
│   └── wine_sku_attr_ir_v1/
├── profiles/            # User profiles
│   └── user_profile_v1/
└── training/            # Training datasets
    └── training_examples_v1__ds=ds_v1/
        ├── data.parquet
        └── manifest.json
```

## 🎯 다음 단계

1. **모델 학습**: `src/wine_rec/models/training/`
2. **평가**: `src/wine_rec/models/evaluation/`
3. **서빙**: `just serve` → http://localhost:8000
4. **벤치마크**: RFC-DATASET-BENCH-005 참고
5. **SOTA 실험**: RFC-TRAINING-DATA-015 참고

## 📚 추가 문서

- [RFC 목록](rfc/README.md)
- [E2E 파이프라인](rfc/RFC-E2E-PIPELINE-006.md)
- [데이터셋 벤치마크](rfc/RFC-DATASET-BENCH-005.md)
- [학습 데이터 준비](rfc/RFC-TRAINING-DATA-015__SOTA-Grade-Training-Data-Preparation-v1.md)
