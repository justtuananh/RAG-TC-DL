"""SQLAlchemy session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import get_database_url

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging during development
    pool_size=20,
    max_overflow=0,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency for FastAPI routes to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
