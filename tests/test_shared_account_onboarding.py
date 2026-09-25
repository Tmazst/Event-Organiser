import pytest
from itsdangerous import URLSafeTimedSerializer

from app import create_app
from app.extensions import db
from app.models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-app-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CSRF_PROTECT = False
    SESSION_COOKIE_SECURE = False
    FREE_BUDGET_ITEM_LIMIT = 4
    OWNER_PLAN_PRICE = "40.00"
    STAKEHOLDER_PRICE = "30.00"
    PAYMENT_CURRENCY = "SZL"
    MOJAPOS_MOCK_AUTO_COMPLETE = True
    MOJAPOS_SUPPORTED_COUNTRIES = ("SZ",)
    SHARED_LOGIN_HANDOFF_ENABLED = True
    SHARED_LOGIN_SECRET = "shared-login-test-secret"
    SHARED_LOGIN_MAX_AGE_SECONDS = 90
    UMSHADO_SSO_RECEIVE_URL = "https://wedding.example/shared-login/from-umcimby"
    SHARED_ACCOUNT_DISCOVERY_ENABLED = True
    SHARED_ACCOUNT_API_KEY = "shared-account-test-key"
    SHARED_ACCOUNT_API_TIMEOUT_SECONDS = 5
    VENDOR_FEATURE_ENABLED = True
    VENDOR_STORE_MANAGEMENT_ENABLED = True
    VENDOR_API_ENABLED = True
    VENDOR_ACCOUNT_API_ENABLED = True
    VENDOR_API_KEY = "vendor-test-key"


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("MOJAPOS_MOCK_MODE", "true")
    application = create_app(TestConfig)
    application.config["EVENT_PHOTO_FOLDER"] = tmp_path / "uploads" / "events"
    application.config["LEGACY_EVENT_PHOTO_FOLDER"] = tmp_path / "public" / "events"
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_shared_lookup_requires_server_key(app, client):
    with app.app_context():
        user = User(
            name="Existing", email="existing@example.com",
            phone_number="+26876123456", phone_country="SZ", account_type="organizer",
        )
        user.set_password("secret1")
        db.session.add(user)
        db.session.commit()

    denied = client.post("/shared-accounts/api/lookup", json={"email": "existing@example.com"})
    assert denied.status_code == 401

    allowed = client.post(
        "/shared-accounts/api/lookup",
        json={"email": "existing@example.com"},
        headers={"X-Shared-Account-Key": "shared-account-test-key"},
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["exists"] is True


def test_register_detects_existing_umshado_account(app, client, monkeypatch):
    monkeypatch.setattr(
        "app.shared_accounts.requests.post",
        lambda *args, **kwargs: FakeResponse({
            "exists": True,
            "email": "person@example.com",
            "account_type": "wedding",
        }),
    )
    response = client.post("/shared-accounts/register", data={
        "name": "Person",
        "email": "person@example.com",
        "phone_number": "76123456",
        "phone_country": "SZ",
        "password": "secret1",
        "account_type": "organizer",
    })
    assert response.status_code == 409
    assert b"Continue with UMSHADO" in response.data
    assert b"identity=person%40example.com" in response.data
    with app.app_context():
        assert db.session.scalar(db.select(User).where(User.email == "person@example.com")) is None


def test_umshado_handoff_provisions_organizer_and_routes_to_event_setup(app, client):
    payload = {
        "email": "new@example.com",
        "phone_number": "+26876123456",
        "phone_country": "SZ",
        "name": "New User",
        "source": "umshado",
        "target": "umcimby",
        "account_type": "organizer",
        "provision": True,
    }
    token = URLSafeTimedSerializer(
        app.config["SHARED_LOGIN_SECRET"], salt="umshado-to-umcimby"
    ).dumps(payload)

    response = client.get(f"/shared-login/from-umshado?token={token}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/event/setup")
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "new@example.com"))
        assert user is not None
        assert user.account_type == "organizer"


def test_umshado_handoff_can_provision_vendor(app, client):
    payload = {
        "email": "vendor@example.com",
        "phone_number": "+26876234567",
        "phone_country": "SZ",
        "name": "Vendor User",
        "source": "umshado",
        "target": "umcimby",
        "account_type": "vendor",
        "provision": True,
    }
    token = URLSafeTimedSerializer(
        app.config["SHARED_LOGIN_SECRET"], salt="umshado-to-umcimby"
    ).dumps(payload)

    response = client.get(f"/shared-login/from-umshado?token={token}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/vendor/setup")
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "vendor@example.com"))
        assert user is not None
        assert user.account_type == "vendor"
