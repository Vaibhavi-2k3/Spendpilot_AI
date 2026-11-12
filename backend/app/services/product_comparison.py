from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.recommendation import Recommendation
from app.schemas.comparison import ComparisonProductResponse


def load_product_comparison(
    session_id: str, db: Session,
) -> list[ComparisonProductResponse]:
    rows = db.execute(
        select(Recommendation, Product)
        .join(Product, Recommendation.product_id == Product.id)
        .where(
            Recommendation.shopping_session_id == session_id,
            Product.shopping_session_id == session_id,
        )
        .order_by(
            Recommendation.score.desc(), Product.price.asc(), Product.id.asc(),
        )
        .execution_options(populate_existing=True)
    ).all()

    results = []
    for recommendation, product in rows:
        is_demo = product.source_type == "demo_catalog"
        results.append(ComparisonProductResponse(
            product_id=product.id,
            recommendation_id=recommendation.id,
            shopping_session_id=session_id,
            name=product.name,
            description=product.description,
            price=product.price,
            currency=product.currency,
            merchant=product.merchant,
            product_url=product.product_url,
            image_url=product.image_url,
            availability=product.availability,
            source_type=product.source_type,
            score=recommendation.score,
            reasoning=recommendation.reasoning,
            checkout_eligible=is_demo and product.availability == "in_stock",
            link_type="demo_product" if is_demo else "shopping_discovery",
            created_at=product.created_at,
        ))
    return results
