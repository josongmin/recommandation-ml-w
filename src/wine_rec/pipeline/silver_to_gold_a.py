"""Silver → Gold-A SSOT ETL (RFC-E2E-PIPELINE-006 §3).

Enriches Silver events and upserts into Gold-A master tables.
For local dev, reads/writes Parquet files. Production uses Iceberg.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from wine_rec.common.io import write_parquet_atomic
from wine_rec.common.logging import get_logger


log = get_logger(__name__)


def enrich_impressions(
    impressions: pl.DataFrame,
    actions: pl.DataFrame,
    orders: pl.DataFrame,
) -> pl.DataFrame:
    """Enrich impressions with action/order aggregates.

    For each impression, compute:
        - n_actions: total actions taken
        - has_click: whether any CLICK action occurred
        - has_purchase: whether a matching order exists
        - max_action_type: highest-value action (order > cart > click > view)
    """
    action_value_map = {"VIEW": 1, "CLICK": 2, "DWELL": 3, "LIKE": 4, "WISHLIST": 5, "CART": 6}

    # action aggregates per impression
    if len(actions) > 0:
        action_agg = actions.group_by("impression_id").agg(
            pl.len().alias("n_actions"),
            (pl.col("action_type") == "CLICK").any().alias("has_click"),
            (pl.col("action_type") == "CART").any().alias("has_cart"),
            pl.col("action_type")
            .replace_strict(action_value_map, default=0)
            .max()
            .alias("max_action_value"),
        )
    else:
        action_agg = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "n_actions": pl.UInt32,
                "has_click": pl.Boolean,
                "has_cart": pl.Boolean,
                "max_action_value": pl.Int64,
            }
        )

    # order flag per impression
    if len(orders) > 0 and "impression_id" in orders.columns:
        order_agg = (
            orders.filter(pl.col("impression_id").is_not_null())
            .group_by("impression_id")
            .agg(pl.lit(True).alias("has_purchase"))
        )
    else:
        order_agg = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "has_purchase": pl.Boolean,
            }
        )

    return (
        impressions.join(action_agg, on="impression_id", how="left")
        .join(order_agg, on="impression_id", how="left")
        .with_columns(
            pl.col("n_actions").fill_null(0),
            pl.col("has_click").fill_null(False),
            pl.col("has_cart").fill_null(False),
            pl.col("has_purchase").fill_null(False),
            pl.col("max_action_value").fill_null(0),
        )
    )


def compute_user_profiles(
    _actions: pl.DataFrame,
    orders: pl.DataFrame,
    existing_profiles: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Compute/update user profiles from event data.

    Aggregates per user:
        - purchase_count, total_spend
        - action counts by type
        - most recent activity timestamp
    """
    # from orders
    if len(orders) > 0:
        order_stats = orders.group_by("user_id").agg(
            pl.len().alias("order_count"),
            pl.col("quantity").sum().alias("total_quantity"),
            pl.col("price").sum().alias("total_spend"),
        )
    else:
        order_stats = pl.DataFrame(
            schema={
                "user_id": pl.Utf8,
                "order_count": pl.UInt32,
                "total_quantity": pl.Int64,
                "total_spend": pl.Float64,
            }
        )

    # from actions — need user_id via impression join
    # for now, return order-based profiles
    profiles = order_stats.with_columns(
        pl.col("total_spend").fill_null(0.0),
        pl.col("total_quantity").fill_null(0),
    )

    if existing_profiles is not None and len(existing_profiles) > 0:
        # Snapshot merge: new data supersedes existing for users present in
        # the current batch.  Users absent from the new batch retain their
        # existing profile (coalesce: new wins, old as fallback).
        merged_cols = ["order_count", "total_quantity", "total_spend"]
        profiles = (
            existing_profiles.join(profiles, on="user_id", how="full", suffix="_new")
            .with_columns(pl.coalesce(f"{c}_new", c).alias(c) for c in merged_cols)
            .select("user_id", *merged_cols)
        )

    return profiles


def run_silver_to_gold_a(*, input_path: str, output_path: str, dt: str) -> dict[str, int]:
    """Build enriched Gold-A tables from Silver events.

    Args:
        input_path: Silver root path
        output_path: Gold-A output root path
        dt: Processing date

    Returns:
        Dict mapping table name to row count.
    """
    silver = Path(input_path)
    gold_a = Path(output_path)
    results: dict[str, int] = {}

    # find latest Silver partitions
    def _read_latest(log_type: str) -> pl.DataFrame | None:
        base = silver / log_type
        if not base.exists():
            return None
        # try partitioned first, then flat
        parts = sorted(base.glob("dt=*/data.parquet"))
        if parts:
            return pl.read_parquet(parts[-1])
        flat = base / "data.parquet"
        if flat.exists():
            return pl.read_parquet(flat)
        return None

    impressions = _read_latest("impression_log_v1")
    actions = _read_latest("action_log_v1")
    orders = _read_latest("order_log_v1")

    if impressions is None:
        log.warning("no_impressions", msg="No impression data found in Silver")
        return results

    if actions is None:
        actions = pl.DataFrame(
            schema={
                "impression_id": pl.Utf8,
                "wine_core_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
                "action_type": pl.Utf8,
            }
        )

    if orders is None:
        orders = pl.DataFrame(
            schema={
                "order_id": pl.Utf8,
                "user_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
                "impression_id": pl.Utf8,
            }
        )

    # Enriched impressions
    log.info("enriching_impressions")
    enriched = enrich_impressions(impressions, actions, orders)
    out_path = gold_a / "enriched_impressions_v1" / f"dt={dt}" / "data.parquet"
    write_parquet_atomic(enriched, out_path)
    results["enriched_impressions_v1"] = len(enriched)

    # User profiles (incremental)
    log.info("computing_user_profiles")
    existing = None
    profile_path = gold_a / "user_profile_computed_v1" / "data.parquet"
    if profile_path.exists():
        existing = pl.read_parquet(profile_path)

    profiles = compute_user_profiles(actions, orders, existing)
    write_parquet_atomic(profiles, profile_path)
    results["user_profile_computed_v1"] = len(profiles)

    log.info("silver_to_gold_a_done", results=results)
    return results
