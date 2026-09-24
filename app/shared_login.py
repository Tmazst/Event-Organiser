from urllib.parse import urlencode

from flask import Blueprint, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required, login_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import or_, select

from .extensions import db
from .models import User


bp = Blueprint("shared_login", __name__, url_prefix="/shared-login")


def _enabled():
    return current_app.config.get("SHARED_LOGIN_HANDOFF_ENABLED", False)


def _serializer(salt):
    secret = current_app.config.get("SHARED_LOGIN_SECRET") or ""
    if not secret:
        raise RuntimeError("Shared login secret is not configured.")
    return URLSafeTimedSerializer(secret_key=secret, salt=salt)


def _identity_payload(user):
    return {
        "email": user.email,
        "phone_number": user.phone_number,
        "name": user.name,
        "source": "umcimby",
        "target": "umshado",
    }


@bp.get("/to-umshado")
@login_required
def to_umshado():
    if not _enabled():
        return ("Not found", 404)
    destination = current_app.config.get("UMSHADO_SSO_RECEIVE_URL") or ""
    if not destination:
        flash("UMSHADO shared login is not configured yet.", "error")
        return redirect(url_for("main.index"))
    token = _serializer("umcimby-to-umshado").dumps(_identity_payload(current_user))
    separator = "&" if "?" in destination else "?"
    return redirect(f"{destination}{separator}{urlencode({'token': token})}")


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

    email = (payload.get("email") or "").strip().lower()
    phone = (payload.get("phone_number") or "").strip()
    clauses = []
    if email:
        clauses.append(User.email == email)
    if phone:
        clauses.append(User.phone_number == phone)
    user = db.session.scalar(select(User).where(or_(*clauses))) if clauses else None
    if user is None:
        flash("No Umcimby account was found for this UMSHADO account. Please register first.", "info")
        return redirect(url_for("main.register"))

    login_user(user)
    flash("Signed in through UMSHADO.", "success")
    destination = "vendors.dashboard" if user.account_type == "vendor" else "main.dashboard"
    return redirect(url_for(destination))
