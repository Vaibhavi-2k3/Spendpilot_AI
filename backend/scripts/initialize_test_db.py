
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def main():
    development_url = make_url(
        get_settings().database_url
    )

    if development_url.get_backend_name() != "postgresql":
        raise RuntimeError(
            "Expected PostgreSQL database."
        )

    if development_url.database != "spendpilot_db":
        raise RuntimeError(
            "Unexpected development database. Aborting."
        )

    test_url = development_url.set(
        database="spendpilot_test_db"
    )

    alembic_config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini")
    )


    alembic_config.attributes["database_url_override"] = (
        test_url.render_as_string(hide_password=False)
)


    command.upgrade(alembic_config, "head")


if __name__ == "__main__":
    main()
