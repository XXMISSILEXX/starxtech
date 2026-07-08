import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    APP_ENV = os.getenv("APP_ENV", "local")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true" and APP_ENV != "production"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", str(BASE_DIR / "storage" / "uploads"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    MAX_IMAGES_PER_SECTION = int(os.getenv("MAX_IMAGES_PER_SECTION", "3"))
    SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
