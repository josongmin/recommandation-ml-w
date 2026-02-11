"""Seed data generator for local development & pipeline testing.

Generates realistic wine recommendation data:
- Wine masters (core + SKU)
- Reviews (critic/expert/user mix)
- User profiles
- Event logs (impression, action, order, policy)

Outputs Parquet files under data/ following S3 path conventions.

Usage:
    uv run python scripts/seed_data.py [--output-dir data] [--seed 42]
"""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl


# ── Domain vocabulary ──

COUNTRIES_REGIONS: dict[str, list[dict[str, str]]] = {
    "France": [
        {"region": "Bordeaux", "sub_region": "Pauillac", "appellation": "Pauillac AOC"},
        {
            "region": "Bordeaux",
            "sub_region": "Saint-Émilion",
            "appellation": "Saint-Émilion Grand Cru",
        },
        {"region": "Burgundy", "sub_region": "Côte de Nuits", "appellation": "Gevrey-Chambertin"},
        {"region": "Burgundy", "sub_region": "Côte de Beaune", "appellation": "Meursault"},
        {"region": "Champagne", "sub_region": "Épernay", "appellation": "Champagne AOC"},
        {"region": "Rhône", "sub_region": "Northern Rhône", "appellation": "Côte-Rôtie"},
        {"region": "Loire", "sub_region": "Sancerre", "appellation": "Sancerre AOC"},
    ],
    "Italy": [
        {
            "region": "Tuscany",
            "sub_region": "Chianti Classico",
            "appellation": "Chianti Classico DOCG",
        },
        {
            "region": "Tuscany",
            "sub_region": "Montalcino",
            "appellation": "Brunello di Montalcino DOCG",
        },
        {"region": "Piedmont", "sub_region": "Langhe", "appellation": "Barolo DOCG"},
        {"region": "Piedmont", "sub_region": "Langhe", "appellation": "Barbaresco DOCG"},
        {
            "region": "Veneto",
            "sub_region": "Valpolicella",
            "appellation": "Amarone della Valpolicella",
        },
    ],
    "Spain": [
        {"region": "Rioja", "sub_region": "Rioja Alta", "appellation": "Rioja DOCa"},
        {
            "region": "Ribera del Duero",
            "sub_region": "Pesquera",
            "appellation": "Ribera del Duero DO",
        },
        {"region": "Priorat", "sub_region": "Gratallops", "appellation": "DOQ Priorat"},
    ],
    "USA": [
        {"region": "Napa Valley", "sub_region": "Rutherford", "appellation": "Rutherford AVA"},
        {"region": "Napa Valley", "sub_region": "Oakville", "appellation": "Oakville AVA"},
        {
            "region": "Sonoma",
            "sub_region": "Russian River Valley",
            "appellation": "Russian River Valley AVA",
        },
        {
            "region": "Oregon",
            "sub_region": "Willamette Valley",
            "appellation": "Willamette Valley AVA",
        },
    ],
    "Australia": [
        {
            "region": "Barossa Valley",
            "sub_region": "Eden Valley",
            "appellation": "Barossa Valley GI",
        },
        {"region": "Margaret River", "sub_region": "Wilyabrup", "appellation": "Margaret River GI"},
    ],
    "Chile": [
        {"region": "Maipo Valley", "sub_region": "Alto Maipo", "appellation": "Valle del Maipo DO"},
    ],
    "New Zealand": [
        {"region": "Marlborough", "sub_region": "Wairau Valley", "appellation": "Marlborough GI"},
    ],
}

VARIETIES_BY_TYPE: dict[str, list[str]] = {
    "red": [
        "Cabernet Sauvignon",
        "Merlot",
        "Pinot Noir",
        "Syrah",
        "Grenache",
        "Sangiovese",
        "Nebbiolo",
        "Tempranillo",
        "Malbec",
        "Cabernet Franc",
        "Mourvèdre",
        "Zinfandel",
        "Petit Verdot",
        "Corvina",
    ],
    "white": [
        "Chardonnay",
        "Sauvignon Blanc",
        "Riesling",
        "Pinot Grigio",
        "Albariño",
        "Viognier",
        "Gewürztraminer",
        "Sémillon",
        "Chenin Blanc",
        "Grüner Veltliner",
        "Vermentino",
    ],
    "sparkling": ["Chardonnay", "Pinot Noir", "Pinot Meunier"],
    "rosé": ["Grenache", "Syrah", "Cinsault", "Mourvèdre"],
}

PRODUCERS: list[str] = [
    "Château Lafite Rothschild",
    "Château Latour",
    "Château Margaux",
    "Domaine de la Romanée-Conti",
    "Domaine Leroy",
    "Domaine Leflaive",
    "Opus One",
    "Screaming Eagle",
    "Ridge Vineyards",
    "Penfolds",
    "Antinori",
    "Sassicaia",
    "Gaja",
    "Giacomo Conterno",
    "Vega Sicilia",
    "Pingus",
    "Alvaro Palacios",
    "Cloudy Bay",
    "Felton Road",
    "Concha y Toro Don Melchor",
    "Henschke",
    "Torbreck",
    "Joseph Phelps",
    "Stag's Leap Wine Cellars",
    "Louis Roederer",
    "Krug",
    "Dom Pérignon",
    "E. Guigal",
    "M. Chapoutier",
    "Paul Jaboulet Aîné",
    "Domaine Weinbach",
    "Trimbach",
    "Zind-Humbrecht",
    "Ca' del Bosco",
    "Marchesi di Barolo",
    "Tenuta San Guido",
    "Almaviva",
    "Clos Apalta",
    "Montes",
]

WINE_TYPE_WEIGHTS = {
    "red": 0.50,
    "white": 0.25,
    "sparkling": 0.10,
    "rosé": 0.05,
    "fortified": 0.05,
    "dessert": 0.05,
}

SURFACES = ["home", "search", "detail", "cart", "push"]
ACTION_TYPES = ["VIEW", "CLICK", "DWELL", "LIKE", "WISHLIST", "CART"]
AUTHOR_TYPES_WEIGHTS = [("critic", 0.10), ("expert", 0.20), ("user", 0.60), ("anonymous", 0.10)]
REVIEW_SOURCES = [
    "vivino",
    "wine_enthusiast",
    "robert_parker",
    "james_suckling",
    "decanter",
    "first_party",
]

MERCHANTS = [
    "와인타임",
    "신세계 L&B",
    "롯데주류",
    "와인앤모어",
    "와인25",
    "프리미엄 와인 직수입",
    "에노테카 코리아",
]

# ── Data generation ──

NOW = datetime(2026, 2, 1, tzinfo=UTC)
BASE_TS = datetime(2025, 1, 1, tzinfo=UTC)


def _pick_weighted(items: list[str], weights: list[float]) -> str:
    return random.choices(items, weights=weights, k=1)[0]


def generate_wine_cores(n: int = 120) -> pl.DataFrame:
    """Generate wine core master data."""
    rows = []
    for i in range(n):
        country = random.choice(list(COUNTRIES_REGIONS.keys()))
        region_info = random.choice(COUNTRIES_REGIONS[country])

        wine_type = _pick_weighted(
            list(WINE_TYPE_WEIGHTS.keys()),
            list(WINE_TYPE_WEIGHTS.values()),
        )
        if wine_type in ("fortified", "dessert"):
            variety_pool = VARIETIES_BY_TYPE["red"] + VARIETIES_BY_TYPE["white"]
        else:
            variety_pool = VARIETIES_BY_TYPE.get(wine_type, VARIETIES_BY_TYPE["red"])

        n_varieties = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1], k=1)[0]
        varieties = random.sample(variety_pool, min(n_varieties, len(variety_pool)))
        producer = random.choice(PRODUCERS)

        rows.append(
            {
                "wine_core_id": f"core_{i:04d}",
                "canonical_name": f"{producer} {varieties[0]} {region_info['region']}",
                "producer": producer,
                "region": region_info["region"],
                "sub_region": region_info["sub_region"],
                "variety": ",".join(varieties),
                "wine_type": wine_type,
                "country": country,
                "appellation": region_info.get("appellation"),
                "created_at": (BASE_TS + timedelta(days=random.randint(0, 30))).isoformat(),
                "updated_at": (BASE_TS + timedelta(days=random.randint(30, 365))).isoformat(),
            }
        )

    return pl.DataFrame(rows)


def generate_wine_skus(cores_df: pl.DataFrame, avg_skus_per_core: float = 2.0) -> pl.DataFrame:
    """Generate wine SKU master data (vintage × merchant variants)."""
    rows = []
    core_ids = cores_df["wine_core_id"].to_list()

    for core_id in core_ids:
        n_skus = max(1, int(random.gauss(avg_skus_per_core, 1.0)))
        for _j in range(n_skus):
            vintage = random.choice([None, *range(2015, 2025)])
            rows.append(
                {
                    "wine_sku_id": f"sku_{len(rows):05d}",
                    "wine_core_id": core_id,
                    "vintage_year": vintage,
                    "bottle_size_ml": random.choice([375, 750, 750, 750, 1500]),
                    "merchant": random.choice(MERCHANTS),
                    "created_at": (BASE_TS + timedelta(days=random.randint(0, 60))).isoformat(),
                    "updated_at": (BASE_TS + timedelta(days=random.randint(60, 365))).isoformat(),
                }
            )

    return pl.DataFrame(rows)


def generate_authors(n_critics: int = 8, n_experts: int = 15, n_users: int = 180) -> pl.DataFrame:
    """Generate author/reviewer profiles."""
    rows = [
        *[{"author_id": f"critic_{i:03d}", "author_type": "critic"} for i in range(n_critics)],
        *[{"author_id": f"expert_{i:03d}", "author_type": "expert"} for i in range(n_experts)],
        *[{"author_id": f"user_{i:04d}", "author_type": "user"} for i in range(n_users)],
    ]
    return pl.DataFrame(rows)


def generate_reviews(
    cores_df: pl.DataFrame,
    authors_df: pl.DataFrame,
    n: int = 600,
) -> pl.DataFrame:
    """Generate review master data."""
    rows = []
    core_ids = cores_df["wine_core_id"].to_list()
    author_rows = authors_df.to_dicts()

    for i in range(n):
        author = random.choice(author_rows)
        author_type = author["author_type"]

        # rating scale varies by author type
        if author_type in ("critic", "expert"):
            rating_scale = random.choice(["100", "100", "20"])
            if rating_scale == "100":
                rating = round(random.gauss(89, 5), 1)
                rating = max(70.0, min(100.0, rating))
            else:
                rating = round(random.gauss(16, 2), 1)
                rating = max(10.0, min(20.0, rating))
        else:
            rating_scale = "5"
            rating = round(random.gauss(3.8, 0.8), 1)
            rating = max(1.0, min(5.0, rating))

        published_at = BASE_TS + timedelta(
            days=random.randint(0, 365),
            hours=random.randint(0, 23),
        )

        rows.append(
            {
                "review_id": f"rev_{i:05d}",
                "wine_core_id": random.choice(core_ids),
                "author_id": author["author_id"],
                "author_type": author_type,
                "rating": rating,
                "rating_scale": rating_scale,
                "text": None if random.random() < 0.1 else f"Sample review text #{i}",
                "language": random.choice(["en", "en", "en", "ko"]),
                "published_at": published_at.isoformat(),
                "source": random.choice(REVIEW_SOURCES),
            }
        )

    return pl.DataFrame(rows)


def generate_user_profiles(n: int = 200) -> pl.DataFrame:
    """Generate user profile data for feature engineering."""
    all_varieties = VARIETIES_BY_TYPE["red"] + VARIETIES_BY_TYPE["white"]
    all_regions = list({r["region"] for regions in COUNTRIES_REGIONS.values() for r in regions})

    rows = [
        {
            "user_id": f"user_{i:04d}",
            "price_elasticity": round(random.uniform(0.1, 2.0), 3),
            "avg_rating": round(random.gauss(3.8, 0.6), 2),
            "purchase_count": random.randint(0, 100),
            "review_count": random.randint(0, 30),
            "preferred_variety_top3": ",".join(random.sample(all_varieties, 3)),
            "preferred_region_top3": ",".join(random.sample(all_regions, min(3, len(all_regions)))),
            "signup_date": (BASE_TS - timedelta(days=random.randint(30, 730))).isoformat(),
        }
        for i in range(n)
    ]

    return pl.DataFrame(rows)


def generate_events(
    skus_df: pl.DataFrame,
    user_profiles_df: pl.DataFrame,
    n_impressions: int = 2000,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Generate event logs: impressions, actions, orders, policy logs."""
    sku_rows = skus_df.to_dicts()
    sku_to_core = {r["wine_sku_id"]: r["wine_core_id"] for r in sku_rows}
    sku_ids = list(sku_to_core.keys())
    user_ids = user_profiles_df["user_id"].to_list()

    impressions = []
    actions = []
    orders = []
    policies = []

    for i in range(n_impressions):
        imp_id = f"imp_{i:06d}"
        user_id = random.choice(user_ids)
        shown_ts = BASE_TS + timedelta(
            days=random.randint(0, 365),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        surface = random.choice(SURFACES)
        n_shown = random.randint(3, 12)
        shown_items = random.sample(sku_ids, min(n_shown, len(sku_ids)))

        impressions.append(
            {
                "impression_id": imp_id,
                "user_id": user_id,
                "shown_ts": shown_ts.isoformat(),
                "surface": surface,
                "items": ",".join(shown_items),
                "schema_version": "impression_log_v1",
            }
        )

        # policy log for this impression
        candidates = [
            {
                "wine_sku_id": sku_id,
                "score": round(random.uniform(0.01, 0.99), 4),
                "source": random.choice(["collaborative", "content", "graph", "popular"]),
            }
            for sku_id in shown_items
        ]

        propensity = round(random.uniform(0.05, 0.5), 4) if random.random() > 0.03 else None
        policies.append(
            {
                "impression_id": imp_id,
                "model_version": "baseline_v0",
                "feature_set_version": "fs_v1",
                "candidates_json": str(candidates),
                "exploration_policy": random.choice([None, "epsilon_greedy_0.1", "thompson"]),
                "propensity": propensity,
                "propensity_model": "logged" if propensity else None,
                "schema_version": "policy_log_v1",
            }
        )

        # user actions (some impressions → actions)
        if random.random() < 0.45:
            n_actions = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1], k=1)[0]
            for _ in range(n_actions):
                acted_sku = random.choice(shown_items)
                action_ts = shown_ts + timedelta(seconds=random.randint(1, 600))
                action_type = _pick_weighted(
                    ACTION_TYPES,
                    [0.35, 0.30, 0.15, 0.10, 0.05, 0.05],
                )
                actions.append(
                    {
                        "impression_id": imp_id,
                        "wine_core_id": sku_to_core.get(acted_sku, ""),
                        "wine_sku_id": acted_sku,
                        "action_type": action_type,
                        "action_ts": action_ts.isoformat(),
                        "dwell_ms": random.randint(500, 30000) if action_type == "DWELL" else None,
                        "schema_version": "action_log_v1",
                    }
                )

        # orders (subset of impressions → purchases)
        if random.random() < 0.08:
            ordered_sku = random.choice(shown_items)
            order_ts = shown_ts + timedelta(
                minutes=random.randint(5, 1440),
            )
            orders.append(
                {
                    "order_id": f"ord_{len(orders):05d}",
                    "user_id": user_id,
                    "wine_sku_id": ordered_sku,
                    "order_ts": order_ts.isoformat(),
                    "quantity": random.choices([1, 2, 3, 6], weights=[0.6, 0.2, 0.1, 0.1], k=1)[0],
                    "price": round(random.lognormvariate(11.0, 0.8), 0),  # KRW range
                    "impression_id": imp_id,
                    "schema_version": "order_log_v1",
                }
            )

    return (
        pl.DataFrame(impressions),
        pl.DataFrame(actions),
        pl.DataFrame(orders)
        if orders
        else pl.DataFrame(
            schema={
                "order_id": pl.Utf8,
                "user_id": pl.Utf8,
                "wine_sku_id": pl.Utf8,
                "order_ts": pl.Utf8,
                "quantity": pl.Int64,
                "price": pl.Float64,
                "impression_id": pl.Utf8,
                "schema_version": pl.Utf8,
            }
        ),
        pl.DataFrame(policies),
    )


def generate_ir_data(
    cores_df: pl.DataFrame,
    reviews_df: pl.DataFrame,
    skus_df: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """Generate IR (Intermediate Representation) data from masters."""
    core_ids = cores_df["wine_core_id"].to_list()
    as_of = NOW.isoformat()

    # Review Aggregate IR
    agg_rows = []
    for core_id in core_ids:
        core_reviews = reviews_df.filter(pl.col("wine_core_id") == core_id)
        n_reviews = len(core_reviews)
        if n_reviews > 0:
            ratings = core_reviews["rating"].to_list()
            mean_r = sum(ratings) / len(ratings)
            var_r = sum((r - mean_r) ** 2 for r in ratings) / max(len(ratings), 1)
        else:
            mean_r = 0.0
            var_r = 1.0

        agg_rows.append(
            {
                "wine_core_id": core_id,
                "weighted_rating_mean": round(mean_r, 2),
                "authority_weighted_count": n_reviews,
                "critic_consensus_score": round(1.0 / (var_r + 0.01), 4),
                "discrepancy_note": None if var_r < 5.0 else "High variance among reviewers",
                "as_of_ts": as_of,
            }
        )

    # Temporal IR
    temporal_rows = []
    for core_id in core_ids:
        vintage = random.choice(range(2010, 2024))
        drink_from = vintage + random.randint(2, 5)
        drink_to = drink_from + random.randint(3, 15)
        current_year = 2026
        if current_year < drink_from:
            stage = "too_young"
        elif current_year <= drink_to:
            stage = random.choice(["early", "peak", "peak"])
        else:
            stage = "past"

        temporal_rows.append(
            {
                "wine_core_id": core_id,
                "vintage_year": vintage,
                "drink_from_year": drink_from,
                "drink_to_year": drink_to,
                "current_stage": stage,
                "estimation_method": random.choice(["rule", "rule", "model", "expert"]),
                "confidence": round(random.uniform(0.4, 0.95), 2),
                "as_of_ts": as_of,
            }
        )

    # Scarcity IR
    scarcity_rows = [
        {
            "wine_core_id": core_id,
            "production_volume_est": random.choice([None, *range(500, 50000, 500)]),
            "rarity_score": round(random.betavariate(2, 5), 3),
            "market_scope": "global",
            "scarcity_version": "scarcity_v1",
        }
        for core_id in core_ids
    ]

    # SKU-level attrs
    sku_attr_rows = [
        {
            "wine_sku_id": row["wine_sku_id"],
            "wine_core_id": row["wine_core_id"],
            "median_price_by_market": round(random.lognormvariate(11.0, 0.8), 0),
            "in_stock": random.random() > 0.15,
            "as_of_ts": as_of,
        }
        for row in skus_df.to_dicts()
    ]

    return {
        "wine_review_aggregate_ir_v1": pl.DataFrame(agg_rows),
        "wine_temporal_ir_v1": pl.DataFrame(temporal_rows),
        "wine_scarcity_ir_v1": pl.DataFrame(scarcity_rows),
        "wine_sku_attr_ir_v1": pl.DataFrame(sku_attr_rows),
    }


def write_parquet(df: pl.DataFrame, path: Path) -> None:
    """Write DataFrame to Parquet, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
    print(f"  {path} ({len(df)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate seed data for wine-rec pipeline")
    parser.add_argument("--output-dir", default="data", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    out = Path(args.output_dir)

    print("Generating wine-rec seed data...\n")

    # ── Masters (Gold-A) ──
    print("[Gold-A] Master data")
    cores = generate_wine_cores(120)
    skus = generate_wine_skus(cores, avg_skus_per_core=2.0)
    authors = generate_authors()
    reviews = generate_reviews(cores, authors, n=600)

    write_parquet(cores, out / "gold_a" / "wine_core_master_v1" / "data.parquet")
    write_parquet(skus, out / "gold_a" / "wine_sku_master_v1" / "data.parquet")
    write_parquet(reviews, out / "gold_a" / "review_master_v1" / "data.parquet")

    # ── User profiles ──
    print("\n[Profiles] User data")
    profiles = generate_user_profiles(200)
    write_parquet(profiles, out / "profiles" / "user_profile_v1" / "data.parquet")

    # ── Bronze events ──
    print("\n[Bronze] Event logs")
    impressions, action_events, order_events, policy_events = generate_events(
        skus,
        profiles,
        n_impressions=2000,
    )
    write_parquet(impressions, out / "bronze" / "impression_log_v1" / "data.parquet")
    write_parquet(action_events, out / "bronze" / "action_log_v1" / "data.parquet")
    write_parquet(order_events, out / "bronze" / "order_log_v1" / "data.parquet")
    write_parquet(policy_events, out / "bronze" / "policy_log_v1" / "data.parquet")

    # ── IR data (Gold-B) ──
    print("\n[Gold-B] IR derivations")
    ir_data = generate_ir_data(cores, reviews, skus)
    for table_name, df in ir_data.items():
        write_parquet(df, out / "gold_b" / table_name / "data.parquet")

    # ── Summary ──
    print(f"\nSeed data generated in {out}/")
    print(f"  Cores: {len(cores)}, SKUs: {len(skus)}, Reviews: {len(reviews)}")
    print(f"  Users: {len(profiles)}")
    print(f"  Impressions: {len(impressions)}, Actions: {len(action_events)}")
    print(f"  Orders: {len(order_events)}, Policies: {len(policy_events)}")


if __name__ == "__main__":
    main()
