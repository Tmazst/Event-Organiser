import pytest

from app import create_app
from app.extensions import db


class VendorApiCsrfConfig:
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CSRF_PROTECT = True
    FREE_BUDGET_ITEM_LIMIT = 4
    OWNER_PLAN_PRICE = "40.00"
    STAKEHOLDER_PRICE = "30.00"
    PAYMENT_CURRENCY = "SZL"
    MOJAPOS_SUPPORTED_COUNTRIES = ("SZ",)
    VENDOR_FEATURE_ENABLED = True
    VENDOR_API_ENABLED = True
    VENDOR_ACCOUNT_API_ENABLED = True
    VENDOR_API_KEY = "test-vendor-api-key"


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("MOJAPOS_MOCK_MODE", "true")
    application = create_app(VendorApiCsrfConfig)
    application.config["EVENT_PHOTO_FOLDER"] = tmp_path / "uploads" / "events"
    application.config["LEGACY_EVENT_PHOTO_FOLDER"] = tmp_path / "public" / "events"
    with application.app_context():
        db.create_all()
    return application


def test_vendor_account_lookup_accepts_server_json_without_browser_csrf(app):
    client = app.test_client()
    response = client.post(
        "/api/vendors/accounts/lookup",
        json={
            "email": "newvendor@example.com",
            "phone_number": "+26876123456",
            "phone_country": "SZ",
        },
        headers={"X-Vendor-API-Key": "test-vendor-api-key"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "exists": False,
        "is_vendor": False,
        "has_store": False,
    }


def test_normal_browser_post_still_requires_csrf(app):
    client = app.test_client()
    response = client.post("/register", data={})
    assert response.status_code == 400
