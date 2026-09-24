"""Database configuration from environment variables."""
import os
from sqlalchemy.engine import Engine


def get_database_url() -> str:
    """
    Construct PostgreSQL connection URL from environment.
    
    Variables:
      DATABASE_URL (optional): Full connection string, takes precedence
      POSTGRES_HOST: hostname (default: localhost)
      POSTGRES_PORT: port (default: 5432)
      POSTGRES_DB: database name (default: qtkd)
      POSTGRES_USER: user (default: qtkd_user)
      POSTGRES_PASSWORD: password (default: qtkd_password)
    """
    # If DATABASE_URL is set, use it directly (e.g., for Heroku or testing)
    if url := os.environ.get("DATABASE_URL"):
        return url

    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "qtkd")
    user = os.environ.get("POSTGRES_USER", "qtkd_user")
    password = os.environ.get("POSTGRES_PASSWORD", "qtkd_password")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def init_db(engine: Engine) -> None:
    """Initialize database tables from metadata."""
    from .models import Base
    Base.metadata.create_all(bind=engine)
