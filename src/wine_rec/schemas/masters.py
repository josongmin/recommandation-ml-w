"""SSOT Master schemas (RFC-SSOT-IR-001)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WineCoreMaster(BaseModel):
    """wine_core_master_v1 — taste learning unit SSOT."""

    wine_core_id: str
    canonical_name: str
    producer: str
    region: str
    sub_region: str | None = None
    variety: list[str]
    wine_type: str = Field(description="red|white|rose|sparkling|fortified|dessert")
    country: str
    appellation: str | None = None
    created_at: datetime
    updated_at: datetime


class WineSkuMaster(BaseModel):
    """wine_sku_master_v1 — sales/stock unit SSOT."""

    wine_sku_id: str
    wine_core_id: str
    vintage_year: int | None = None
    bottle_size_ml: int = 750
    merchant: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewMaster(BaseModel):
    """review_master_v1 — review identity SSOT."""

    review_id: str
    wine_core_id: str
    author_id: str
    author_type: str = Field(description="critic|expert|user|anonymous")
    rating: float | None = None
    rating_scale: str | None = Field(default=None, description="100|5|20")
    text: str | None = None
    language: str = "en"
    published_at: datetime
    source: str
