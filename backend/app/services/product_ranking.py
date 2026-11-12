
from dataclasses import dataclass
from decimal import Decimal

from app.models.product import Product
from app.models.shopping_session import ShoppingSession


@dataclass(frozen=True)
class RankedProduct:
    product: Product
    score: float
    reasoning: str


def rank_products(
    shopping_session: ShoppingSession,
    products: list[Product],
) -> list[RankedProduct]:

    query_terms = {
        term.lower()
        for term in (
            getattr(shopping_session, "discovery_query", None) or shopping_session.query
        ).split()
        if term.strip()
    }

    ranked_products = []

    for product in products:

        # Currency must match the shopping session.
        if product.currency != shopping_session.currency:
            continue

        # Allow confirmed stock and unknown stock.
        # Explicitly unavailable products are excluded.
        if product.availability not in {
            "in_stock",
            "unknown",
        }:
            continue

        # Reject invalid negative prices.
        if product.price < 0:
            continue

        # Enforce the shopping budget.
        if (
            shopping_session.budget_amount is not None
            and product.price > shopping_session.budget_amount
        ):
            continue

        searchable_text = (
            f"{product.name} {product.description or ''}"
        ).lower()

        matching_terms = sum(
            1
            for term in query_terms
            if term in searchable_text
        )

        if matching_terms == 0:
            continue

        relevance_score = (
            matching_terms / len(query_terms)
            if query_terms
            else 0
        )

        # Calculate the budget score.
        if shopping_session.budget_amount is not None:

            budget = Decimal(
                str(shopping_session.budget_amount)
            )

            price_ratio = product.price / budget

            budget_score = float(
                1 - price_ratio
            )

        else:
            budget_score = 0.5

        # Relevance has 75% weight.
        # Budget efficiency has 25% weight.
        score = (
            relevance_score * 0.75
            + budget_score * 0.25
        )

        score = round(score, 4)

        reasoning = (
            f"Matches {matching_terms} of "
            f"{len(query_terms)} search terms. "
            f"Price: {product.currency} {product.price}."
        )

        # Never claim that external stock is confirmed.
        if product.availability == "unknown":
            reasoning += (
                " Stock availability has not been verified."
            )

        # External listings are comparison-only.
        if product.source_type != "demo_catalog":
            reasoning += (
                " External shopping listing for comparison only; "
                "not eligible for SpendPilot PayPal sandbox checkout."
            )

        ranked_products.append(
            RankedProduct(
                product=product,
                score=score,
                reasoning=reasoning,
            )
        )

    # Sort by:
    # 1. Highest score
    # 2. Lowest price
    # 3. Product ID for deterministic ordering
    return sorted(
        ranked_products,
        key=lambda item: (
            -item.score,
            item.product.price,
            item.product.id,
        ),
    )
