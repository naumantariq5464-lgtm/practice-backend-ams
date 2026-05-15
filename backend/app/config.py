"""
Application configuration — loads values from .env file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


# Determine .env file path (only used for local development)
_env_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
_env_file = _env_file_path if os.path.exists(_env_file_path) else None


class Settings(BaseSettings):
    """All application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql://user:password@host/dbname"

    # JWT
    JWT_SECRET_KEY: str = "ams-super-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Admin credentials (hardcoded login — NOT stored in DB)
    ADMIN_EMAIL: str = "admin109@gmail.com"
    ADMIN_PASSWORD_HASH: str = ""

    class Config:
        # Only load .env if it exists (local dev) — on Vercel, env vars come from dashboard
        env_file = _env_file
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once, reused everywhere."""
    return Settings()

