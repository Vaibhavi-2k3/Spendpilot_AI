
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.recommendation import Recommendation
from app.models.shopping_session import ShoppingSession
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation_service import generate_recommendations


router = APIRouter(
    prefix="/api/shopping-sessions",
    tags=["Recommendations"],
)


@router.post(
    "/{session_id}/recommendations",
    response_model=list[RecommendationResponse],
)
def create_recommendations(
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

    return generate_recommendations(
        shopping_session=shopping_session,
        db=db,
    )


@router.get(
    "/{session_id}/recommendations",
    response_model=list[RecommendationResponse],
)
def list_recommendations(
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

    recommendations = db.scalars(
        select(Recommendation)
        .where(
            Recommendation.shopping_session_id
            == session_id
        )
        .order_by(
            Recommendation.score.desc(),
            Recommendation.product_id.asc(),
        )
    ).all()

    return list(recommendations)
