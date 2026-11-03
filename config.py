import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from the project root.
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration for IntelliDesk."""

    SECRET_KEY = os.getenv("SECRET_KEY")

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is missing. Configure it in the project-root .env file."
        )

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL is missing. Configure it in the project-root .env file."
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Request-size limit: 5 MB.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # Session-cookie settings for local HTTP development.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"
