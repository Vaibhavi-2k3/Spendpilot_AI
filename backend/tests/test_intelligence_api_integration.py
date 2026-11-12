from types import SimpleNamespace
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes.intelligence import get_gemini_provider
from app.db.database import get_db
from app.main import app
from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from app.providers.gemini_provider import GeminiError, GeminiProvider
from app.schemas.intelligence import (
    GroundedComparison, ProductEvidence, ProductExplanation, ShoppingIntent,
)
from tests.test_database_config import get_test_database_url


def make_report(context):
    return GroundedComparison(
        summary="These options fit the entered budget; compare the stated features.",
        recommended_product_id=context["products"][0]["product_id"],
        products=[ProductExplanation(
            product_id=product["product_id"],
            explanation=f"The listing explicitly offers {product['name']}.",
            evidence=[ProductEvidence(field="name", quote=product["name"])],
        ) for product in context["products"]],
    )


@pytest.fixture
def environment():
    engine = create_engine(get_test_database_url(), pool_pre_ping=True)
    provider = MagicMock(spec=GeminiProvider)
    provider.model = "gemini-test"
    provider.understand_intent.return_value = ShoppingIntent(
        search_query="noise cancelling headphones", use_case="commuting",
        preferences=["noise cancellation"],
    )
    provider.compare.side_effect = make_report

    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one() == "spendpilot_test_db"
            connection.rollback()
            transaction = connection.begin()

            def override_get_db():
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    yield db

            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[get_gemini_provider] = lambda: provider
            try:
                with TestClient(app) as client:
                    yield SimpleNamespace(
                        client=client, provider=provider, connection=connection,
                    )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_gemini_provider, None)
                transaction.rollback()
    finally:
        engine.dispose()


def create_session(env):
    response = env.client.post("/api/shopping-sessions", json={
        "query": "I need headphones for a noisy commute",
        "budget_amount": 100, "currency": "USD",
    })
    assert response.status_code == 201
    return f"/api/shopping-sessions/{response.json()['id']}"


def discover_and_recommend(env, base):
    assert env.client.post(f"{base}/discover").status_code == 200
    assert env.client.post(f"{base}/recommendations").status_code == 200


def test_intent_drives_discovery_and_grounded_comparison_is_cached(environment):
    env = environment
    base = create_session(env)
    intent = env.client.post(f"{base}/intent")
    assert intent.status_code == 200
    assert intent.json()["provider"] == "gemini"
    assert intent.json()["intent"]["search_query"] == "noise cancelling headphones"
    assert env.client.post(f"{base}/intent").json() == intent.json()
    env.provider.understand_intent.assert_called_once()

    discover_and_recommend(env, base)
    products = env.client.get(f"{base}/products").json()
    assert len(products) == 1
    assert products[0]["name"] == "Wireless Noise Cancelling Headphones"

    response = env.client.post(f"{base}/ai-comparison")
    assert response.status_code == 200
    report = response.json()
    assert report["provider"] == "gemini"
    assert report["status"] == "ready"
    assert report["recommended_product_id"] == products[0]["id"]
    assert env.client.post(f"{base}/ai-comparison").json() == report
    env.provider.compare.assert_called_once()

    session = env.client.get(base).json()
    assert session["query"] == "I need headphones for a noisy commute"
    assert session["budget_amount"] == 100
    assert session["currency"] == "USD"
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        stored = db.get(ShoppingSession, session["id"])
        assert stored.intent["preferences"] == ["noise cancellation"]
        assert stored.ai_comparison["report"]["recommended_product_id"] == products[0]["id"]


def test_unconfigured_gemini_keeps_the_complete_shopping_flow_usable(environment):
    env = environment
    app.dependency_overrides[get_gemini_provider] = lambda: None
    base = create_session(env)
    intent = env.client.post(f"{base}/intent").json()
    assert intent["provider"] == "rule_based"
    assert intent["intent"]["search_query"] == "I need headphones for a noisy commute"
    discover_and_recommend(env, base)
    report = env.client.post(f"{base}/ai-comparison")
    assert report.status_code == 200
    assert report.json()["provider"] == "rule_based"
    assert report.json()["status"] == "unavailable"
    assert report.json()["products"]
    env.provider.understand_intent.assert_not_called()
    env.provider.compare.assert_not_called()


def test_intent_provider_failure_preserves_original_request(environment):
    env = environment
    env.provider.understand_intent.side_effect = GeminiError("private-test-key")
    base = create_session(env)
    response = env.client.post(f"{base}/intent")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "private-test-key" not in response.text
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        assert db.get(ShoppingSession, base.rsplit("/", 1)[1]).intent is None


@pytest.mark.parametrize("failure", ["provider_error", "invented_product", "invented_evidence"])
def test_comparison_failure_uses_rules_without_modifying_catalog(environment, failure):
    env = environment
    base = create_session(env)
    discover_and_recommend(env, base)
    original = env.client.get(f"{base}/comparison").json()

    def fail(context):
        if failure == "provider_error":
            raise GeminiError("private-test-key")
        report = make_report(context)
        if failure == "invented_product":
            report.recommended_product_id = "invented-product"
        else:
            report.products[0].evidence[0].quote = "invented 48-hour battery"
        return report

    env.provider.compare.side_effect = fail
    response = env.client.post(f"{base}/ai-comparison")
    assert response.status_code == 200
    assert response.json()["provider"] == "rule_based"
    assert response.json()["status"] == "unavailable"
    assert "private-test-key" not in response.text
    assert env.client.get(f"{base}/comparison").json() == original


def test_intent_cannot_be_changed_after_discovery(environment):
    env = environment
    base = create_session(env)
    discover_and_recommend(env, base)
    assert env.client.post(f"{base}/intent").status_code == 409
    env.provider.understand_intent.assert_not_called()


def test_no_products_skips_the_model(environment):
    env = environment
    base = create_session(env)
    response = env.client.post(f"{base}/ai-comparison")
    assert response.status_code == 200
    assert response.json()["status"] == "empty"
    env.provider.compare.assert_not_called()


def test_price_change_during_inference_does_not_save_stale_ai_report(environment):
    env = environment
    base = create_session(env)
    discover_and_recommend(env, base)

    def update_price(context):
        with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
            product = db.get(Product, context["products"][0]["product_id"])
            product.price += 1
            db.commit()
        return make_report(context)

    env.provider.compare.side_effect = update_price
    response = env.client.post(f"{base}/ai-comparison")
    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        assert db.get(ShoppingSession, base.rsplit("/", 1)[1]).ai_comparison is None


def test_cached_ai_report_is_invalidated_by_discovery_changes(environment):
    env = environment
    base = create_session(env)
    discover_and_recommend(env, base)
    assert env.client.post(f"{base}/ai-comparison").json()["provider"] == "gemini"
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        product = db.scalar(select(Product).where(
            Product.shopping_session_id == base.rsplit("/", 1)[1],
        ))
        product.price += 1
        db.commit()

    assert env.client.post(f"{base}/discover").status_code == 200
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        assert db.get(ShoppingSession, base.rsplit("/", 1)[1]).ai_comparison is None
    assert env.client.post(f"{base}/recommendations").status_code == 200
    assert env.client.post(f"{base}/ai-comparison").json()["provider"] == "gemini"
    assert env.provider.compare.call_count == 2


def test_comparison_only_sends_top_five_eligible_products_and_keeps_external_checkout_off(
    environment,
):
    env = environment
    base = create_session(env)
    session_id = base.rsplit("/", 1)[1]
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        for index in range(10):
            db.add(Product(
                shopping_session_id=session_id,
                name=f"Wireless Headphones {index}", description="Bluetooth audio",
                price=Decimal("10") + index if index != 9 else Decimal("101"),
                currency="INR" if index == 8 else "USD",
                merchant="External Store",
                product_url=f"https://example.com/product/{index}",
                availability="out_of_stock" if index == 7 else "unknown",
                source_type="serpapi_google_shopping",
            ))
        db.commit()

    assert env.client.post(f"{base}/recommendations").status_code == 200
    response = env.client.post(f"{base}/ai-comparison")
    assert response.json()["provider"] == "gemini"
    assert len(response.json()["products"]) == 5

    context = env.provider.compare.call_args.args[0]
    assert len(context["products"]) == 5
    assert all(
        product["currency"] == "USD"
        and Decimal(product["price"]) <= 100
        and product["availability"] == "unknown"
        and product["checkout_eligible"] is False
        and "product_url" not in product and "image_url" not in product
        for product in context["products"]
    )
    comparison = env.client.get(f"{base}/comparison").json()
    assert len(comparison) == 7
    assert all(product["checkout_eligible"] is False for product in comparison)


def test_changed_context_bypasses_cached_report(environment):
    env = environment
    base = create_session(env)
    discover_and_recommend(env, base)
    assert env.client.post(f"{base}/ai-comparison").json()["provider"] == "gemini"
    with Session(bind=env.connection, join_transaction_mode="create_savepoint") as db:
        product = db.scalar(select(Product).where(
            Product.shopping_session_id == base.rsplit("/", 1)[1],
        ))
        product.price += 1
        db.commit()
    assert env.client.post(f"{base}/ai-comparison").json()["provider"] == "gemini"
    assert env.provider.compare.call_count == 2


@pytest.mark.parametrize("endpoint", ["intent", "ai-comparison"])
def test_intelligence_session_not_found(environment, endpoint):
    response = environment.client.post(f"/api/shopping-sessions/missing/{endpoint}")
    assert response.status_code == 404
