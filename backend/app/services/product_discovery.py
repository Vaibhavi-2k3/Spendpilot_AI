
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.shopping_session import ShoppingSession
from app.providers.base import ProductProvider


class DiscoveryContextChanged(ValueError):
    """The shopping request changed while the external search was in flight."""


async def discover_products(
    shopping_session: ShoppingSession,
    db: Session,
    provider: ProductProvider,
) -> list[Product]:
    query = getattr(shopping_session, "discovery_query", None) or shopping_session.query
    budget, currency = shopping_session.budget_amount, shopping_session.currency
    discovered = await provider.search(
        query=query, budget_amount=budget, currency=currency,
    )

    # Validate all results before modifying the database.
    for item in discovered:
        item.validate()

        if item.currency != currency:
            raise ValueError("Provider returned a different currency")

        if (
            budget is not None
            and item.price > budget
        ):
            raise ValueError("Provider returned a product over budget")

    try:
        # Discovery and recommendation writers share this lock. Acquire it
        # after the network request so concurrent searches can run in parallel.
        current_session = db.execute(
            select(ShoppingSession)
            .where(ShoppingSession.id == shopping_session.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        if (
            current_session.discovery_query != query
            or current_session.budget_amount != budget
            or current_session.currency != currency
        ):
            raise DiscoveryContextChanged(
                "Shopping intent changed during discovery. Retry discovery."
            )

        existing_products = list(db.scalars(
            select(Product)
            .where(Product.shopping_session_id == shopping_session.id)
            .execution_options(populate_existing=True)
        ).all())
        existing_by_url = {
            product.product_url: product for product in existing_products
        }

        new_products = []
        touched_products = []
        seen_urls = set()
        catalog_changed = False
        now = datetime.now(timezone.utc)

        for item in discovered:
            if item.product_url in seen_urls:
                continue
            seen_urls.add(item.product_url)

            values = {
                field: getattr(item, field)
                for field in (
                    "name", "description", "price", "currency", "merchant",
                    "product_url", "image_url", "availability", "source_type",
                )
            }
            product = existing_by_url.get(item.product_url)

            if product is None:
                product = Product(
                    shopping_session_id=shopping_session.id, **values,
                )
                new_products.append(product)
                catalog_changed = True
            else:
                for field, value in values.items():
                    if getattr(product, field) != value:
                        setattr(product, field, value)
                        catalog_changed = True

            product.last_seen_at = now
            touched_products.append(product)

        if new_products:
            db.add_all(new_products)

        # Scores and eligibility must be regenerated when a listing changes.
        if catalog_changed:
            shopping_session.ai_comparison = None
            db.execute(
                delete(Recommendation).where(
                    Recommendation.shopping_session_id == shopping_session.id
                )
            )

        db.commit()

        for product in touched_products:
            db.refresh(product)

    except Exception:
        db.rollback()
        raise

    return existing_products + new_products
