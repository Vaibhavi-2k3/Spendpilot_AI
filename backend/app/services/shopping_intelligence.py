import hashlib
import json

from app.providers.gemini_provider import GeminiError
from app.schemas.comparison import ComparisonProductResponse
from app.schemas.intelligence import (
    AIComparisonResponse, GroundedComparison, ProductEvidence,
    ProductExplanation, ShoppingIntent,
)


def original_intent(query: str) -> ShoppingIntent:
    return ShoppingIntent(search_query=query, use_case=None, preferences=[])


def comparison_context(shopping_session, products: list[ComparisonProductResponse]):
    return {
        "request": shopping_session.query,
        "intent": shopping_session.intent,
        "budget_amount": shopping_session.budget_amount,
        "currency": shopping_session.currency,
        "products": [
            {
                "product_id": product.product_id,
                "name": product.name,
                "description": (product.description or "")[:4000],
                "price": str(product.price),
                "currency": product.currency,
                "merchant": product.merchant,
                "availability": product.availability,
                "checkout_eligible": product.checkout_eligible,
                "source_type": product.source_type,
            }
            for product in products
        ],
    }


def context_fingerprint(context: dict) -> str:
    return hashlib.sha256(
        json.dumps(context, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def validate_grounding(report: GroundedComparison, context: dict) -> None:
    products_by_id = {
        product["product_id"]: product for product in context["products"]
    }
    reported_ids = [product.product_id for product in report.products]
    if (
        len(reported_ids) != len(set(reported_ids))
        or set(reported_ids) != set(products_by_id)
        or report.recommended_product_id not in products_by_id
    ):
        raise GeminiError("Gemini referenced an invalid set of products")

    for product in report.products:
        source = products_by_id[product.product_id]
        if any(
            evidence.quote not in source[evidence.field]
            for evidence in product.evidence
        ):
            raise GeminiError("Gemini evidence did not match the supplied listings")


def fallback_comparison(
    products: list[ComparisonProductResponse], status: str, message: str,
) -> AIComparisonResponse:
    return AIComparisonResponse(
        provider="rule_based", status=status, message=message,
        summary=(
            "Products are ordered by search-term relevance and budget efficiency. "
            "Prices and checkout eligibility come from the catalog; external "
            "stock and product features have not been independently verified."
        ) if products else "No eligible recommendations are available to compare.",
        recommended_product_id=products[0].product_id if products else None,
        products=[
            ProductExplanation(
                product_id=product.product_id, explanation=product.reasoning,
                evidence=[ProductEvidence(field="name", quote=product.name)],
            )
            for product in products
        ],
    )


def comparison_response(report: GroundedComparison) -> AIComparisonResponse:
    return AIComparisonResponse(
        provider="gemini", status="ready", **report.model_dump(),
    )
