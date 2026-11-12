
from decimal import Decimal

from app.providers.base import DiscoveredProduct, ProductProvider


DEMO_PRODUCTS = [
    DiscoveredProduct(
        name="Wireless Noise Cancelling Headphones",
        description="Bluetooth headphones with active noise cancellation",
        price=Decimal("79.99"),
        currency="USD",
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/headphones",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
    ),
    DiscoveredProduct(
        name="Wireless Bluetooth Earbuds",
        description="Compact earbuds with charging case",
        price=Decimal("39.99"),
        currency="USD",
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/earbuds",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
    ),
    DiscoveredProduct(
        name="Mechanical Gaming Keyboard",
        description="RGB mechanical keyboard with tactile switches",
        price=Decimal("59.99"),
        currency="USD",
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/keyboard",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
    ),
    DiscoveredProduct(
        name="Wireless Gaming Mouse",
        description="Ergonomic wireless mouse with adjustable DPI",
        price=Decimal("29.99"),
        currency="USD",
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/mouse",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
    ),
    DiscoveredProduct(
        name="USB-C Laptop Docking Station",
        description="Multi-port USB-C hub for laptops and monitors",
        price=Decimal("119.99"),
        currency="USD",
        merchant="SpendPilot Demo Store",
        product_url="https://example.com/demo/dock",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
    ),
]


class DemoCatalogProvider(ProductProvider):

    async def search(
        self,
        query: str,
        budget_amount: int | None = None,
        currency: str = "USD",
    ) -> list[DiscoveredProduct]:

        search_terms = query.lower().split()

        results = []

        for product in DEMO_PRODUCTS:
            if product.currency != currency:
                continue

            if (
                budget_amount is not None
                and product.price > Decimal(budget_amount)
            ):
                continue

            searchable_text = (
                f"{product.name} {product.description or ''}"
            ).lower()

            if not any(
                term in searchable_text
                for term in search_terms
            ):
                continue

            results.append(product)

        return results
