"""Dataset Manifest Diff Tool (RFC-DATASET-BUILDER-011 §8-2).

Compares two manifest versions and outputs changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def diff_manifests(path_a: str, path_b: str) -> dict[str, object]:
    """Compare two dataset manifests and return diff."""
    a = json.loads(Path(path_a).read_text())
    b = json.loads(Path(path_b).read_text())

    changes: list[dict[str, object]] = []
    all_keys = set(a.keys()) | set(b.keys())

    for key in sorted(all_keys):
        val_a = a.get(key)
        val_b = b.get(key)
        if val_a != val_b:
            changes.append({"field": key, "old": val_a, "new": val_b})

    return {
        "version_a": a.get("dataset_version", "unknown"),
        "version_b": b.get("dataset_version", "unknown"),
        "total_changes": len(changes),
        "changes": changes,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <manifest_a.json> <manifest_b.json>")
        sys.exit(1)
    result = diff_manifests(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))
