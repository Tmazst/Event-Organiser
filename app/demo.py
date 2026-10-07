from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import secrets
import shutil

import click
from flask import Blueprint, current_app, flash, redirect, request, session, url_for
from flask.cli import with_appcontext
from flask_login import current_user, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select

from .extensions import db
from .models import BudgetCategory, Quotation, User, Event


bp = Blueprint("demo", __name__)
DEMO_INVITE_MAX_AGE = 90 * 60


def _demo_email():
    return current_app.config.get("DEMO_ACCOUNT_EMAIL", "demo@umcimby.app").strip().lower()


def _is_demo_user(user):
    return bool(
        current_app.config.get("DEMO_MODE_ENABLED", True)
        and user.is_authenticated
        and user.email.lower() == _demo_email()
    )


def _demo_invite_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="umcimby-demo-team-invite")


def _attach_demo_photo(event):
    source = Path(current_app.static_folder) / "images" / "demo" / "demo-event.jpg"
    if not source.is_file():
        event.profile_image = None
        return False

    folder = Path(current_app.config["EVENT_PHOTO_FOLDER"]) / str(event.id)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "demo-event.jpg"
    shutil.copyfile(source, destination)
    event.profile_image = f"events/{event.id}/demo-event.jpg"
    return True


def seed_demo_event():
    """Create or reset the public Umcimby marketing demo."""
    email = _demo_email()
    user = db.session.scalar(select(User).where(User.email == email))

    if user is None:
        user = User(
            name="Umcimby Demo Organizer",
            email=email,
            phone_number=None,
            phone_country="SZ",
            account_type="organizer",
        )
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.flush()
    else:
        user.name = "Umcimby Demo Organizer"
        user.account_type = "organizer"
        for event in list(user.events):
            db.session.delete(event)
        db.session.flush()

    event = Event(
        title="Eswatini Business & Creatives Gala 2026",
        event_type="corporate",
        description=(
            "A polished networking and awards evening bringing together entrepreneurs, "
            "creatives, partners and invited guests from across Eswatini."
        ),
        event_date=date(2026, 11, 28),
        location="Ezulwini, Eswatini",
        budget_target=Decimal("120000.00"),
        plan_tier="standard",
        upgraded_at=datetime.now(timezone.utc),
        owner_id=user.id,
    )
    db.session.add(event)
    db.session.flush()
    photo_attached = _attach_demo_photo(event)

    budget = [
        ("Venue", "22000.00", [("Ezulwini Events Demo Venue", "21500.00"), ("Valley Conference Demo Venue", "23500.00")]),
        ("Catering", "30000.00", [("Royal Table Demo Catering", "29200.00"), ("Gather & Dine Demo Catering", "31800.00")]),
        ("Décor & Staging", "16000.00", [("Modern Moments Demo Décor", "15500.00"), ("Signature Stage Demo Events", "16900.00")]),
        ("Sound & Lighting", "12500.00", [("Clear Sound Demo Productions", "12000.00"), ("Live Beam Demo AV", "13200.00")]),
        ("Photography & Video", "9500.00", [("Frame Story Demo Media", "9000.00"), ("Focus House Demo Studio", "10200.00")]),
        ("Entertainment", "10500.00", [("Pulse Live Demo Entertainment", "10000.00"), ("Stage Culture Demo Artists", "11200.00")]),
        ("Branding & Printing", "7000.00", [("BrandWorks Demo Print", "6800.00"), ("Creative Press Demo Studio", "7500.00")]),
        ("Transport & Logistics", "6500.00", [("Swift Move Demo Logistics", "6200.00"), ("Event Route Demo Transport", "6900.00")]),
    ]

    for category_name, planned_amount, quotes in budget:
        category = BudgetCategory(
            name=category_name,
            planned_amount=Decimal(planned_amount),
            event_id=event.id,
        )
        db.session.add(category)
        db.session.flush()
        for index, (vendor_name, amount) in enumerate(quotes):
            db.session.add(Quotation(
                vendor_name=vendor_name,
                amount=Decimal(amount),
                contact="Demo quotation",
                notes="Sample quotation included for the Umcimby product demo.",
                valid_until=date(2026, 11, 15),
                is_selected=index == 0,
                category_id=category.id,
            ))

    db.session.commit()
    return user, photo_attached


@bp.get("/demo")
def enter_demo():
    if not current_app.config.get("DEMO_MODE_ENABLED", True):
        return ("Not found", 404)
    user = db.session.scalar(select(User).where(User.email == _demo_email()))
    if user is None:
        flash("The demo account is not prepared yet. Please try again shortly.", "info")
        return redirect(url_for("main.login"))
    if current_user.is_authenticated and current_user.id != user.id:
        logout_user()
    login_user(user)
    session.pop("shared_vendor_role_is_vendor", None)
    session.pop("demo_invitation", None)
    session.pop("demo_invited_name", None)
    session.pop("demo_invited_role", None)
    session["demo_access_mode"] = "primary"
    flash("You are viewing the Umcimby demo. Changes are disabled so the demo stays ready for everyone.", "info")
    return redirect(url_for("main.dashboard"))


@bp.get("/demo/join/<token>")
def join_demo_invitation(token):
    if not current_app.config.get("DEMO_MODE_ENABLED", True):
        return ("Not found", 404)
    try:
        payload = _demo_invite_serializer().loads(token, max_age=DEMO_INVITE_MAX_AGE)
    except SignatureExpired:
        flash("This demo invitation has expired. Ask the sender to create a new one.", "info")
        return redirect(url_for("main.login"))
    except BadSignature:
        flash("This demo invitation is invalid.", "error")
        return redirect(url_for("main.login"))
    if payload.get("purpose") != "demo-view":
        return ("Not found", 404)

    user = db.session.scalar(select(User).where(User.email == _demo_email()))
    if user is None:
        flash("The demo account is not prepared yet.", "info")
        return redirect(url_for("main.login"))
    if current_user.is_authenticated and current_user.id != user.id:
        logout_user()
    login_user(user)
    session.pop("shared_vendor_role_is_vendor", None)
    session["demo_access_mode"] = "invited"
    session["demo_invited_name"] = payload.get("name")
    session["demo_invited_role"] = payload.get("role")
    flash("You joined the Umcimby demo in view-only mode.", "success")
    return redirect(url_for("main.dashboard"))


def _create_demo_invitation():
    if session.get("demo_access_mode", "primary") != "primary":
        flash("Only the main demo visitor can create temporary invitations.", "info")
        return redirect(url_for("billing.team"))

    role = request.form.get("role", "viewer")
    if role not in {"co_organizer", "finance_manager", "vendor_coordinator", "team_member", "viewer"}:
        role = "viewer"
    invitee_name = request.form.get("invitee_name", "").strip() or None
    token = _demo_invite_serializer().dumps(
        {
            "purpose": "demo-view",
            "nonce": secrets.token_urlsafe(10),
            "name": invitee_name,
            "role": role,
        }
    )
    session["demo_invitation"] = {
        "name": invitee_name,
        "role": role,
        "url": url_for("demo.join_demo_invitation", token=token, _external=True),
    }
    flash("Temporary demo invitation created. It will expire in 90 minutes.", "success")
    return redirect(url_for("billing.team"))


def demo_read_only_guard():
    if not _is_demo_user(current_user):
        return None
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.endpoint == "main.logout":
        return None
    if request.endpoint == "billing.team" and request.method == "POST":
        return _create_demo_invitation()
    flash("This is a read-only demo. Create your own account to save changes.", "info")
    return redirect(request.referrer or url_for("main.dashboard"))


def demo_context():
    is_demo = _is_demo_user(current_user)
    access_mode = session.get("demo_access_mode", "primary") if is_demo else None
    return {
        "is_demo_account": is_demo,
        "demo_can_invite": bool(is_demo and access_mode == "primary"),
        "demo_invitation": session.get("demo_invitation") if is_demo else None,
        "demo_invited_name": session.get("demo_invited_name") if is_demo else None,
        "demo_invited_role": session.get("demo_invited_role") if is_demo else None,
    }


@click.command("seed-demo")
@with_appcontext
def seed_demo_command():
    _, photo_attached = seed_demo_event()
    click.echo("Umcimby demo event is ready.")
    if photo_attached:
        click.echo("Demo event image attached.")
    else:
        click.echo("Demo image not found. Add app/static/images/demo/demo-event.jpg and run seed-demo again.")


def register_demo(app):
    app.register_blueprint(bp)
    app.before_request(demo_read_only_guard)
    app.context_processor(demo_context)
    app.cli.add_command(seed_demo_command)
