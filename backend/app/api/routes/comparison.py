
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.shopping_session import ShoppingSession
from app.schemas.comparison import ComparisonProductResponse
from app.services.product_comparison import load_product_comparison


router = APIRouter(
    prefix="/api/shopping-sessions",
    tags=["Comparison"],
)


@router.get(
    "/{session_id}/comparison",
    response_model=list[ComparisonProductResponse],
)
def get_product_comparison(
    session_id: str,
    db: Session = Depends(get_db),
):
    shopping_session = db.get(
        ShoppingSession,
        session_id,
    )

    if shopping_session is None:
        raise HTTPException(
            status_code=404,
            detail="Shopping session not found",
        )

    return load_product_comparison(session_id, db)
