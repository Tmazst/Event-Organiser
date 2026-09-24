import pytest
from itsdangerous import URLSafeTimedSerializer

from app import create_app
from app.extensions import db
from app.models import SharedLoginUse, User, VendorStore


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


def make_token(app, email="vendor@example.com", phone="76123456", **overrides):
    payload = {
        "email": email,
        "phone_number": phone,
        "name": "Vendor",
        "source": "umshado",
        "target": "umcimby",
    }
    payload.update(overrides)
    return URLSafeTimedSerializer(
        app.config["SHARED_LOGIN_SECRET"], salt="umshado-to-umcimby"
    ).dumps(payload)


def add_user(app, email="vendor@example.com", phone="76123456", account_type="vendor", with_store=True):
    with app.app_context():
        user = User(
            name="Vendor", email=email, phone_number=phone,
            phone_country="SZ", account_type=account_type,
        )
        user.set_password("secret1")
        db.session.add(user)
        db.session.flush()
        if account_type == "vendor" and with_store:
            db.session.add(VendorStore(
                store_name="Vendor Store", contact_phone=phone, location="Manzini",
                offering_summary="Events", owner_id=user.id,
            ))
        db.session.commit()
        return user.id


def test_valid_handoff_logs_in_existing_vendor_once(app, client):
    user_id = add_user(app)
    token = make_token(app)

    first = client.get(f"/shared-login/from-umshado?token={token}")
    assert first.status_code == 302
    assert first.headers["Location"].endswith("/vendor")
    with client.session_transaction() as session:
        assert session.get("_user_id") == str(user_id)
    with app.app_context():
        assert db.session.query(SharedLoginUse).count() == 1

    second = client.get(f"/shared-login/from-umshado?token={token}")
    assert second.status_code == 302
    assert second.headers["Location"].endswith("/login")


def test_tampered_handoff_is_rejected(app, client):
    add_user(app)
    token = make_token(app)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    response = client.get(f"/shared-login/from-umshado?token={tampered}", follow_redirects=True)
    assert b"shared login link is invalid" in response.data


def test_identity_conflict_is_rejected(app, client):
    add_user(app, email="one@example.com", phone="76111111", with_store=False)
    add_user(app, email="two@example.com", phone="76222222", with_store=False)
    token = make_token(app, email="one@example.com", phone="76222222")
    response = client.get(f"/shared-login/from-umshado?token={token}", follow_redirects=True)
    assert b"conflicting email and phone records" in response.data


def test_missing_local_account_goes_to_registration(app, client):
    token = make_token(app)
    response = client.get(f"/shared-login/from-umshado?token={token}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/register")


def test_disabled_handoff_returns_404(app, client):
    app.config["SHARED_LOGIN_HANDOFF_ENABLED"] = False
    assert client.get("/shared-login/from-umshado?token=x").status_code == 404


def test_expired_handoff_is_rejected(app, client):
    add_user(app)
    token = make_token(app)
    app.config["SHARED_LOGIN_MAX_AGE_SECONDS"] = -1
    response = client.get(f"/shared-login/from-umshado?token={token}", follow_redirects=True)
    assert b"shared login link expired" in response.data
