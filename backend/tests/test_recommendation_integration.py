
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


def test_recommendations_with_real_postgresql():
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

            # SELECT starts an implicit transaction.
            connection.rollback()
            outer_transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    shopping_session = ShoppingSession(
                        query="wireless headphones",
                        budget_amount=100,
                        currency="USD",
                        status="created",
                    )

                    db.add(shopping_session)
                    db.flush()

                    headphones = Product(
                        shopping_session_id=shopping_session.id,
                        name="Wireless Headphones",
                        description="Noise cancelling headphones",
                        price=Decimal("79.99"),
                        currency="USD",
                        merchant="SpendPilot Demo Store",
                        product_url="https://example.com/demo/headphones",
                        image_url=None,
                        availability="in_stock",
                        source_type="demo_catalog",
                    )

                    earbuds = Product(
                        shopping_session_id=shopping_session.id,
                        name="Wireless Earbuds",
                        description="Bluetooth earbuds",
                        price=Decimal("39.99"),
                        currency="USD",
                        merchant="SpendPilot Demo Store",
                        product_url="https://example.com/demo/earbuds",
                        image_url=None,
                        availability="in_stock",
                        source_type="demo_catalog",
                    )

                    db.add_all([headphones, earbuds])
                    db.commit()

                    # First recommendation generation.
                    first_results = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    assert len(first_results) == 2
                    assert first_results[0].product_id == headphones.id

                    first_ids = {
                        item.product_id: item.id
                        for item in first_results
                    }

                    assert all(
                        0 <= item.score <= 1
                        for item in first_results
                    )

                    assert all(
                        item.reasoning
                        for item in first_results
                    )

                    # Generate again: existing rows should be reused.
                    second_results = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    assert len(second_results) == 2

                    second_ids = {
                        item.product_id: item.id
                        for item in second_results
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

                    # Make earbuds unavailable.
                    earbuds.availability = "out_of_stock"
                    db.commit()

                    third_results = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    assert len(third_results) == 1
                    assert third_results[0].product_id == headphones.id

                    remaining = db.scalars(
                        select(Recommendation).where(
                            Recommendation.shopping_session_id
                            == shopping_session.id
                        )
                    ).all()

                    assert len(remaining) == 1
                    assert remaining[0].product_id == headphones.id

            finally:
                outer_transaction.rollback()

    finally:
        engine.dispose()
