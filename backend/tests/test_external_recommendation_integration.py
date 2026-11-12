
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.shopping_session import ShoppingSession
from app.services.recommendation_service import (
    generate_recommendations,
)
from tests.test_database_config import get_test_database_url


def test_external_products_can_be_recommended_and_persisted():
    engine = create_engine(
        get_test_database_url(),
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            database_name = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()

            assert database_name == "spendpilot_test_db"

            connection.rollback()
            outer_transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    shopping_session = ShoppingSession(
                        query="wireless headphones",
                        budget_amount=5000,
                        currency="INR",
                        status="created",
                    )

                    db.add(shopping_session)
                    db.flush()

                    products = [
                        Product(
                            shopping_session_id=shopping_session.id,
                            name="Wireless Headphones A",
                            description="Bluetooth headphones",
                            price=Decimal("1999.00"),
                            currency="INR",
                            merchant="External Merchant A",
                            product_url="https://example.com/a",
                            image_url=None,
                            availability="unknown",
                            source_type="serpapi_google_shopping",
                        ),
                        Product(
                            shopping_session_id=shopping_session.id,
                            name="Wireless Headphones B",
                            description="Bluetooth headphones",
                            price=Decimal("2999.00"),
                            currency="INR",
                            merchant="External Merchant B",
                            product_url="https://example.com/b",
                            image_url=None,
                            availability="unknown",
                            source_type="serpapi_google_shopping",
                        ),
                        Product(
                            shopping_session_id=shopping_session.id,
                            name="Wireless Headphones C",
                            description="Bluetooth headphones",
                            price=Decimal("5999.00"),
                            currency="INR",
                            merchant="External Merchant C",
                            product_url="https://example.com/c",
                            image_url=None,
                            availability="unknown",
                            source_type="serpapi_google_shopping",
                        ),
                    ]

                    db.add_all(products)
                    db.commit()

                    first = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    # The over-budget product must be excluded.
                    assert len(first) == 2

                    assert all(
                        "Stock availability has not been verified"
                        in item.reasoning
                        for item in first
                    )

                    assert all(
                        "comparison only" in item.reasoning
                        for item in first
                    )

                    first_ids = {
                        item.product_id: item.id
                        for item in first
                    }

                    second = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    # Repeated generation must preserve IDs.
                    assert len(second) == 2

                    second_ids = {
                        item.product_id: item.id
                        for item in second
                    }

                    assert first_ids == second_ids

                    count = db.scalar(
                        select(func.count())
                        .select_from(Recommendation)
                        .where(
                            Recommendation.shopping_session_id
                            == shopping_session.id
                        )
                    )

                    assert count == 2

                    # Explicitly unavailable products are removed.
                    products[0].availability = "out_of_stock"
                    db.commit()

                    third = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    assert len(third) == 1
                    assert third[0].product_id == products[1].id

            finally:
                outer_transaction.rollback()

    finally:
        engine.dispose()
