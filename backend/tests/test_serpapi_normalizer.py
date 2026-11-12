
from decimal import Decimal

import pytest

from app.providers.serpapi_normalizer import (
    normalize_shopping_results,
)


def make_product(
    price="$79.99",
    link="https://example.com/product",
):
    return {
        "title": "Wireless Headphones",
        "price": price,
        "source": "Example Electronics",
        "link": link,
        "snippet": "Bluetooth noise cancelling headphones",
        "thumbnail": "https://example.com/image.jpg",
    }


@pytest.mark.parametrize(
    "currency,price_text,expected_price",
    [
        ("USD", "$79.99", Decimal("79.99")),
        ("INR", "₹4,999", Decimal("4999")),
    ],
)
def test_normalize_valid_product(
    currency,
    price_text,
    expected_price,
):
    results = [
        make_product(price=price_text)
    ]

    products = normalize_shopping_results(
        results=results,
        currency=currency,
    )

    assert len(products) == 1

    product = products[0]

    assert product.name == "Wireless Headphones"
    assert product.price == expected_price
    assert product.currency == currency
    assert product.merchant == "Example Electronics"
    assert product.product_url == (
        "https://example.com/product"
    )
    assert product.availability == "unknown"
    assert product.source_type == (
        "serpapi_google_shopping"
    )


def test_normalize_filters_over_budget():
    results = [
        make_product(price="$150.00")
    ]

    products = normalize_shopping_results(
        results=results,
        currency="USD",
        budget_amount=100,
    )

    assert products == []


def test_normalize_removes_duplicate_urls():
    results = [
        make_product(),
        make_product(),
    ]

    products = normalize_shopping_results(
        results=results,
        currency="USD",
    )

    assert len(products) == 1


@pytest.mark.parametrize(
    "invalid_link",
    [
        "",
        "http://example.com/product",
        "javascript:alert(1)",
        "not-a-url",
        "https://user:password@example.com/product",
    ],
)
def test_normalize_rejects_invalid_links(
    invalid_link,
):
    results = [
        make_product(link=invalid_link)
    ]

    products = normalize_shopping_results(
        results=results,
        currency="USD",
    )

    assert products == []


def test_normalize_rejects_missing_price():
    results = [
        make_product(price="Price unavailable")
    ]

    products = normalize_shopping_results(
        results=results,
        currency="USD",
    )

    assert products == []


def test_normalize_rejects_wrong_currency():
    results = [
        make_product(price="₹4,999")
    ]

    products = normalize_shopping_results(
        results=results,
        currency="USD",
    )

    assert products == []


def test_normalizes_real_serpapi_product_link():
    results = [
        {
            "title": "Wireless Headphones",
            "price": "$79.99",
            "source": "Example Electronics",
            "product_link": (
                "https://www.google.com/shopping/product/123"
            ),
            "snippet": (
                "Wireless noise cancelling headphones"
            ),
            "thumbnail": (
                "https://example.com/image.jpg"
            ),
        }
    ]

    products = normalize_shopping_results(
        results=results,
        currency="USD",
        budget_amount=100,
    )

    assert len(products) == 1

    product = products[0]

    assert product.name == "Wireless Headphones"
    assert product.price == Decimal("79.99")
    assert product.currency == "USD"
    assert product.merchant == "Example Electronics"
    assert product.product_url == (
        "https://www.google.com/shopping/product/123"
    )
    assert product.availability == "unknown"
    assert product.source_type == (
        "serpapi_google_shopping"
    )


def test_product_link_takes_priority_over_link():
    product = make_product()

    product["product_link"] = (
        "https://www.google.com/shopping/product/456"
    )

    products = normalize_shopping_results(
        results=[product],
        currency="USD",
    )

    assert len(products) == 1
    assert products[0].product_url == (
        "https://www.google.com/shopping/product/456"
    )


def test_fallback_to_link_when_product_link_invalid():
    product = make_product()

    product["product_link"] = "invalid-url"

    products = normalize_shopping_results(
        results=[product],
        currency="USD",
    )

    assert len(products) == 1
    assert products[0].product_url == (
        "https://example.com/product"
    )


def test_rejects_invalid_product_and_link():
    product = make_product(
        link="http://example.com/product"
    )

    product["product_link"] = "invalid-url"

    products = normalize_shopping_results(
        results=[product],
        currency="USD",
    )

    assert products == []


def test_invalid_thumbnail_is_removed():
    product = make_product()

    product["thumbnail"] = (
        "http://example.com/image.jpg"
    )

    products = normalize_shopping_results(
        results=[product],
        currency="USD",
    )

    assert len(products) == 1
    assert products[0].image_url is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "x" * 256),
        ("source", "x" * 101),
        ("price", "$10,000,000,000.00"),
    ],
)
def test_unpersistable_listing_is_skipped_without_losing_valid_results(
    field, value,
):
    invalid = make_product()
    invalid[field] = value
    valid = make_product()

    products = normalize_shopping_results([invalid, valid], currency="USD")

    assert len(products) == 1
    assert products[0].name == "Wireless Headphones"


@pytest.mark.parametrize(
    "url",
    ["https://example.com:invalid/p", "https://example.com:99999/p"],
)
def test_malformed_port_is_rejected(url):
    assert normalize_shopping_results(
        [make_product(link=url)], currency="USD",
    ) == []
