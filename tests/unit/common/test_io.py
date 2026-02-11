"""Tests for atomic I/O utilities."""

from pathlib import Path

import polars as pl

from wine_rec.common.io import write_parquet_atomic


class TestWriteParquetAtomic:
    def test_writes_valid_parquet(self, tmp_path: Path):
        df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        out = tmp_path / "subdir" / "data.parquet"

        write_parquet_atomic(df, out)

        assert out.exists()
        result = pl.read_parquet(out)
        assert result.shape == (3, 2)
        assert result["a"].to_list() == [1, 2, 3]

    def test_no_temp_file_left_on_success(self, tmp_path: Path):
        df = pl.DataFrame({"a": [1]})
        out = tmp_path / "data.parquet"

        write_parquet_atomic(df, out)

        # temp file should be cleaned up
        temp = tmp_path / ".data.parquet.tmp"
        assert not temp.exists()

    def test_creates_parent_dirs(self, tmp_path: Path):
        df = pl.DataFrame({"a": [1]})
        out = tmp_path / "deep" / "nested" / "dir" / "data.parquet"

        write_parquet_atomic(df, out)

        assert out.exists()

    def test_overwrites_existing(self, tmp_path: Path):
        out = tmp_path / "data.parquet"

        # write original
        pl.DataFrame({"a": [1]}).write_parquet(out)

        # overwrite atomically
        df2 = pl.DataFrame({"a": [99, 100]})
        write_parquet_atomic(df2, out)

        result = pl.read_parquet(out)
        assert result["a"].to_list() == [99, 100]
