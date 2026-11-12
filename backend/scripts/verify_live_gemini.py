"""Verify real Gemini against demo products, rolling back all test records."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.main import app


def verify(engine):
    with engine.connect() as connection:
        if connection.exec_driver_sql(
            "SELECT current_database()"
        ).scalar_one() != "spendpilot_test_db":
            raise RuntimeError("Verification requires spendpilot_test_db")
        connection.rollback()
        transaction = connection.begin()

        def override_get_db():
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                yield db

        previous = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app) as client:
                created = client.post("/api/shopping-sessions", json={
                    "query": "wireless headphones with noise cancellation for commuting",
                    "budget_amount": 100, "currency": "USD",
                })
                if created.status_code != 201:
                    raise RuntimeError("Could not create verification session")
                base = f"/api/shopping-sessions/{created.json()['id']}"

                intent = client.post(f"{base}/intent")
                if intent.status_code != 200 or intent.json()["provider"] != "gemini":
                    raise RuntimeError("Gemini intent analysis was unavailable")
                if client.post(f"{base}/discover").status_code != 200:
                    raise RuntimeError("Demo product discovery failed")
                if client.post(f"{base}/recommendations").status_code != 200:
                    raise RuntimeError("Recommendation generation failed")
                comparison = client.post(f"{base}/ai-comparison")
                if (
                    comparison.status_code != 200
                    or comparison.json()["provider"] != "gemini"
                    or comparison.json()["status"] != "ready"
                ):
                    raise RuntimeError("Gemini did not produce a grounded comparison")
                cached = client.post(f"{base}/ai-comparison")
                if cached.status_code != 200 or cached.json() != comparison.json():
                    raise RuntimeError("Comparison cache verification failed")
                session = client.get(base).json()
                if session["budget_amount"] != 100 or session["currency"] != "USD":
                    raise RuntimeError("Original budget/currency were not preserved")

                print("Gemini shopping intent verified.")
                print(f"Grounded explanations: {len(comparison.json()['products'])}")
                print("Budget/currency preservation and comparison cache verified.")
        finally:
            if previous is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous
            transaction.rollback()


def main() -> int:
    settings = get_settings()
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        print("Gemini API key is not configured. Set GEMINI_API_KEY in .env.")
        return 1
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql" or url.database != "spendpilot_db":
        print("Expected PostgreSQL development database spendpilot_db.")
        return 1
    engine = create_engine(
        url.set(database="spendpilot_test_db"),
        connect_args={"connect_timeout": 5}, pool_pre_ping=True,
    )
    try:
        verify(engine)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    except SQLAlchemyError:
        print("Test database is unavailable or needs migrations.")
        return 1
    finally:
        engine.dispose()
    print("Live Gemini workflow verified. Verification rows were rolled back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
