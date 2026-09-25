import hashlib
import secrets
from urllib.parse import urlencode

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import SharedLoginUse, User


bp = Blueprint("shared_login", __name__, url_prefix="/shared-login")


def _enabled():
    return current_app.config.get("SHARED_LOGIN_HANDOFF_ENABLED", False)


def _serializer(salt):
    secret = current_app.config.get("SHARED_LOGIN_SECRET") or ""
    if not secret:
        raise RuntimeError("Shared login secret is not configured.")
    return URLSafeTimedSerializer(secret_key=secret, salt=salt)


def _identity_payload(user, *, provision=False):
    payload = {
        "email": user.email,
        "phone_number": user.phone_number,
        "name": user.name,
        "source": "umcimby",
        "target": "umshado",
        "account_type": user.account_type,
    }
    if provision:
        payload["provision"] = True
    return payload


def _matching_user(payload):
    email = (payload.get("email") or "").strip().lower()
    phone = (payload.get("phone_number") or "").strip()
    email_user = db.session.scalar(select(User).where(User.email == email)) if email else None
    phone_user = db.session.scalar(select(User).where(User.phone_number == phone)) if phone else None
    if email_user and phone_user and email_user.id != phone_user.id:
        return None, True
    return email_user or phone_user, False


def _consume_token(token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if db.session.scalar(select(SharedLoginUse).where(SharedLoginUse.token_hash == token_hash)):
        return False
    db.session.add(SharedLoginUse(token_hash=token_hash))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False
    return True


def _send_to_umshado(user, *, provision=False):
    destination = current_app.config.get("UMSHADO_SSO_RECEIVE_URL") or ""
    if not destination:
        flash("UMSHADO shared login is not configured yet.", "error")
        return redirect(url_for("main.login"))
    token = _serializer("umcimby-to-umshado").dumps(
        _identity_payload(user, provision=provision)
    )
    separator = "&" if "?" in destination else "?"
    return redirect(f"{destination}{separator}{urlencode({'token': token})}")


@bp.route("/continue-to-umshado", methods=["GET", "POST"])
def continue_to_umshado():
    """Authenticate an existing Umcimby account before provisioning UMSHADO."""
    if not _enabled():
        return ("Not found", 404)
    if current_user.is_authenticated:
        return _send_to_umshado(current_user, provision=True)
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db.session.scalar(select(User).where(User.email == email))
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            return _send_to_umshado(user, provision=True)
        flash("Incorrect Umcimby email or password.", "error")
    return render_template(
        "auth/shared_continue.html",
        source_name="Umcimby",
        destination_name="UMSHADO",
        account_type="",
    )


@bp.get("/to-umshado")
def to_umshado():
    if not _enabled():
        return ("Not found", 404)
    if not current_user.is_authenticated:
        return redirect(url_for("shared_login.continue_to_umshado"))
    return _send_to_umshado(current_user)


@bp.get("/from-umshado")
def from_umshado():
    if not _enabled():
        return ("Not found", 404)
    token = request.args.get("token", "")
    try:
        payload = _serializer("umshado-to-umcimby").loads(
            token,
            max_age=current_app.config.get("SHARED_LOGIN_MAX_AGE_SECONDS", 90),
        )
    except SignatureExpired:
        flash("That shared login link expired. Please try again from UMSHADO.", "error")
        return redirect(url_for("main.login"))
    except (BadSignature, RuntimeError):
        flash("That shared login link is invalid.", "error")
        return redirect(url_for("main.login"))

    if payload.get("source") != "umshado" or payload.get("target") != "umcimby":
        flash("That shared login link is invalid.", "error")
        return redirect(url_for("main.login"))

    user, identity_conflict = _matching_user(payload)
    if identity_conflict:
        flash("This shared account has conflicting email and phone records. Please sign in normally and contact support.", "error")
        return redirect(url_for("main.login"))

    if user is None and payload.get("provision"):
        email = (payload.get("email") or "").strip().lower()
        name = (payload.get("name") or "").strip() or "Umcimby user"
        phone = (payload.get("phone_number") or "").strip() or None
        account_type = payload.get("account_type", "organizer")
        if account_type not in {"organizer", "vendor"}:
            account_type = "organizer"
        if not email:
            flash("The UMSHADO account is missing an email address.", "error")
            return redirect(url_for("main.register"))
        user = User(
            name=name,
            email=email,
            phone_number=phone,
            phone_country="SZ",
            account_type=account_type,
        )
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
    elif user is None:
        flash("No Umcimby account was found for this UMSHADO account. Please register first.", "info")
        return redirect(url_for("main.register"))

    if not _consume_token(token):
        flash("That shared login link has already been used. Please start again from UMSHADO.", "error")
        return redirect(url_for("main.login"))

    login_user(user)
    flash("Signed in through UMSHADO.", "success")
    if payload.get("provision"):
        return redirect(url_for("vendors.setup_store" if user.account_type == "vendor" else "main.setup_event"))
    destination = "vendors.dashboard" if user.account_type == "vendor" else "main.dashboard"
    return redirect(url_for(destination))
