
import asyncio
from dataclasses import replace
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.models.shopping_session import ShoppingSession
from app.models.product import Product
from app.providers.base import DiscoveredProduct
from app.services.product_discovery import discover_products


def make_session():
    return ShoppingSession(
        id="test-session",
        query="wireless headphones",
        budget_amount=100,
        currency="USD",
        status="created",
    )


def make_product(
    price=Decimal("79.99"),
    currency="USD",
):
    return DiscoveredProduct(
        name="Wireless Headphones",
        description="Bluetooth headphones",
        price=price,
        currency=currency,
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/headphones",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
    )


def make_provider(products):
    provider = MagicMock()

    async def search(*args, **kwargs):
        return products

    provider.search.side_effect = search
    return provider


def test_discovery_saves_products():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    db.execute.return_value.scalar_one.return_value = make_session()

    provider = make_provider([make_product()])

    results = asyncio.run(
        discover_products(make_session(), db, provider)
    )

    assert len(results) == 1
    assert results[0].name == "Wireless Headphones"
    assert results[0].shopping_session_id == "test-session"

    db.add_all.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


def test_discovery_rejects_over_budget_product():
    db = MagicMock()
    provider = make_provider(
        [make_product(price=Decimal("150.00"))]
    )

    with pytest.raises(ValueError, match="over budget"):
        asyncio.run(
            discover_products(make_session(), db, provider)
        )

    db.add_all.assert_not_called()
    db.commit.assert_not_called()


def test_discovery_skips_duplicate_products():
    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = make_session()

    discovered = make_product()
    existing_product = Product(
        id="existing-product", shopping_session_id="test-session",
        **discovered.__dict__,
    )

    db.scalars.return_value.all.return_value = [
        existing_product
    ]

    provider = make_provider([make_product()])

    results = asyncio.run(
        discover_products(make_session(), db, provider)
    )

    assert len(results) == 1
    assert results[0] is existing_product
    db.add_all.assert_not_called()
    db.commit.assert_called_once()
    assert existing_product.last_seen_at is not None
    # The only statement executed is the session lock, not invalidation.
    assert db.execute.call_count == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"price": Decimal("NaN")},
        {"price": Decimal("Infinity")},
        {"price": Decimal("-1")},
        {"price": Decimal("10000000000")},
        {"price": Decimal("1.001")},
        {"name": "x" * 256},
        {"merchant": "x" * 101},
    ],
)
def test_discovery_rejects_invalid_batch_before_any_write(changes):
    db = MagicMock()
    invalid = replace(make_product(), **changes)

    with pytest.raises(ValueError):
        asyncio.run(discover_products(
            make_session(), db, make_provider([make_product(), invalid]),
        ))

    db.execute.assert_not_called()
    db.add_all.assert_not_called()
    db.commit.assert_not_called()


def test_discovery_rolls_back_on_commit_failure():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    db.execute.return_value.scalar_one.return_value = make_session()
    db.commit.side_effect = RuntimeError("Database error")

    provider = make_provider([make_product()])

    with pytest.raises(RuntimeError, match="Database error"):
        asyncio.run(
            discover_products(make_session(), db, provider)
        )

    db.rollback.assert_called_once()
