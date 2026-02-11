# Task Completion Checklist

작업 완료 시 수행할 명령:

1. **Format & Lint**
   ```bash
   just fmt
   ```

2. **Type Check**
   ```bash
   just typecheck
   ```

3. **Test**
   ```bash
   just test
   ```

4. **Full Check (권장)**
   ```bash
   just check
   just test
   ```

5. **Pre-commit (커밋 전)**
   ```bash
   just hooks
   ```

Coverage: 55% 이상 유지 (pytest --cov-fail-under=55)
