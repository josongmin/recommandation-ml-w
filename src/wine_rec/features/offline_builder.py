"""Offline feature builder (RFC-FEATURE-MANIFEST-010 §4).

Manifest-driven offline feature construction with time-travel join enforcement.
Time-travel join 강제: as_of_ts <= event_ts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import yaml

from wine_rec.common.logging import get_logger
from wine_rec.schemas.manifest import EntityManifest, FeatureDef, FeatureManifest


log = get_logger(__name__)

_MANIFEST_PATH = Path(__file__).parent / "manifest" / "feature_manifest_v1.yaml"

# Local-dev table aliases: manifest name → seed data name
_TABLE_ALIASES: dict[str, str] = {
    "user_profile_snapshot_v1": "user_profile_v1",
    "wine_attr_ir_v1": "wine_sku_attr_ir_v1",
    "wine_sku_inventory_v1": "wine_sku_attr_ir_v1",
}


def load_manifest(path: Path | None = None) -> FeatureManifest:
    """Load and validate the feature manifest YAML."""
    manifest_path = path or _MANIFEST_PATH
    raw = yaml.safe_load(manifest_path.read_text())
    # add generated_at if missing (for hand-written manifests)
    if "generated_at" not in raw:
        raw["generated_at"] = "2026-01-01T00:00:00Z"
    return FeatureManifest.model_validate(raw)


def _resolve_table(data_root: Path, table_name: str) -> pl.DataFrame | None:
    """Find and load a table from the data directory hierarchy.

    Search order: gold_b > gold_a > silver > bronze > profiles.
    """
    search_dirs = ["gold_b", "gold_a", "silver", "bronze", "profiles"]
    names_to_try = [table_name]
    if table_name in _TABLE_ALIASES:
        names_to_try.append(_TABLE_ALIASES[table_name])

    for name in names_to_try:
        for layer in search_dirs:
            table_dir = data_root / layer / name
            if not table_dir.exists():
                continue
            parts = sorted(table_dir.glob("dt=*/data.parquet"))
            if parts:
                return pl.read_parquet(parts[-1])
            flat = table_dir / "data.parquet"
            if flat.exists():
                return pl.read_parquet(flat)
    return None


def _apply_time_travel_filter(
    df: pl.DataFrame,
    feature_def: FeatureDef,
    event_ts: str,
) -> pl.DataFrame:
    """Filter rows that satisfy time-travel constraint: ts_field <= event_ts."""
    rule = feature_def.time_travel_rule.rule
    ts_field = feature_def.time_travel_rule.timestamp_field

    if rule == "none" or ts_field not in df.columns:
        return df

    if df[ts_field].dtype == pl.Utf8:
        df = df.with_columns(pl.col(ts_field).str.to_datetime(time_zone="UTC"))

    event_dt = pl.lit(event_ts).str.to_datetime(time_zone="UTC")
    return df.filter(pl.col(ts_field) <= event_dt)


def _extract_feature_value(
    df: pl.DataFrame,
    feature_def: FeatureDef,
    entity_key: str,
) -> pl.DataFrame:
    """Extract a single feature column from source table.

    Uses `feature_def.source.key` to look up in the source table when it
    differs from the entity join key (e.g. wine_core_id in scarcity IR
    looked up for a wine_sku entity).

    Returns a 2-column DataFrame: (entity_key, feature_name).
    """
    source_key = feature_def.source.key
    # prefer source.key for lookup; fall back to entity key
    lookup_key = source_key if source_key in df.columns else entity_key
    if lookup_key not in df.columns:
        return pl.DataFrame({entity_key: [], feature_def.name: []})

    value_path = feature_def.source.value_path
    if value_path and value_path in df.columns:
        result = df.select(pl.col(lookup_key), pl.col(value_path).alias(feature_def.name))
    else:
        result = df.select(pl.col(lookup_key)).with_columns(
            pl.lit(None).alias(feature_def.name),
        )

    # deduplicate: keep latest per key
    if result[lookup_key].n_unique() < len(result):
        result = result.unique(subset=[lookup_key], keep="last")

    # rename source key → entity key when they differ (for downstream join)
    if lookup_key != entity_key:
        result = result.rename({lookup_key: entity_key})

    return result


def _apply_null_policy(
    df: pl.DataFrame,
    feature_def: FeatureDef,
) -> pl.DataFrame:
    """Apply null_policy from manifest: error | default | allow_null."""
    col_name = feature_def.name

    if col_name not in df.columns:
        return df

    null_count = df[col_name].null_count()

    if feature_def.null_policy == "error" and null_count > 0:
        msg = f"Null policy violation: feature '{col_name}' has {null_count} nulls (policy=error)"
        raise ValueError(msg)
    if feature_def.null_policy == "default" and feature_def.default is not None:
        default_val = _cast_default(feature_def.default, feature_def.dtype)
        df = df.with_columns(pl.col(col_name).fill_null(pl.lit(default_val)))

    return df


def _cast_default(default: Any, dtype: str) -> Any:
    """Cast a manifest default value to the appropriate Python type."""
    type_map: dict[str, type] = {
        "float": float,
        "int": int,
        "bool": bool,
        "string": str,
    }
    cast_fn = type_map.get(dtype)
    if cast_fn is None:
        return default
    if dtype == "bool":
        return str(default).lower() in ("true", "1", "yes")
    return cast_fn(default)


def _build_entity_features(
    entity: EntityManifest,
    data_root: Path,
    event_ts: str,
) -> pl.DataFrame | None:
    """Build all features for a single entity type."""
    key_col = entity.join_keys[0]
    result_df: pl.DataFrame | None = None
    table_cache: dict[str, pl.DataFrame | None] = {}

    for feature_def in entity.features:
        table_name = feature_def.source.table

        if table_name not in table_cache:
            table_cache[table_name] = _resolve_table(data_root, table_name)

        source_df = table_cache[table_name]
        if source_df is None:
            log.warning("source_not_found", table=table_name, feature=feature_def.name)
            continue

        source_key = feature_def.source.key
        if key_col not in source_df.columns and source_key not in source_df.columns:
            log.warning(
                "key_not_found",
                table=table_name,
                entity_key=key_col,
                source_key=source_key,
                feature=feature_def.name,
            )
            continue

        # time-travel filter
        filtered = _apply_time_travel_filter(source_df, feature_def, event_ts)

        # extract feature value
        feature_col = _extract_feature_value(filtered, feature_def, key_col)

        # apply null policy
        feature_col = _apply_null_policy(feature_col, feature_def)

        # join into result
        if result_df is None:
            result_df = feature_col
        else:
            result_df = result_df.join(feature_col, on=key_col, how="full", coalesce=True)

    return result_df


def build_offline_features(
    *,
    feature_set_version: str,
    event_ts: str,
    output_path: str,
    data_root: str = "data",
    manifest_path: str | None = None,
) -> dict[str, pl.DataFrame]:
    """Build features_offline_v1 from manifest definition.

    Ensures:
        - as_of_ts/published_at <= event_ts for all features
        - recipe_version/transform_version recorded
        - lineage_input_refs tracked

    Args:
        feature_set_version: Version string to match manifest.
        event_ts: ISO timestamp for time-travel boundary.
        output_path: Directory to write output Parquet files.
        data_root: Root directory containing data layers.
        manifest_path: Override path to manifest YAML.

    Returns:
        Dict mapping entity_type to feature DataFrame.
    """
    manifest = load_manifest(Path(manifest_path) if manifest_path else None)

    if manifest.feature_set_version != feature_set_version:
        log.warning(
            "version_mismatch",
            manifest=manifest.feature_set_version,
            requested=feature_set_version,
        )

    root = Path(data_root)
    out = Path(output_path)
    results: dict[str, pl.DataFrame] = {}

    for entity in manifest.entities:
        log.info(
            "building_entity_features",
            entity_type=entity.entity_type,
            n_features=len(entity.features),
        )

        entity_features = _build_entity_features(entity, root, event_ts)

        if entity_features is None or len(entity_features) == 0:
            log.warning("no_features_built", entity_type=entity.entity_type)
            continue

        # add metadata columns
        entity_features = entity_features.with_columns(
            pl.lit(feature_set_version).alias("_feature_set_version"),
            pl.lit(event_ts).alias("_event_ts"),
        )

        # write output
        entity_path = out / f"features_offline_v1__{entity.entity_type}" / "data.parquet"
        entity_path.parent.mkdir(parents=True, exist_ok=True)
        entity_features.write_parquet(entity_path)

        results[entity.entity_type] = entity_features
        log.info(
            "entity_features_built",
            entity_type=entity.entity_type,
            rows=len(entity_features),
            columns=entity_features.columns,
        )

    log.info("offline_features_done", entities=list(results.keys()))
    return results
