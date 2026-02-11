# Suggested Commands (Darwin)

## Setup
```bash
just setup        # venv 생성 + 의존성 설치 + pre-commit 설치
just install      # core만 설치
just install-dev  # dev+test 의존성
just lock         # lockfile 동기화
```

## Quality (lint, format, typecheck)
```bash
just check        # lint + typecheck
just lint         # ruff check
just fmt          # ruff format + fix
just fix          # fmt + basedpyright
```

## Pre-commit
```bash
just hooks        # 전체 파일 pre-commit 실행
just hooks-update # pre-commit 훅 업데이트
```

## Test
```bash
just test         # 전체 테스트 (pytest)
just test-unit    # unit만
just test-integration  # integration (AWS mocks)
just test-e2e     # e2e
just test-fast    # 빠른 테스트 (slow/e2e 제외, -n auto)
just test-v       # verbose 출력
```

## Run
```bash
just serve        # FastAPI 로컬 (uvicorn --reload :8000)
just benchmark    # evaluator 벤치마크 실행
```

## Entry Points
```bash
uv run wine-rec train ...     # CLI train
uv run wine-rec evaluate ...  # CLI evaluate
uv run wine-rec serve ...     # CLI serve
```

## Docker
```bash
just docker-train  # training 이미지 빌드
just docker-serve  # serving 이미지 빌드
```

## Terraform
```bash
just tf-init   # dev env init
just tf-plan   # dev env plan
just tf-apply  # dev env apply
```

## Clean
```bash
just clean     # 캐시·빌드 산출물 제거
```
