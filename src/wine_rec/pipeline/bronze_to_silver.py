"""Bronze → Silver ETL (RFC-E2E-PIPELINE-006 §2).

Cleaning, dedup, schema validation on raw event logs.
Polars-based for local dev, Spark-based for production.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from wine_rec.common.io import write_parquet_atomic
from wine_rec.common.logging import get_logger


log = get_logger(__name__)


def _dedup_events(df: pl.DataFrame, key_cols: list[str]) -> pl.DataFrame:
    """Deduplicate events by key columns, keeping the first occurrence."""
    before = len(df)
    df = df.unique(subset=key_cols, keep="first")
    after = len(df)
    if before != after:
        log.info("dedup", removed=before - after, remaining=after)
    return df


def _validate_not_null(df: pl.DataFrame, required_cols: list[str]) -> pl.DataFrame:
    """Drop rows where required columns are null."""
    before = len(df)
    mask = pl.lit(True)
    for col in required_cols:
        if col in df.columns:
            mask = mask & pl.col(col).is_not_null()
    df = df.filter(mask)
    dropped = before - len(df)
    if dropped > 0:
        log.warning("null_drop", dropped=dropped, columns=required_cols)
    return df


def _normalize_timestamps(df: pl.DataFrame, ts_cols: list[str]) -> pl.DataFrame:
    """Parse ISO timestamp strings to datetime."""
    for col in ts_cols:
        if col in df.columns and df[col].dtype == pl.Utf8:
            df = df.with_columns(pl.col(col).str.to_datetime(time_zone="UTC").alias(col))
    return df


def clean_impressions(df: pl.DataFrame) -> pl.DataFrame:
    """Clean impression events: dedup, validate, normalize."""
    df = _dedup_events(df, ["impression_id"])
    df = _validate_not_null(df, ["impression_id", "user_id", "shown_ts", "surface", "items"])
    return _normalize_timestamps(df, ["shown_ts"])


def clean_actions(df: pl.DataFrame) -> pl.DataFrame:
    """Clean action events."""
    df = _dedup_events(df, ["impression_id", "wine_sku_id", "action_type", "action_ts"])
    df = _validate_not_null(df, ["impression_id", "wine_sku_id", "action_type", "action_ts"])
    return _normalize_timestamps(df, ["action_ts"])


def clean_orders(df: pl.DataFrame) -> pl.DataFrame:
    """Clean order events."""
    df = _dedup_events(df, ["order_id"])
    df = _validate_not_null(df, ["order_id", "user_id", "wine_sku_id", "order_ts"])
    df = _normalize_timestamps(df, ["order_ts"])
    # clamp negative quantities
    if "quantity" in df.columns:
        df = df.with_columns(pl.col("quantity").clip(lower_bound=1))
    return df


def clean_policies(df: pl.DataFrame) -> pl.DataFrame:
    """Clean policy logs."""
    df = _dedup_events(df, ["impression_id"])
    return _validate_not_null(df, ["impression_id", "model_version", "feature_set_version"])


_CLEANERS: dict[str, type[object] | None] = {
    "impression_log_v1": None,
    "action_log_v1": None,
    "order_log_v1": None,
    "policy_log_v1": None,
}

_CLEAN_FN = {
    "impression_log_v1": clean_impressions,
    "action_log_v1": clean_actions,
    "order_log_v1": clean_orders,
    "policy_log_v1": clean_policies,
}


def run_bronze_to_silver(*, input_path: str, output_path: str, dt: str) -> dict[str, int]:
    """Clean and validate raw events from Bronze to Silver.

    Args:
        input_path: Root path for Bronze data (e.g. data/bronze)
        output_path: Root path for Silver output (e.g. data/silver)
        dt: Processing date partition (e.g. 2026-01-15)

    Returns:
        Dict mapping log_type to number of output rows.
    """
    input_root = Path(input_path)
    output_root = Path(output_path)
    results: dict[str, int] = {}

    for log_type, clean_fn in _CLEAN_FN.items():
        parquet_path = input_root / log_type / "data.parquet"
        if not parquet_path.exists():
            log.warning("missing_input", log_type=log_type, path=str(parquet_path))
            continue

        log.info("processing", log_type=log_type)
        df = pl.read_parquet(parquet_path)
        df = clean_fn(df)

        # add processing metadata
        df = df.with_columns(
            pl.lit(dt).alias("_process_dt"),
            pl.lit("bronze_to_silver").alias("_pipeline_stage"),
        )

        out_path = output_root / log_type / f"dt={dt}" / "data.parquet"
        write_parquet_atomic(df, out_path)

        results[log_type] = len(df)
        log.info("completed", log_type=log_type, rows=len(df))

    return results
