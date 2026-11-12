import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.shopping_session import ShoppingSession
from app.providers.base import DiscoveredProduct
from app.services.product_discovery import DiscoveryContextChanged, discover_products
from app.services.recommendation_service import generate_recommendations
from tests.test_database_config import get_test_database_url


def make_listing(**changes):
    listing = DiscoveredProduct(
        name="Wireless Headphones", description="Bluetooth headphones",
        price=Decimal("79.99"), currency="USD", merchant="Example Electronics",
        product_url="https://example.com/headphones", image_url=None,
        availability="unknown", source_type="serpapi_google_shopping",
    )
    return replace(listing, **changes)


def provider_for(*listings):
    return SimpleNamespace(search=AsyncMock(return_value=list(listings)))


@pytest.fixture
def persisted_session():
    """Real commits let independent connections exercise row locks."""
    engine = create_engine(
        get_test_database_url(), pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": "-c lock_timeout=10000"},
    )
    session_id = None
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one() == "spendpilot_test_db"

        with Session(engine) as db:
            shopping_session = ShoppingSession(
                query="wireless headphones", budget_amount=100, currency="USD",
            )
            db.add(shopping_session)
            db.commit()
            session_id = shopping_session.id

        yield engine, session_id
    finally:
        if session_id is not None:
            with Session(engine) as db:
                db.execute(delete(ShoppingSession).where(
                    ShoppingSession.id == session_id,
                ))
                db.commit()
        engine.dispose()


def test_refresh_preserves_identity_and_invalidates_stale_recommendations(
    persisted_session,
):
    engine, session_id = persisted_session
    with Session(engine) as db:
        shopping_session = db.get(ShoppingSession, session_id)
        first = asyncio.run(discover_products(
            shopping_session, db, provider_for(make_listing()),
        ))[0]
        product_id, created_at = first.id, first.created_at
        first.last_seen_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()
        assert len(generate_recommendations(shopping_session, db)) == 1

        refreshed = asyncio.run(discover_products(
            shopping_session, db,
            provider_for(make_listing(
                price=Decimal("89.99"), availability="out_of_stock",
                description="Updated provider description",
            )),
        ))

        assert len(refreshed) == 1
        assert refreshed[0].id == product_id
        assert refreshed[0].created_at == created_at
        assert refreshed[0].price == Decimal("89.99")
        assert refreshed[0].availability == "out_of_stock"
        assert refreshed[0].description == "Updated provider description"
        assert refreshed[0].last_seen_at.year > 2000
        assert db.scalar(select(func.count()).select_from(Recommendation).where(
            Recommendation.shopping_session_id == session_id,
        )) == 0
        assert generate_recommendations(shopping_session, db) == []


def test_concurrent_discoveries_reuse_the_same_product(persisted_session):
    engine, session_id = persisted_session
    barrier = Barrier(2)

    async def search(**kwargs):
        barrier.wait(timeout=10)
        return [make_listing(), make_listing()]

    def discover():
        with Session(engine) as db:
            shopping_session = db.get(ShoppingSession, session_id)
            products = asyncio.run(discover_products(
                shopping_session, db, SimpleNamespace(search=search),
            ))
            return [product.id for product in products]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: discover(), range(2)))

    assert len(first) == 1
    assert first == second
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Product).where(
            Product.shopping_session_id == session_id,
        )) == 1


def test_intent_change_during_search_requires_retry_without_saving_wrong_results(
    persisted_session,
):
    engine, session_id = persisted_session

    async def change_intent(**kwargs):
        # Commit on an independent connection, as a simultaneous intent request
        # would. Rolling back the discovery transaction must not undo this write.
        with Session(engine) as other_db:
            session = other_db.get(ShoppingSession, session_id)
            session.intent = {
                "search_query": "noise cancelling headphones",
                "use_case": "commuting", "preferences": ["noise cancellation"],
            }
            other_db.commit()
        return [make_listing()]

    with Session(engine) as db:
        shopping_session = db.get(ShoppingSession, session_id)
        with pytest.raises(DiscoveryContextChanged):
            asyncio.run(discover_products(
                shopping_session, db, SimpleNamespace(search=change_intent),
            ))
        assert db.scalar(select(func.count()).select_from(Product).where(
            Product.shopping_session_id == session_id,
        )) == 0
        assert shopping_session.discovery_query == "noise cancelling headphones"
        assert len(asyncio.run(discover_products(
            shopping_session, db, provider_for(make_listing()),
        ))) == 1


def test_concurrent_recommendations_reuse_the_same_row(persisted_session):
    engine, session_id = persisted_session
    with Session(engine) as db:
        asyncio.run(discover_products(
            db.get(ShoppingSession, session_id), db, provider_for(make_listing()),
        ))

    barrier = Barrier(2)

    def recommend():
        with Session(engine) as db:
            shopping_session = db.get(ShoppingSession, session_id)
            barrier.wait(timeout=10)
            return [item.id for item in generate_recommendations(
                shopping_session, db,
            )]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: recommend(), range(2)))

    assert len(first) == 1
    assert first == second
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Recommendation).where(
            Recommendation.shopping_session_id == session_id,
        )) == 1


@pytest.mark.parametrize("entity", ["product", "recommendation"])
def test_database_rejects_duplicate_rows(persisted_session, entity):
    engine, session_id = persisted_session
    with Session(engine) as db:
        shopping_session = db.get(ShoppingSession, session_id)
        product = asyncio.run(discover_products(
            shopping_session, db, provider_for(make_listing()),
        ))[0]
        generate_recommendations(shopping_session, db)

        if entity == "product":
            duplicate = Product(
                shopping_session_id=session_id, **make_listing().__dict__,
            )
        else:
            duplicate = Recommendation(
                shopping_session_id=session_id, product_id=product.id,
                score=0.9, reasoning="Duplicate",
            )

        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
