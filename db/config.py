"""Database configuration from config/settings.yaml."""
from sqlalchemy.engine import Engine

from core.settings_loader import get_settings


def get_database_url() -> str:
    """
    Construct PostgreSQL connection URL from settings.

    database.url (optional): Full connection string, takes precedence
    Host/port/name/user/password otherwise come from the same settings block.
    """
    database = get_settings().database
    if database.url is not None:
        return database.url.get_secret_value()

    return (
        f"postgresql://{database.user}:{database.password.get_secret_value()}"
        f"@{database.host}:{database.port}/{database.name}"
    )


def init_db(engine: Engine) -> None:
    """Initialize database tables from metadata."""
    from .models import Base

    Base.metadata.create_all(bind=engine)
