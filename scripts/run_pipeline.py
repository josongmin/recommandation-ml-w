#!/usr/bin/env python
"""Run complete data pipeline: seed → training dataset.

Since seed_data.py already generates Bronze + Gold-A + Gold-B,
this script just runs seed and builds training dataset.

Usage:
    python scripts/run_pipeline.py [--skip-seed]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from wine_rec.common.logging import get_logger
from wine_rec.pipeline.dataset_builder import build_training_examples

log = get_logger(__name__)


def print_section(title: str) -> None:
    """Print section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def run_seed_data(output_dir: Path, seed: int = 42) -> None:
    """Step 1: Generate seed data (Bronze + Gold-A + Gold-B)."""
    print_section("Step 1: Generate Seed Data")

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/seed_data.py",
            "--output-dir",
            str(output_dir),
            "--seed",
            str(seed),
        ],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        log.error("seed_data_failed", returncode=result.returncode)
        sys.exit(1)

    print("✅ Seed data generated successfully")


def run_dataset_builder(data_dir: Path, dataset_version: str = "v1") -> None:
    """Step 2: Build training dataset."""
    print_section("Step 2: Build Training Dataset")

    print(f"  Data root: {data_dir}")
    print(f"  Dataset version: {dataset_version}")

    examples_df = build_training_examples(
        dataset_version=dataset_version,
        feature_set_version="fs_v1",
        seed=42,
        data_root=str(data_dir),
        output_root=str(data_dir / "training"),
        cap_per_positive=10,
        attribution_window_days=7,
    )

    print("\n📊 Dataset Statistics:")
    print(f"  Total examples: {len(examples_df):,}")

    if "label" in examples_df.columns:
        label_dist = examples_df["label"].value_counts().sort("label")
        print("  Label distribution:")
        for row in label_dist.iter_rows(named=True):
            print(f"    {row['label']}: {row['count']:,}")

    if "split" in examples_df.columns:
        split_dist = examples_df["split"].value_counts().sort("split")
        print("  Split distribution:")
        for row in split_dist.iter_rows(named=True):
            print(f"    {row['split']}: {row['count']:,}")

    output_path = data_dir / "training" / dataset_version
    print(f"\n✅ Training dataset saved to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ML data pipeline")
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seed generation (use existing)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Output directory",
    )
    parser.add_argument(
        "--dataset-version",
        default="v1",
        help="Dataset version",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )

    args = parser.parse_args()

    print("\n🚀 Wine Recommendation ML Pipeline")
    print("=" * 70)
    print(f"  Output: {args.output_dir}")
    print(f"  Dataset version: {args.dataset_version}")
    print(f"  Seed: {args.seed}")
    print("=" * 70)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not args.skip_seed:
            run_seed_data(args.output_dir, seed=args.seed)
        else:
            print("\n⏭️  Skipping seed generation")

        run_dataset_builder(args.output_dir, dataset_version=args.dataset_version)

        print_section("Pipeline Complete! 🎉")
        print("Generated:")
        print(f"  ✅ Bronze: {args.output_dir}/bronze/")
        print(f"  ✅ Gold-A: {args.output_dir}/gold_a/")
        print(f"  ✅ Gold-B: {args.output_dir}/gold_b/")
        print(f"  ✅ Training: {args.output_dir}/training/{args.dataset_version}/")

        print("\nNext: just serve")
        return 0

    except Exception as e:
        log.exception("pipeline_failed", error=str(e))
        print(f"\n❌ Failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
