
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from tests.test_database_config import get_test_database_url


def test_real_database_product_insert_and_retrieve():
    test_url = get_test_database_url()

    engine = create_engine(
        test_url,
        pool_pre_ping=True,
    )

    try:

        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one() == "spendpilot_test_db"

            # End the transaction automatically started by SELECT.
            connection.rollback()

            # Start a fresh transaction for the integration test.
            transaction = connection.begin()


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

                    product = Product(
                        shopping_session_id=shopping_session.id,
                        name="Wireless Noise Cancelling Headphones",
                        description="Bluetooth headphones",
                        price=Decimal("79.99"),
                        currency="USD",
                        merchant="SpendPilot Demo Store",
                        product_url="https://example.com/demo/headphones",
                        image_url=None,
                        availability="in_stock",
                        source_type="demo_catalog",
                    )

                    db.add(product)
                    db.flush()

                    saved_product = db.scalar(
                        select(Product).where(
                            Product.shopping_session_id
                            == shopping_session.id
                        )
                    )

                    assert saved_product is not None
                    assert saved_product.name == (
                        "Wireless Noise Cancelling Headphones"
                    )
                    assert saved_product.price == Decimal("79.99")
                    assert saved_product.source_type == "demo_catalog"

            finally:
                transaction.rollback()

    finally:
        engine.dispose()
