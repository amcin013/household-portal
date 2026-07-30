"""Configuration, read from the environment (and .env if present)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _emails(name):
    raw = os.environ.get(name, "")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secret")

    INSTANCE_DIR = BASE_DIR / "instance"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'portal.db'}"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    ALLOWED_EMAILS = _emails("ALLOWED_EMAILS")
    AUTH_MODE = os.environ.get("AUTH_MODE", "open").strip().lower()
    LOCAL_PASSWORD = os.environ.get("LOCAL_PASSWORD", "").strip()

    NWS_USER_AGENT = os.environ.get(
        "NWS_USER_AGENT", "household-portal (set NWS_USER_AGENT in .env)"
    )
    WEATHER_CACHE_MINUTES = int(os.environ.get("WEATHER_CACHE_MINUTES", "20"))

    BEHIND_PROXY = _bool("BEHIND_PROXY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("BEHIND_PROXY")
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # stay signed in a month

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB uploads

    @property
    def google_enabled(self):
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "test"
    WTF_CSRF_ENABLED = False
    AUTH_MODE = "local"
    LOCAL_PASSWORD = "test-password"
