"""Atomic I/O utilities for pipeline resilience."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wine_rec.common.logging import get_logger


if TYPE_CHECKING:
    from pathlib import Path

    import polars as pl

log = get_logger(__name__)


def write_parquet_atomic(df: pl.DataFrame, path: Path) -> None:
    """Write a Parquet file atomically via temp-file-then-rename.

    Prevents corrupted output from partial writes (disk full, crash, etc.).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp"
    try:
        df.write_parquet(temp_path)
        temp_path.rename(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    log.info("write_completed", path=str(path), rows=len(df))
