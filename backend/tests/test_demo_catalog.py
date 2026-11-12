
import asyncio

from app.providers.demo_catalog import DemoCatalogProvider


def test_demo_catalog_search():
    provider = DemoCatalogProvider()

    results = asyncio.run(
        provider.search("wireless headphones", 100, "USD")
    )

    assert len(results) == 3
    assert all(product.source_type == "demo_catalog" for product in results)


def test_demo_catalog_budget_filter():
    provider = DemoCatalogProvider()

    results = asyncio.run(
        provider.search("wireless", 40, "USD")
    )

    assert len(results) == 2
    assert all(product.price <= 40 for product in results)


def test_demo_catalog_currency_filter():
    provider = DemoCatalogProvider()

    results = asyncio.run(
        provider.search("wireless", 100, "INR")
    )

    assert results == []


def test_demo_catalog_no_matches():
    provider = DemoCatalogProvider()

    results = asyncio.run(
        provider.search("refrigerator", 500, "USD")
    )

    assert results == []
