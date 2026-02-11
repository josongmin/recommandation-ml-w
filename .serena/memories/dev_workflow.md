# 개발 워크플로우

## 필수 명령어 (justfile)

### Setup
```bash
just setup          # venv + deps + pre-commit hooks
just install-dev    # dev + test deps만
```

### Quality Checks
```bash
just check          # lint + typecheck (CI와 동일)
just lint           # ruff check
just fmt            # ruff format + fix
just typecheck      # basedpyright strict
```

### Tests
```bash
just test           # 전체 테스트
just test-unit      # unit 테스트만
just test-fast      # -n auto (병렬)
just test -v        # verbose
```

### Serving
```bash
just serve          # uvicorn --reload (localhost:8000)
```

## TDD 원칙 (CLAUDE.md 지시)
1. **테스트 먼저 작성**
2. **stub/fake/hardcoding 금지**: 통합 안 된 코드 절대 불허
3. **No deadcode**: 사용하지 않는 코드 즉시 삭제
4. **Coverage 55%+**: pyproject.toml L205 기준

## 커밋 전 체크리스트
```bash
# 1. Lint + typecheck
just check

# 2. 관련 테스트 실행
just test tests/unit/pipeline/test_bronze_to_silver.py

# 3. Coverage 확인
just test --cov-report=html
open htmlcov/index.html

# 4. Pre-commit (자동)
git commit -m "..."
```

## Ruff 규칙 하이라이트
- **F, E, W**: pyflakes, pycodestyle
- **I**: isort (import 정렬)
- **ANN**: type annotation 필수
- **S**: bandit (보안)
- **PL**: pylint (복잡도)
- **TC003**: TYPE_CHECKING 사용 권장

### Per-file ignores
- `tests/**`: S101 (assert), ANN (annotation 생략 가능)
- `scripts/**`: T20 (print OK), S311 (random OK)
- `src/schemas/**`: TC003 (Pydantic runtime 필요)

## Type Checking
- **basedpyright strict mode**
- boto3-stubs 포함 (L48)
- 서드파티 stub 부족 시 "warning"으로 강등 (L162-165)
