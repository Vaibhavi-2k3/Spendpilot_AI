
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.shopping_session import ShoppingSession
from app.schemas.shopping_session import (
    ShoppingSessionCreate,
    ShoppingSessionResponse,
)


router = APIRouter(
    prefix="/api/shopping-sessions",
    tags=["Shopping Sessions"],
)


@router.post(
    "",
    response_model=ShoppingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_shopping_session(
    payload: ShoppingSessionCreate,
    db: Session = Depends(get_db),
):
    shopping_session = ShoppingSession(
        query=payload.query,
        budget_amount=payload.budget_amount,
        currency=payload.currency,
        status="created",
    )

    db.add(shopping_session)

    try:
        db.commit()
        db.refresh(shopping_session)
    except Exception:
        db.rollback()
        raise

    return shopping_session


@router.get(
    "/{session_id}",
    response_model=ShoppingSessionResponse,
)
def get_shopping_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    shopping_session = db.get(ShoppingSession, session_id)

    if shopping_session is None:
        raise HTTPException(
            status_code=404,
            detail="Shopping session not found",
        )

    return shopping_session
