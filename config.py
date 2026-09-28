import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "event_organiser_session_v2")
    SESSION_COOKIE_DOMAIN = None
    SESSION_COOKIE_PATH = "/"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() in {
        "1", "true", "yes", "on"
    }
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'event_planner.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FREE_BUDGET_ITEM_LIMIT = int(os.getenv("FREE_BUDGET_ITEM_LIMIT", "4"))
    OWNER_PLAN_PRICE = os.getenv("OWNER_PLAN_PRICE", "40.00")
    STAKEHOLDER_PRICE = os.getenv("STAKEHOLDER_PRICE", "30.00")

    # Shared vendor service. Disabled by default so it can be deployed safely.
    VENDOR_FEATURE_ENABLED = env_bool("VENDOR_FEATURE_ENABLED", False)
    VENDOR_STORE_MANAGEMENT_ENABLED = env_bool("VENDOR_STORE_MANAGEMENT_ENABLED", True)
    VENDOR_API_ENABLED = env_bool("VENDOR_API_ENABLED", False)
    VENDOR_ACCOUNT_API_ENABLED = env_bool("VENDOR_ACCOUNT_API_ENABLED", False)
    VENDOR_API_KEY = os.getenv("VENDOR_API_KEY") or None

    # Short-lived signed login handoff between Umcimby and UMSHADO.
    SHARED_LOGIN_HANDOFF_ENABLED = env_bool("SHARED_LOGIN_HANDOFF_ENABLED", False)
    SHARED_LOGIN_SECRET = os.getenv("SHARED_LOGIN_SECRET") or None
    SHARED_LOGIN_MAX_AGE_SECONDS = int(os.getenv("SHARED_LOGIN_MAX_AGE_SECONDS", "90"))
    UMSHADO_SSO_RECEIVE_URL = os.getenv("UMSHADO_SSO_RECEIVE_URL", "").strip()

    # Cross-app account discovery. Keep this server-to-server secret separate
    # from both SHARED_LOGIN_SECRET and VENDOR_API_KEY.
    SHARED_ACCOUNT_DISCOVERY_ENABLED = env_bool("SHARED_ACCOUNT_DISCOVERY_ENABLED", False)
    SHARED_ACCOUNT_API_KEY = os.getenv("SHARED_ACCOUNT_API_KEY") or None
    SHARED_ACCOUNT_API_TIMEOUT_SECONDS = float(os.getenv("SHARED_ACCOUNT_API_TIMEOUT_SECONDS", "5"))

    PAYMENT_CURRENCY = os.getenv("MOJAPOS_CURRENCY", "SZL")
    MOJAPOS_SUPPORTED_COUNTRIES = tuple(
        country.strip().upper()
        for country in os.getenv("MOJAPOS_SUPPORTED_COUNTRIES", "SZ").split(",")
        if country.strip()
    )
    MOJAPOS_MOCK_AUTO_COMPLETE = os.getenv(
        "MOJAPOS_MOCK_AUTO_COMPLETE", "false"
    ).lower() in {"1", "true", "yes", "on"}
    CSRF_PROTECT = True
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    EVENT_PHOTO_FOLDER = BASE_DIR / "instance" / "uploads" / "events"
    LEGACY_EVENT_PHOTO_FOLDER = BASE_DIR / "app" / "static" / "uploads" / "events"
