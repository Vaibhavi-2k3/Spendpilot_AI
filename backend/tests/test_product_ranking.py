
from decimal import Decimal

from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from app.services.product_ranking import rank_products


def make_session(
    query="wireless headphones",
    budget=100,
    currency="USD",
):
    return ShoppingSession(
        query=query,
        budget_amount=budget,
        currency=currency,
        status="created",
    )


def make_product(
    name,
    price,
    description="",
    currency="USD",
    availability="in_stock",
    source_type="demo_catalog",
):
    return Product(
        shopping_session_id="test-session",
        name=name,
        description=description,
        price=Decimal(str(price)),
        currency=currency,
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/product",
        image_url=None,
        availability=availability,
        source_type=source_type,
    )


def test_relevance_has_priority_over_lower_price():
    session = make_session()

    headphones = make_product(
        "Wireless Headphones",
        "79.99",
    )

    mouse = make_product(
        "Wireless Mouse",
        "19.99",
    )

    ranked = rank_products(
        session,
        [mouse, headphones],
    )

    assert ranked[0].product.name == "Wireless Headphones"
    assert ranked[0].score > ranked[1].score


def test_products_over_budget_are_excluded():
    session = make_session(budget=50)

    products = [
        make_product("Wireless Headphones", "79.99"),
        make_product("Wireless Earbuds", "39.99"),
    ]

    ranked = rank_products(session, products)

    assert len(ranked) == 1
    assert ranked[0].product.name == "Wireless Earbuds"


def test_unavailable_products_are_excluded():
    session = make_session()

    product = make_product(
        "Wireless Headphones",
        "49.99",
        availability="out_of_stock",
    )

    assert rank_products(session, [product]) == []


def test_different_currency_is_excluded():
    session = make_session(currency="USD")

    product = make_product(
        "Wireless Headphones",
        "49.99",
        currency="INR",
    )

    assert rank_products(session, [product]) == []


def test_negative_price_is_excluded():
    session = make_session()

    product = make_product(
        "Wireless Headphones",
        "-10.00",
    )

    assert rank_products(session, [product]) == []


def test_ranking_is_independent_of_input_order():
    session = make_session()

    headphones = make_product(
        "Wireless Headphones",
        "79.99",
    )

    earbuds = make_product(
        "Wireless Earbuds",
        "39.99",
    )

    first = rank_products(
        session,
        [headphones, earbuds],
    )

    second = rank_products(
        session,
        [earbuds, headphones],
    )

    assert [
        item.product.name for item in first
    ] == [
        item.product.name for item in second
    ]


def test_scores_are_between_zero_and_one():
    session = make_session()

    products = [
        make_product("Wireless Headphones", "79.99"),
        make_product("Wireless Earbuds", "39.99"),
        make_product("Gaming Keyboard", "59.99"),
    ]

    ranked = rank_products(session, products)

    assert all(
        0 <= item.score <= 1
        for item in ranked
    )


def test_empty_product_list():
    session = make_session()

    assert rank_products(session, []) == []


def test_cheap_but_unrelated_product_is_not_recommended():
    session = make_session(query="headphones")
    product = make_product("Garden Rake", "5.00")

    assert rank_products(session, [product]) == []


def test_unknown_availability_is_eligible_for_ranking():
    session = make_session()

    product = make_product(
        "Wireless Headphones",
        "79.99",
        availability="unknown",
    )

    ranked = rank_products(session, [product])

    assert len(ranked) == 1
    assert ranked[0].product.name == "Wireless Headphones"
    assert "not been verified" in ranked[0].reasoning


def test_external_product_has_checkout_disclaimer():
    session = make_session(
        budget=5000,
        currency="INR",
    )

    product = make_product(
        "Wireless Headphones",
        "2299",
        currency="INR",
        availability="unknown",
        source_type="serpapi_google_shopping",
    )

    ranked = rank_products(session, [product])

    assert len(ranked) == 1
    assert "comparison only" in ranked[0].reasoning
    assert "not eligible" in ranked[0].reasoning


def test_unknown_availability_still_respects_budget():
    session = make_session(
        budget=5000,
        currency="INR",
    )

    product = make_product(
        "Wireless Headphones",
        "5999",
        currency="INR",
        availability="unknown",
    )

    assert rank_products(session, [product]) == []


def test_unsupported_availability_is_excluded():
    session = make_session()

    product = make_product(
        "Wireless Headphones",
        "49.99",
        availability="discontinued",
    )

    assert rank_products(session, [product]) == []


def test_in_stock_demo_product_has_no_external_disclaimer():
    session = make_session()

    product = make_product(
        "Wireless Headphones",
        "79.99",
        availability="in_stock",
    )

    ranked = rank_products(session, [product])

    assert len(ranked) == 1
    assert "comparison only" not in ranked[0].reasoning
    assert "not been verified" not in ranked[0].reasoning
