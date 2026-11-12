
import asyncio

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from app.providers.demo_catalog import DemoCatalogProvider
from app.services.product_discovery import discover_products
from tests.test_database_config import get_test_database_url


def test_discovery_with_real_postgresql():
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

            # End the transaction started by the database check.
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
                    db.commit()

                    provider = DemoCatalogProvider()

                    first_results = asyncio.run(
                        discover_products(
                            shopping_session=shopping_session,
                            db=db,
                            provider=provider,
                        )
                    )

                    assert len(first_results) == 3

                    first_ids = {
                        product.id for product in first_results
                    }

                    stored_products = db.scalars(
                        select(Product).where(
                            Product.shopping_session_id
                            == shopping_session.id
                        )
                    ).all()

                    assert len(stored_products) == 3

                    second_results = asyncio.run(
                        discover_products(
                            shopping_session=shopping_session,
                            db=db,
                            provider=provider,
                        )
                    )

                    second_ids = {
                        product.id for product in second_results
                    }

                    assert len(second_results) == 3
                    assert first_ids == second_ids

                    total_products = db.scalar(
                        select(func.count()).select_from(Product).where(
                            Product.shopping_session_id
                            == shopping_session.id
                        )
                    )

                    assert total_products == 3

                    assert all(
                        product.source_type == "demo_catalog"
                        for product in second_results
                    )

            finally:
                outer_transaction.rollback()

    finally:
        engine.dispose()
