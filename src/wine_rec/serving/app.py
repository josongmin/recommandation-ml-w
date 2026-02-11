"""FastAPI application (RFC-INFRA-IMPL-013 §1-6)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from wine_rec import __version__
from wine_rec.serving.deps import get_feature_store
from wine_rec.serving.recommender import Recommender


if TYPE_CHECKING:
    from wine_rec.contracts.feature_store import FeatureStore


app = FastAPI(title="wine-rec", version=__version__)


# ── Request / Response ──


class RecommendRequest(BaseModel):
    """Recommendation request."""

    user_id: str
    n_items: int = Field(default=10, ge=1, le=100)
    context: dict[str, Any] = Field(default_factory=dict)


class RecommendedItem(BaseModel):
    """Single recommended item."""

    wine_sku_id: str
    score: float
    explanation: str = ""


class RecommendResponse(BaseModel):
    """Recommendation response."""

    items: list[RecommendedItem]
    model_version: str
    feature_set_version: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str


# ── Endpoints ──


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check."""
    return HealthResponse(version=__version__)


@app.post("/recommend", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    feature_store: FeatureStore = Depends(get_feature_store),  # noqa: B008
) -> RecommendResponse:
    """Generate wine recommendations for a user."""
    recommender = Recommender(feature_store=feature_store)
    raw_items = recommender.recommend(
        user_id=req.user_id,
        n_items=req.n_items,
        context=req.context,
    )
    items = [
        RecommendedItem(
            wine_sku_id=item["wine_sku_id"],
            score=item["score"],
        )
        for item in raw_items
    ]
    return RecommendResponse(
        items=items,
        model_version="v0",
        feature_set_version="v0",
    )
