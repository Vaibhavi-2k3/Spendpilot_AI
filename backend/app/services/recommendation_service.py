
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.shopping_session import ShoppingSession
from app.services.product_ranking import rank_products


def generate_recommendations(
    shopping_session: ShoppingSession,
    db: Session,
) -> list[Recommendation]:
    # Serialize writers for this session, including discovery refreshes.
    db.execute(
        select(ShoppingSession.id)
        .where(ShoppingSession.id == shopping_session.id)
        .with_for_update()
    ).scalar_one()

    products = db.scalars(
        select(Product)
        .where(Product.shopping_session_id == shopping_session.id)
        .execution_options(populate_existing=True)
    ).all()

    ranked_products = rank_products(
        shopping_session,
        list(products),
    )

    existing_recommendations = db.scalars(
        select(Recommendation).where(
            Recommendation.shopping_session_id
            == shopping_session.id
        ).execution_options(populate_existing=True)
    ).all()

    existing_by_product_id = {
        recommendation.product_id: recommendation
        for recommendation in existing_recommendations
    }

    ranked_product_ids = {
        item.product.id for item in ranked_products
    }

    # Remove recommendations for products that are no longer eligible.
    for recommendation in existing_recommendations:
        if recommendation.product_id not in ranked_product_ids:
            db.delete(recommendation)

    results = []

    for item in ranked_products:
        recommendation = existing_by_product_id.get(
            item.product.id
        )

        if recommendation is None:
            recommendation = Recommendation(
                shopping_session_id=shopping_session.id,
                product_id=item.product.id,
                score=item.score,
                reasoning=item.reasoning,
            )
            db.add(recommendation)
        else:
            recommendation.score = item.score
            recommendation.reasoning = item.reasoning

        results.append(recommendation)

    try:
        db.commit()

        for recommendation in results:
            db.refresh(recommendation)

    except Exception:
        db.rollback()
        raise

    return results
