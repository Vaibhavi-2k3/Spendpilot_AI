
import asyncio
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest

from app.providers.serpapi_provider import SerpApiProvider


@pytest.mark.parametrize(
    "currency,expected_country",
    [
        ("USD", "us"),
        ("INR", "in"),
    ],
)
def test_serpapi_market_request(
    currency,
    expected_country,
):
    captured_requests = []

    def mock_handler(request: httpx.Request):
        captured_requests.append(request)

        return httpx.Response(
            200,
            json={"shopping_results": []},
        )

    transport = httpx.MockTransport(mock_handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = SerpApiProvider(
        api_key="test-api-key"
    )

    with patch(
        "app.providers.serpapi_provider.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        results = asyncio.run(
            provider.search(
                query="wireless headphones",
                budget_amount=100,
                currency=currency,
            )
        )

    assert results == []
    assert len(captured_requests) == 1

    request = captured_requests[0]

    assert str(request.url).startswith(
        "https://serpapi.com/search.json"
    )

    assert request.url.params["engine"] == (
        "google_shopping"
    )
    assert request.url.params["q"] == (
        "wireless headphones"
    )
    assert request.url.params["gl"] == (
        expected_country
    )
    assert request.url.params["hl"] == "en"
    assert request.url.params["api_key"] == (
        "test-api-key"
    )


def test_serpapi_rejects_api_error():
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={"error": "Invalid API key"},
        )

    transport = httpx.MockTransport(mock_handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = SerpApiProvider(
        api_key="test-api-key"
    )

    with patch(
        "app.providers.serpapi_provider.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        with pytest.raises(
            ValueError,
            match="SerpApi returned an API error",
        ):
            asyncio.run(
                provider.search(
                    query="wireless headphones",
                    currency="USD",
                )
            )


@pytest.mark.parametrize(
    "currency,price_text,expected_price",
    [
        ("USD", "$79.99", "79.99"),
        ("INR", "₹4,999", "4999"),
    ],
)
def test_serpapi_returns_normalized_products(
    currency,
    price_text,
    expected_price,
):
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "shopping_results": [
                    {
                        "title": "Wireless Headphones",
                        "price": price_text,
                        "source": "Example Electronics",
                        "link": (
                            "https://example.com/headphones"
                        ),
                        "snippet": (
                            "Bluetooth noise cancelling headphones"
                        ),
                        "thumbnail": (
                            "https://example.com/headphones.jpg"
                        ),
                    }
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = SerpApiProvider(
        api_key="test-api-key"
    )

    with patch(
        "app.providers.serpapi_provider.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        products = asyncio.run(
            provider.search(
                query="wireless headphones",
                currency=currency,
            )
        )

    assert len(products) == 1

    product = products[0]

    assert product.name == "Wireless Headphones"
    assert product.price == Decimal(expected_price)
    assert product.currency == currency
    assert product.merchant == "Example Electronics"
    assert product.product_url == (
        "https://example.com/headphones"
    )
    assert product.source_type == (
        "serpapi_google_shopping"
    )
    assert product.availability == "unknown"


@pytest.mark.parametrize(
    "response_data,expected_error",
    [
        (
            ["invalid", "response"],
            "Unexpected SerpApi response format",
        ),
        (
            {"shopping_results": "invalid"},
            "Unexpected SerpApi shopping results format",
        ),
        (
            {"error": "Invalid API key"},
            "SerpApi returned an API error",
        ),
    ],
)
def test_serpapi_rejects_malformed_responses(
    response_data,
    expected_error,
):
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            200,
            json=response_data,
        )

    transport = httpx.MockTransport(mock_handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = SerpApiProvider(
        api_key="test-api-key"
    )

    with patch(
        "app.providers.serpapi_provider.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        with pytest.raises(
            ValueError,
            match=expected_error,
        ):
            asyncio.run(
                provider.search(
                    query="wireless headphones",
                    currency="USD",
                )
            )


def test_serpapi_handles_http_error():
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            503,
            json={"error": "Service unavailable"},
        )

    transport = httpx.MockTransport(mock_handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = SerpApiProvider(
        api_key="test-api-key"
    )

    with patch(
        "app.providers.serpapi_provider.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        with pytest.raises(
            ValueError,
            match="SerpApi request failed with HTTP status 503",
        ) as exc_info:
            asyncio.run(
                provider.search(
                    query="wireless headphones",
                    currency="USD",
                )
            )

    # Ensure API credentials are not exposed.
    assert "test-api-key" not in str(exc_info.value)


def test_serpapi_handles_timeout():
    def mock_handler(request: httpx.Request):
        raise httpx.ReadTimeout(
            "Request timed out",
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = SerpApiProvider(
        api_key="test-api-key"
    )

    with patch(
        "app.providers.serpapi_provider.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        with pytest.raises(
            ValueError,
            match="SerpApi request timed out",
        ) as exc_info:
            asyncio.run(
                provider.search(
                    query="wireless headphones",
                    currency="INR",
                )
            )

    # Ensure API credentials are not exposed.
    assert "test-api-key" not in str(exc_info.value)
