from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import Invitation, Payment, Event, EventMember


class TestConfig:
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CSRF_PROTECT = False
    FREE_BUDGET_ITEM_LIMIT = 4
    OWNER_PLAN_PRICE = "40.00"
    STAKEHOLDER_PRICE = "30.00"
    PAYMENT_CURRENCY = "SZL"
    MOJAPOS_MOCK_AUTO_COMPLETE = True


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("MOJAPOS_MOCK_MODE", "true")
    application = create_app(TestConfig)
    application.config["EVENT_PHOTO_FOLDER"] = tmp_path / "uploads" / "events"
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, name, email, phone, invite_token=""):
    return client.post("/register", data={
        "name": name, "email": email, "phone_number": phone,
        "password": "secret1", "invite_token": invite_token,
    })


def create_owner_event(client):
    register(client, "Owner", "owner@example.com", "76123456")
    client.post("/event/setup", data={
        "title": "Manzini Business Expo", "event_type": "conference",
        "budget_target": "80000", "location": "Manzini",
    })


def test_free_limit_and_budget_totals(app, client):
    create_owner_event(client)
    for number in range(4):
        response = client.post("/budget", data={
            "name": f"Item {number}", "planned_amount": "10000",
        })
        assert response.status_code == 302

    blocked = client.post("/budget", data={"name": "Fifth item", "planned_amount": "5000"})
    assert blocked.headers["Location"].endswith("/pricing")

    client.post("/budget/1/quotes", data={"vendor_name": "Tech Xolutions", "amount": "8500"})
    client.post("/quotes/1/select")
    budget = client.get("/budget")
    assert b"E8500.00" in budget.data
    with app.app_context():
        assert len(db.session.scalar(select(Event)).categories) == 4


def test_standard_upgrade_is_exactly_e40(app, client):
    create_owner_event(client)
    response = client.post("/billing/upgrade", follow_redirects=True)
    assert b"Payment confirmed" in response.data
    with app.app_context():
        event = db.session.scalar(select(Event))
        payment = db.session.scalar(select(Payment))
        assert event.plan_tier == "standard"
        assert str(payment.amount) == "40.00"
        assert payment.status == "completed"


def test_owner_paid_invitation_adds_registered_stakeholder(app, client):
    create_owner_event(client)
    client.post("/billing/upgrade")
    client.post("/team", data={
        "invitee_name": "Nomsa", "role": "finance_manager", "payer": "owner",
    })
    with app.app_context():
        invitation = db.session.scalar(select(Invitation))
        token = invitation.token
        assert invitation.status == "paid"
        payment = db.session.scalars(
            select(Payment).where(Payment.kind == "owner_pays_invite")
        ).one()
        assert str(payment.amount) == "30.00"

    client.post("/logout")
    register(client, "Nomsa", "nomsa@example.com", "76234567", token)
    joined = client.post(f"/invite/{token}/join", follow_redirects=True)
    assert b"Conference" in joined.data
    with app.app_context():
        member = db.session.scalar(select(EventMember))
        assert member.role == "finance_manager"


def test_invitee_can_pay_their_own_e30_access(app, client):
    create_owner_event(client)
    client.post("/billing/upgrade")
    client.post("/team", data={
        "invitee_name": "Bongani", "role": "team_member", "payer": "invitee",
    })
    with app.app_context():
        token = db.session.scalar(select(Invitation)).token

    client.post("/logout")
    register(client, "Bongani", "bongani@example.com", "76345678", token)
    paid = client.post(f"/invite/{token}/join", follow_redirects=True)
    assert b"Payment confirmed" in paid.data
    with app.app_context():
        invitation = db.session.scalar(select(Invitation))
        payment = db.session.scalars(
            select(Payment).where(Payment.kind == "invitee_pays_invite")
        ).one()
        assert invitation.status == "accepted"
        assert str(payment.amount) == "30.00"
        assert db.session.scalar(select(EventMember)) is not None


def test_account_details_can_be_updated(app, client):
    create_owner_event(client)
    response = client.post("/account", data={
        "name": "Updated Owner", "email": "updated@example.com", "phone_number": "76456789",
    }, follow_redirects=True)
    assert b"Account details updated" in response.data
    assert b"Free plan" in response.data
    with app.app_context():
        user = db.session.scalar(select(Event).where(Event.owner_id.is_not(None))).owner
        assert user.name == "Updated Owner"
        assert user.phone_number == "26876456789"


def test_owner_can_upload_event_photo(app, client):
    create_owner_event(client)
    photo = BytesIO()
    Image.new("RGB", (80, 60), "#176b63").save(photo, "PNG")
    photo.seek(0)
    response = client.post(
        "/event/photo", data={"profile_image": (photo, "event.png")},
        content_type="multipart/form-data", follow_redirects=True,
    )
    assert b"event photo has been updated" in response.data
    with app.app_context():
        event = db.session.scalar(select(Event))
        assert event.profile_image.endswith(".jpg")
        saved = app.config["EVENT_PHOTO_FOLDER"].parent / event.profile_image
        assert saved.is_file()


def test_pwa_files_are_public(client):
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.mimetype == "application/manifest+json"
    assert manifest.json["name"] == "Event Organiser"
    assert manifest.json["display"] == "standalone"

    worker = client.get("/service-worker.js")
    assert worker.status_code == 200
    assert worker.headers["Service-Worker-Allowed"] == "/"
    assert b"event-organiser-static-v1" in worker.data

    offline = client.get("/offline")
    assert offline.status_code == 200
    assert b"offline" in offline.data


def test_event_report_downloads_pdf(client):
    create_owner_event(client)
    client.post("/budget", data={"name": "Venue", "planned_amount": "12000"})
    client.post("/budget/1/quotes", data={"vendor_name": "Mavuso Centre", "amount": "11500"})
    client.post("/quotes/1/select")
    response = client.get("/report")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "manzini-business-expo-report.pdf" in response.headers["Content-Disposition"]
