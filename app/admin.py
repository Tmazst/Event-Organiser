from functools import wraps

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import func, select

from .extensions import db
from .models import Event, Payment, User, VendorStore


bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not (current_user.is_admin or current_user.is_super_admin):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@bp.get("")
@bp.get("/")
@admin_required
def dashboard():
    total_users = db.session.scalar(select(func.count(User.id))) or 0
    total_events = db.session.scalar(select(func.count(Event.id))) or 0
    total_vendors = db.session.scalar(select(func.count(VendorStore.id))) or 0
    total_payments = db.session.scalar(select(func.count(Payment.id))) or 0
    completed_revenue = db.session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed")
    ) or 0

    recent_users = db.session.scalars(
        select(User).order_by(User.created_at.desc()).limit(8)
    ).all()
    recent_events = db.session.scalars(
        select(Event).order_by(Event.created_at.desc()).limit(8)
    ).all()
    recent_payments = db.session.scalars(
        select(Payment).order_by(Payment.created_at.desc()).limit(8)
    ).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_events=total_events,
        total_vendors=total_vendors,
        total_payments=total_payments,
        completed_revenue=completed_revenue,
        recent_users=recent_users,
        recent_events=recent_events,
        recent_payments=recent_payments,
    )


@bp.get("/users")
@admin_required
def users():
    users = db.session.scalars(select(User).order_by(User.created_at.desc())).all()
    return render_template("admin/users.html", users=users)


@bp.get("/events")
@admin_required
def events():
    events = db.session.scalars(select(Event).order_by(Event.created_at.desc())).all()
    return render_template("admin/events.html", events=events)


@bp.get("/vendors")
@admin_required
def vendors():
    stores = db.session.scalars(
        select(VendorStore).order_by(VendorStore.created_at.desc())
    ).all()
    return render_template("admin/vendors.html", stores=stores)


@bp.get("/payments")
@admin_required
def payments():
    payments = db.session.scalars(
        select(Payment).order_by(Payment.created_at.desc())
    ).all()
    return render_template("admin/payments.html", payments=payments)
