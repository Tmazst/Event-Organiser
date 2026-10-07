import re

from app import create_app
from app.extensions import db
from app.models import Event, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "umcimby-demo-test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CSRF_PROTECT = False
    FREE_BUDGET_ITEM_LIMIT = 4
    OWNER_PLAN_PRICE = "40.00"
    STAKEHOLDER_PRICE = "30.00"
    PAYMENT_CURRENCY = "SZL"
    MOJAPOS_MOCK_AUTO_COMPLETE = True
    MOJAPOS_SUPPORTED_COUNTRIES = ("SZ",)
    DEMO_MODE_ENABLED = True
    DEMO_ACCOUNT_EMAIL = "demo@umcimby.app"
    VENDOR_FEATURE_ENABLED = False
    VENDOR_STORE_MANAGEMENT_ENABLED = False
    VENDOR_API_ENABLED = False
    VENDOR_ACCOUNT_API_ENABLED = False
    SHARED_LOGIN_HANDOFF_ENABLED = False
    SHARED_ACCOUNT_DISCOVERY_ENABLED = False


def make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("MOJAPOS_MOCK_MODE", "true")
    app = create_app(TestConfig)
    app.config["EVENT_PHOTO_FOLDER"] = tmp_path / "uploads" / "events"
    app.config["LEGACY_EVENT_PHOTO_FOLDER"] = tmp_path / "legacy" / "events"
    with app.app_context():
        db.create_all()
    return app


def test_seed_demo_creates_complete_standard_event(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0

    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "demo@umcimby.app"))
        assert user is not None
        assert user.account_type == "organizer"
        assert len(user.events) == 1
        event = user.events[0]
        assert event.title == "Eswatini Business & Creatives Gala 2026"
        assert event.plan_tier == "standard"
        assert len(event.categories) == 8
        assert all(len(category.quotations) == 2 for category in event.categories)
        assert all(category.selected_quote is not None for category in event.categories)


def test_demo_is_one_click_and_read_only(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.test_cli_runner().invoke(args=["seed-demo"])
    client = app.test_client()

    response = client.get("/demo", follow_redirects=True)
    assert response.status_code == 200
    assert b"Eswatini Business &amp; Creatives Gala 2026" in response.data or b"Eswatini Business & Creatives Gala 2026" in response.data
    assert b"Demo mode:" in response.data

    response = client.post("/event/setup", data={
        "title": "Changed Demo",
        "event_type": "other",
        "budget_target": "1",
    })
    assert response.status_code == 302

    with app.app_context():
        event = db.session.scalar(db.select(Event))
        assert event.title == "Eswatini Business & Creatives Gala 2026"
        assert str(event.budget_target) == "120000.00"


def test_demo_invite_opens_same_event_view_only(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.test_cli_runner().invoke(args=["seed-demo"])
    owner = app.test_client()
    guest = app.test_client()

    owner.get("/demo")
    response = owner.post(
        "/team",
        data={"invitee_name": "Demo Guest", "role": "viewer"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    match = re.search(rb'value="(http://localhost/demo/join/[^"]+)"', response.data)
    assert match is not None
    invite_url = match.group(1).decode("utf-8")
    invite_path = invite_url.replace("http://localhost", "")

    joined = guest.get(invite_path, follow_redirects=True)
    assert joined.status_code == 200
    assert b"Eswatini Business" in joined.data
    assert b"view-only invitation" in joined.data

    blocked = guest.post("/budget", data={"name": "Should not save", "planned_amount": "50"})
    assert blocked.status_code == 302
    with app.app_context():
        event = db.session.scalar(db.select(Event))
        assert len(event.categories) == 8
