from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=True, index=True)
    phone_country = db.Column(db.String(2), default="SZ", nullable=False, index=True)
    account_type = db.Column(db.String(20), default="organizer", nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    events = db.relationship("Event", backref="owner", lazy=True, cascade="all, delete-orphan")
    memberships = db.relationship("EventMember", backref="user", lazy=True, cascade="all, delete-orphan")
    vendor_store = db.relationship(
        "VendorStore", backref="owner", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def phone_display(self):
        if not self.phone_number:
            return ""
        from .phone_numbers import format_phone_for_display
        return format_phone_for_display(self.phone_number, self.phone_country)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    event_type = db.Column(db.String(60), nullable=False, default="other")
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=True)
    location = db.Column(db.String(160), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    budget_target = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    plan_tier = db.Column(db.String(20), default="free", nullable=False)
    upgraded_at = db.Column(db.DateTime, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    categories = db.relationship("BudgetCategory", backref="event", lazy=True, cascade="all, delete-orphan")
    members = db.relationship("EventMember", backref="event", lazy=True, cascade="all, delete-orphan")
    invitations = db.relationship("Invitation", backref="event", lazy=True, cascade="all, delete-orphan")

    @property
    def estimated_total(self):
        return sum((category.selected_amount for category in self.categories), start=0)


class VendorStore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(160), nullable=False, index=True)
    contact_phone = db.Column(db.String(40), nullable=False)
    contact_email = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(160), nullable=False, index=True)
    offering_summary = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    products = db.relationship(
        "VendorProduct", backref="store", lazy=True, cascade="all, delete-orphan"
    )


class VendorProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=True)
    price_unit = db.Column(db.String(60), nullable=True)
    publish_price = db.Column(db.Boolean, default=False, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("vendor_store.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class BudgetCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    planned_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False, index=True)
    quotations = db.relationship("Quotation", backref="category", lazy=True, cascade="all, delete-orphan")

    @property
    def selected_quote(self):
        return next((quote for quote in self.quotations if quote.is_selected), None)

    @property
    def selected_amount(self):
        return self.selected_quote.amount if self.selected_quote else self.planned_amount


class Quotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(160), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    contact = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    valid_until = db.Column(db.Date, nullable=True)
    is_selected = db.Column(db.Boolean, default=False, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("budget_category.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class EventMember(db.Model):
    __table_args__ = (db.UniqueConstraint("event_id", "user_id", name="uq_event_member"),)

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role = db.Column(db.String(40), default="team_member", nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False, index=True)
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    invitee_name = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(40), default="team_member", nullable=False)
    payer = db.Column(db.String(20), nullable=False)  # owner | invitee
    status = db.Column(db.String(30), default="pending", nullable=False)
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_ref_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="SZL", nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False, index=True)
    invitation_id = db.Column(db.Integer, db.ForeignKey("invitation.id"), nullable=True, index=True)
    gateway_transaction_id = db.Column(db.String(120), nullable=True)
    provider_reference = db.Column(db.String(120), nullable=True)
    failure_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    event = db.relationship("Event", foreign_keys=[event_id])
    invitation = db.relationship("Invitation", foreign_keys=[invitation_id])


class SharedLoginUse(db.Model):
    """Consumed shared-login tokens, stored as hashes to block replay."""

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    consumed_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
