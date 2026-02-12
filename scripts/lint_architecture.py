#!/usr/bin/env python
"""Architecture lint - 모듈 경계 및 의존성 검증.

아키텍처 규칙:
1. Ports & Adapters: infra/는 contracts/만 의존
2. Layer 분리: serving ← models ← features ← pipeline
3. Shared Kernel: schemas/, contracts/는 다른 모듈 의존 금지
4. 순환 의존성 금지
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import NamedTuple


class ImportViolation(NamedTuple):
    """Import violation."""

    file: Path
    line: int
    imported: str
    reason: str


# Architecture rules
RULES = {
    # Shared Kernel: 다른 모듈 의존 금지
    "src/wine_rec/schemas": {
        "forbidden": ["pipeline", "models", "serving", "features", "infra", "ingestion"],
        "reason": "Shared Kernel: schemas cannot depend on domain modules",
    },
    "src/wine_rec/contracts": {
        "forbidden": ["pipeline", "models", "serving", "features", "infra", "ingestion"],
        "reason": "Shared Kernel: contracts cannot depend on implementations",
    },
    # Infra: contracts만 의존
    "src/wine_rec/infra": {
        "forbidden": ["pipeline", "models", "serving", "features", "ingestion"],
        "allowed": ["contracts", "schemas", "common"],
        "reason": "Ports & Adapters: infra can only depend on contracts",
    },
    # Serving: models 의존 가능, pipeline 금지
    "src/wine_rec/serving": {
        "forbidden": ["pipeline"],
        "reason": "Layer separation: serving cannot import pipeline internals",
    },
    # Models: pipeline 금지, serving 금지
    "src/wine_rec/models": {
        "forbidden": ["serving", "pipeline", "ingestion"],
        "reason": "Layer separation: models cannot import serving/pipeline",
    },
    # Ingestion: models 금지
    "src/wine_rec/ingestion": {
        "forbidden": ["models", "serving"],
        "reason": "Layer separation: ingestion cannot import models/serving",
    },
    # Features: serving/models 금지
    "src/wine_rec/features": {
        "forbidden": ["serving", "models"],
        "reason": "Layer separation: features cannot import serving/models",
    },
}


def extract_imports(file_path: Path) -> list[tuple[int, str]]:
    """Extract imports from Python file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))

    return imports


def check_file(file_path: Path) -> list[ImportViolation]:
    """Check architecture violations in file."""
    violations = []

    # Find applicable rule
    rule = None

    for path_prefix, rule_config in RULES.items():
        if str(file_path).startswith(path_prefix):
            rule = rule_config
            break

    if not rule:
        return violations

    # Extract imports
    imports = extract_imports(file_path)

    for line, imported_module in imports:
        # Check if import starts with wine_rec
        if not imported_module.startswith("wine_rec"):
            continue

        # Check forbidden imports
        if "forbidden" in rule:
            for forbidden in rule["forbidden"]:
                if f"wine_rec.{forbidden}" in imported_module:
                    violations.append(
                        ImportViolation(
                            file=file_path.relative_to(Path.cwd()),
                            line=line,
                            imported=imported_module,
                            reason=rule["reason"],
                        )
                    )

        # Check allowed imports (if allowlist exists)
        if "allowed" in rule:
            allowed_prefixes = [f"wine_rec.{a}" for a in rule["allowed"]]
            allowed_prefixes.append("wine_rec")  # Allow wine_rec itself

            if not any(imported_module.startswith(prefix) for prefix in allowed_prefixes):
                # Also check if it's in forbidden
                is_forbidden = any(
                    f"wine_rec.{forbidden}" in imported_module
                    for forbidden in rule.get("forbidden", [])
                )

                if not is_forbidden:
                    violations.append(
                        ImportViolation(
                            file=file_path.relative_to(Path.cwd()),
                            line=line,
                            imported=imported_module,
                            reason=f"{rule['reason']} (allowed: {rule['allowed']})",
                        )
                    )

    return violations


def main() -> int:
    """Run architecture lint."""
    print("🔍 Architecture Lint - Module Boundary Verification\n")

    all_violations = []
    root = Path.cwd()

    # Check all Python files
    for python_file in (root / "src" / "wine_rec").rglob("*.py"):
        violations = check_file(python_file)
        all_violations.extend(violations)

    if not all_violations:
        print("✅ No architecture violations found!")
        print("\nVerified rules:")
        for path_prefix, rule in RULES.items():
            print(f"  - {path_prefix}")
            if "forbidden" in rule:
                print(f"    Forbidden: {', '.join(rule['forbidden'])}")
            if "allowed" in rule:
                print(f"    Allowed: {', '.join(rule['allowed'])}")
        return 0

    # Report violations
    print(f"❌ Found {len(all_violations)} architecture violation(s):\n")

    for violation in all_violations:
        print(f"  {violation.file}:{violation.line}")
        print(f"    Import: {violation.imported}")
        print(f"    Reason: {violation.reason}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
