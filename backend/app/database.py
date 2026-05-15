"""
Database engine and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

settings = get_settings()

# Create engine with connection pool settings
# Pool settings are kept small for serverless (Vercel) compatibility
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,        # Verify connections before using
    pool_size=3,               # Max persistent connections (small for serverless)
    max_overflow=5,            # Extra connections allowed
    pool_recycle=300,          # Recycle connections every 5 min (prevents stale on Neon)
    echo=False,                # Set True for SQL debug logs
)

# Session factory — each request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """
    Dependency that provides a database session per request.
    Automatically closes the session when the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
