from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from app.providers.gemini_provider import GeminiError, GeminiProvider
from app.schemas.intelligence import (
    AIComparisonResponse, GroundedComparison, IntentResponse, ShoppingIntent,
)
from app.services.product_comparison import load_product_comparison
from app.services.shopping_intelligence import (
    comparison_context, comparison_response, context_fingerprint,
    fallback_comparison, original_intent, validate_grounding,
)


router = APIRouter(prefix="/api/shopping-sessions", tags=["Shopping Intelligence"])


def get_gemini_provider() -> GeminiProvider | None:
    settings = get_settings()
    key = settings.gemini_api_key
    if key is None or not key.get_secret_value().strip():
        return None
    return GeminiProvider(key.get_secret_value().strip(), settings.gemini_model)


def get_session(db: Session, session_id: str, lock: bool = False):
    statement = select(ShoppingSession).where(ShoppingSession.id == session_id)
    if lock:
        statement = statement.with_for_update()
    shopping_session = db.scalar(statement.execution_options(populate_existing=True))
    if shopping_session is None:
        raise HTTPException(status_code=404, detail="Shopping session not found")
    return shopping_session


@router.post("/{session_id}/intent", response_model=IntentResponse)
def understand_shopping_intent(
    session_id: str,
    db: Session = Depends(get_db),
    provider: GeminiProvider | None = Depends(get_gemini_provider),
):
    shopping_session = get_session(db, session_id)
    if shopping_session.intent:
        return IntentResponse(
            provider="gemini", status="ready",
            intent=ShoppingIntent.model_validate(shopping_session.intent),
        )

    query = shopping_session.query
    budget, currency = shopping_session.budget_amount, shopping_session.currency
    fallback = IntentResponse(
        provider="rule_based", status="unavailable", intent=original_intent(query),
        message="Gemini is not configured. Using your original search request.",
    )
    if provider is None:
        return fallback

    if db.scalar(select(Product.id).where(
        Product.shopping_session_id == session_id,
    ).limit(1)) is not None:
        raise HTTPException(
            status_code=409,
            detail="Analyze shopping intent before discovering products",
        )

    # Release the read transaction/connection before the external model request.
    db.rollback()
    try:
        intent = provider.understand_intent(query, budget, currency)
    except GeminiError:
        return fallback.model_copy(update={
            "message": "Gemini is temporarily unavailable. Using your original search request.",
        })

    try:
        shopping_session = get_session(db, session_id, lock=True)
        if shopping_session.intent:
            intent = ShoppingIntent.model_validate(shopping_session.intent)
        else:
            if db.scalar(select(Product.id).where(
                Product.shopping_session_id == session_id,
            ).limit(1)) is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Analyze shopping intent before discovering products",
                )
            shopping_session.intent = intent.model_dump()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return IntentResponse(provider="gemini", status="ready", intent=intent)


@router.post("/{session_id}/ai-comparison", response_model=AIComparisonResponse)
def explain_product_comparison(
    session_id: str,
    db: Session = Depends(get_db),
    provider: GeminiProvider | None = Depends(get_gemini_provider),
):
    shopping_session = get_session(db, session_id)
    products = load_product_comparison(session_id, db)[:5]
    if not products:
        return fallback_comparison([], "empty", "Generate eligible recommendations first.")

    context = comparison_context(shopping_session, products)
    fingerprint = context_fingerprint(context)
    cached = shopping_session.ai_comparison
    if (
        cached and cached.get("fingerprint") == fingerprint
        and (provider is None or cached.get("model") == provider.model)
    ):
        return comparison_response(GroundedComparison.model_validate(cached["report"]))

    if provider is None:
        return fallback_comparison(
            products, "unavailable", "Gemini is not configured. Showing rule-based recommendations.",
        )

    db.rollback()
    try:
        report = provider.compare(context)
        validate_grounding(report, context)
    except GeminiError:
        return fallback_comparison(
            products, "unavailable",
            "Gemini could not produce a grounded comparison. Showing rule-based recommendations.",
        )

    try:
        shopping_session = get_session(db, session_id, lock=True)
        current_products = load_product_comparison(session_id, db)[:5]
        if context_fingerprint(comparison_context(shopping_session, current_products)) != fingerprint:
            db.rollback()
            return fallback_comparison(
                current_products, "stale",
                "Listings changed during AI analysis. Request a new comparison.",
            )
        shopping_session.ai_comparison = {
            "fingerprint": fingerprint, "model": provider.model,
            "report": report.model_dump(),
        }
        db.commit()
    except Exception:
        db.rollback()
        raise
    return comparison_response(report)
