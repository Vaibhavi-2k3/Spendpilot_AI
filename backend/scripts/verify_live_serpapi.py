"""Exercise real USD/INR discovery through the API using a rollback-only test DB."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.main import app


def verify_market(engine, currency: str, budget: int) -> int:
    with engine.connect() as connection:
        database_name = connection.exec_driver_sql(
            "SELECT current_database()"
        ).scalar_one()
        if database_name != "spendpilot_test_db":
            raise RuntimeError("Live verification requires spendpilot_test_db")
        connection.rollback()
        transaction = connection.begin()

        def override_get_db():
            with Session(
                bind=connection, join_transaction_mode="create_savepoint",
            ) as db:
                yield db

        previous_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app) as client:
                created = client.post(
                    "/api/shopping-sessions",
                    json={
                        "query": "wireless headphones",
                        "budget_amount": budget, "currency": currency,
                    },
                )
                if created.status_code != 201:
                    raise RuntimeError("Could not create verification session")
                base = f"/api/shopping-sessions/{created.json()['id']}"

                discovered = client.post(f"{base}/discover?source=serpapi")
                if discovered.status_code != 200:
                    raise RuntimeError(
                        f"Live discovery returned HTTP {discovered.status_code}"
                    )
                products = discovered.json()
                if not products:
                    raise RuntimeError("No qualifying live products were found")

                saved = client.get(f"{base}/products")
                if saved.status_code != 200 or {
                    item["id"] for item in saved.json()
                } != {item["id"] for item in products}:
                    raise RuntimeError("Discovered products were not saved correctly")

                recommended = client.post(f"{base}/recommendations")
                comparison = client.get(f"{base}/comparison")
                if recommended.status_code != 200 or comparison.status_code != 200:
                    raise RuntimeError("Recommendation/comparison workflow failed")
                results = comparison.json()
                if not results:
                    raise RuntimeError("No relevant recommendations were generated")

                for product in products:
                    if not (
                        product["currency"] == currency
                        and Decimal("0") <= Decimal(product["price"]) <= budget
                        and product["availability"] == "unknown"
                        and product["source_type"] == "serpapi_google_shopping"
                    ):
                        raise RuntimeError("Live product validation failed")

                if any(
                    item["checkout_eligible"]
                    or item["link_type"] != "shopping_discovery"
                    for item in results
                ):
                    raise RuntimeError("External listing checkout restriction failed")

                print(
                    f"{currency}: {len(products)} real products saved and retrieved; "
                    f"{len(results)} recommendations compared; checkout disabled."
                )
                return len(products)
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
            transaction.rollback()


def main() -> int:
    settings = get_settings()
    if not settings.serpapi_api_key or not settings.serpapi_api_key.strip():
        print("SerpApi API key is not configured.")
        return 1

    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql" or url.database != "spendpilot_db":
        print("Expected PostgreSQL development database spendpilot_db.")
        return 1

    engine = create_engine(
        url.set(database="spendpilot_test_db"),
        connect_args={"connect_timeout": 5}, pool_pre_ping=True,
    )
    succeeded = True
    try:
        for currency, budget in (("USD", 100), ("INR", 5000)):
            try:
                verify_market(engine, currency, budget)
            except RuntimeError as exc:
                print(f"{currency}: {exc}")
                succeeded = False
            except SQLAlchemyError:
                print(f"{currency}: Test database is unavailable or needs migrations.")
                succeeded = False
    finally:
        engine.dispose()

    if succeeded:
        print("Live USD/INR workflow verified. Verification rows were rolled back.")
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
