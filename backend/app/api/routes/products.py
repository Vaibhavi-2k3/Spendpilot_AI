
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from app.providers.demo_catalog import DemoCatalogProvider
from app.providers.serpapi_provider import SerpApiProvider
from app.schemas.product import ProductResponse
from app.services.product_discovery import DiscoveryContextChanged, discover_products


router = APIRouter(
    prefix="/api/shopping-sessions",
    tags=["Products"],
)


@router.get(
    "/{session_id}/products",
    response_model=list[ProductResponse],
)
def list_session_products(
    session_id: str,
    db: Session = Depends(get_db),
):
    shopping_session = db.get(ShoppingSession, session_id)

    if shopping_session is None:
        raise HTTPException(
            status_code=404,
            detail="Shopping session not found",
        )

    products = db.scalars(
        select(Product)
        .where(Product.shopping_session_id == session_id)
        .order_by(Product.created_at.desc())
    ).all()

    return products


@router.post(
    "/{session_id}/discover",
    response_model=list[ProductResponse],
)
async def discover_session_products(
    session_id: str,
    source: Literal["demo", "serpapi"] = Query(
        default="demo",
        description="Product discovery source",
    ),
    db: Session = Depends(get_db),
):
    shopping_session = db.get(ShoppingSession, session_id)

    if shopping_session is None:
        raise HTTPException(
            status_code=404,
            detail="Shopping session not found",
        )

    if source == "serpapi":
        settings = get_settings()

        if not settings.serpapi_api_key:
            raise HTTPException(
                status_code=503,
                detail="Live product discovery is not configured",
            )

        provider = SerpApiProvider(
            api_key=settings.serpapi_api_key,
        )
    else:
        provider = DemoCatalogProvider()

    try:
        products = await discover_products(
            shopping_session=shopping_session,
            db=db,
            provider=provider,
        )
    except DiscoveryContextChanged as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        if source == "serpapi":
            raise HTTPException(
                status_code=502,
                detail="Live product discovery is temporarily unavailable",
            ) from None

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None

    return products
