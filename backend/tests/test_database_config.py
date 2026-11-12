
import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def get_test_database_url() -> str:
    development_url = get_settings().database_url
    parsed_url = make_url(development_url)

    if parsed_url.get_backend_name() != "postgresql":
        raise RuntimeError(
            "Integration tests require PostgreSQL."
        )

    if parsed_url.database != "spendpilot_db":
        raise RuntimeError(
            "Unexpected development database name. "
            "Refusing to construct test database URL."
        )

    return parsed_url.set(
        database="spendpilot_test_db"
    ).render_as_string(hide_password=False)


def test_database_connection():
    test_url = get_test_database_url()

    engine = create_engine(
        test_url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

        assert result == "spendpilot_test_db"
    finally:
        engine.dispose()
