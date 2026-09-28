import pytest
from itsdangerous import URLSafeTimedSerializer

from app import create_app
from app.extensions import db
from app.models import User
from app.shared_identity import SharedIdentity


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


def token(app, *, source_user_id, email, phone):
    return URLSafeTimedSerializer(
        app.config["SHARED_LOGIN_SECRET"], salt="umshado-to-umcimby"
    ).dumps({
        "source_user_id": str(source_user_id),
        "email": email,
        "phone_number": phone,
        "name": "Planner",
        "source": "umshado",
        "target": "umcimby",
    })


def test_link_survives_remote_email_and_phone_change(app, client):
    with app.app_context():
        user = User(
            name="Planner",
            email="original@example.com",
            phone_number="+26876111111",
            phone_country="SZ",
            account_type="organizer",
        )
        user.set_password("secret1")
        db.session.add(user)
        db.session.commit()
        local_user_id = user.id

    first = token(
        app,
        source_user_id=42,
        email="original@example.com",
        phone="+26876111111",
    )
    response = client.get(f"/shared-login/from-umshado?token={first}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with app.app_context():
        link = db.session.scalar(db.select(SharedIdentity))
        assert link is not None
        assert link.user_id == local_user_id
        assert link.provider == "umshado"
        assert link.provider_user_id == "42"

    second = token(
        app,
        source_user_id=42,
        email="changed@example.com",
        phone="+26876222222",
    )
    response = client.get(f"/shared-login/from-umshado?token={second}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    with client.session_transaction() as session:
        assert session.get("_user_id") == str(local_user_id)
    with app.app_context():
        assert db.session.query(SharedIdentity).count() == 1
