
from decimal import Decimal

import pytest

from app.providers.price_parser import parse_product_price


@pytest.mark.parametrize(
    "price_text,currency,expected",
    [
        ("$79.99", "USD", Decimal("79.99")),
        ("79.99", "USD", Decimal("79.99")),
        ("$1,299.00", "USD", Decimal("1299.00")),
        ("₹4,999", "INR", Decimal("4999")),
        ("₹12,499.50", "INR", Decimal("12499.50")),
        ("4999", "INR", Decimal("4999")),
        ("₹4,999", "USD", None),
        ("$79.99", "INR", None),
        ("$79 - $99", "USD", None),
        ("Price unavailable", "USD", None),
        ("", "INR", None),
        ("-10", "USD", None),
        ("1,23,456", "INR", Decimal("123456")),
        ("₹12,34,567.89", "INR", Decimal("1234567.89")),
        ("₹1,234,567.89", "INR", Decimal("1234567.89")),
        ("1,23,456", "USD", None),
        ("₹123,45,678", "INR", None),
        ("₹1,2,345", "INR", None),
        ("₹12,34", "INR", None),
    ],
)
def test_parse_product_price(
    price_text,
    currency,
    expected,
):
    assert parse_product_price(
        price_text,
        currency,
    ) == expected


def test_unsupported_currency():
    with pytest.raises(
        ValueError,
        match="Unsupported price currency: EUR",
    ):
        parse_product_price("€100", "EUR")
