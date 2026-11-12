
from decimal import Decimal
from urllib.parse import urlparse

from app.providers.base import DiscoveredProduct
from app.providers.price_parser import parse_product_price


def is_valid_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False

    if not value.strip():
        return False

    try:
        parsed_url = urlparse(value)
        # Accessing port also validates malformed/out-of-range ports.
        parsed_url.port
    except ValueError:
        return False

    return (
        parsed_url.scheme == "https"
        and bool(parsed_url.hostname)
        and parsed_url.username is None
        and parsed_url.password is None
    )


def normalize_shopping_results(
    results: list[dict],
    currency: str,
    budget_amount: int | None = None,
) -> list[DiscoveredProduct]:

    normalized = []
    seen_urls = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        name = item.get("title")
        price_text = item.get("price")
        merchant = item.get("source")

        # Real SerpApi responses often provide product_link.
        # Older/mock responses may provide link.
        product_url = item.get("product_link")

        if not is_valid_https_url(product_url):
            product_url = item.get("link")

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                name,
                price_text,
                merchant,
            )
        ):
            continue

        if not is_valid_https_url(product_url):
            continue

        price = parse_product_price(
            price_text,
            currency,
        )

        if price is None:
            continue

        if (
            budget_amount is not None
            and price > Decimal(budget_amount)
        ):
            continue

        if product_url in seen_urls:
            continue

        description = item.get("snippet")
        image_url = item.get("thumbnail")

        product = DiscoveredProduct(
            name=name.strip(),
            description=(
                description
                if isinstance(description, str)
                else None
            ),
            price=price,
            currency=currency,
            merchant=merchant.strip(),
            product_url=product_url,
            image_url=(
                image_url
                if is_valid_https_url(image_url)
                else None
            ),
            availability="unknown",
            source_type="serpapi_google_shopping",
        )

        try:
            product.validate()
        except ValueError:
            continue

        seen_urls.add(product_url)
        normalized.append(product)

    return normalized
