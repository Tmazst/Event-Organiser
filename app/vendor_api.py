import hmac

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import or_, select

from .extensions import db
from .models import User, VendorProduct, VendorStore
from .phone_numbers import normalize_phone


bp = Blueprint("vendor_api", __name__, url_prefix="/api/vendors")


def _enabled():
    return (
        current_app.config.get("VENDOR_FEATURE_ENABLED", False)
        and current_app.config.get("VENDOR_API_ENABLED", False)
    )


def _accounts_enabled():
    return _enabled() and current_app.config.get("VENDOR_ACCOUNT_API_ENABLED", False)


def _authorized():
    configured = current_app.config.get("VENDOR_API_KEY") or ""
    supplied = request.headers.get("X-Vendor-API-Key", "")
    return bool(configured and supplied and hmac.compare_digest(configured, supplied))


def _guard(accounts=False):
    if not (_accounts_enabled() if accounts else _enabled()):
        return jsonify({"error": "Vendor API is disabled."}), 404
    if not _authorized():
        return jsonify({"error": "Unauthorized."}), 401
    return None


def _product_payload(product):
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": str(product.price) if product.price is not None else None,
        "price_unit": product.price_unit,
        "publish_price": bool(product.publish_price),
    }


def _store_payload(store, include_products=False):
    payload = {
        "id": store.id,
        "store_name": store.store_name,
        "contact_phone": store.contact_phone,
        "contact_email": store.contact_email,
        "location": store.location,
        "offering_summary": store.offering_summary,
    }
    if include_products:
        payload["products"] = [_product_payload(product) for product in store.products]
    return payload


def _account_payload(user):
    return {
        "exists": True,
        "is_vendor": user.account_type == "vendor",
        "name": user.name,
        "email": user.email,
        "phone_number": user.phone_number,
        "phone_country": user.phone_country,
        "has_store": bool(user.vendor_store) if user.account_type == "vendor" else False,
    }


@bp.get("")
def vendor_directory():
    blocked = _guard()
    if blocked:
        return blocked

    query = request.args.get("q", "").strip()
    statement = select(VendorStore).outerjoin(VendorProduct)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(
            VendorStore.store_name.ilike(pattern),
            VendorStore.location.ilike(pattern),
            VendorStore.offering_summary.ilike(pattern),
            VendorProduct.name.ilike(pattern),
            VendorProduct.description.ilike(pattern),
        ))
    stores = db.session.scalars(
        statement.distinct().order_by(VendorStore.store_name)
    ).all()
    return jsonify({"vendors": [_store_payload(store) for store in stores]})


@bp.get("/<int:store_id>")
def vendor_detail(store_id):
    blocked = _guard()
    if blocked:
        return blocked
    store = db.session.get(VendorStore, store_id)
    if store is None:
        return jsonify({"error": "Vendor not found."}), 404
    return jsonify(_store_payload(store, include_products=True))


@bp.post("/accounts/lookup")
def vendor_account_lookup():
    blocked = _guard(accounts=True)
    if blocked:
        return blocked

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    phone_value = (payload.get("phone_number") or "").strip()
    phone_country = (payload.get("phone_country") or "SZ").strip().upper()

    normalized_phone = None
    if phone_value:
        try:
            normalized_phone, _ = normalize_phone(phone_value, phone_country)
        except ValueError:
            return jsonify({"error": "Invalid phone number."}), 400

    if not email and not normalized_phone:
        return jsonify({"error": "Provide an email address or phone number."}), 400

    conditions = []
    if email:
        conditions.append(User.email == email)
    if normalized_phone:
        conditions.append(User.phone_number == normalized_phone)
    user = db.session.scalar(select(User).where(or_(*conditions)))
    if user is None:
        return jsonify({"exists": False, "is_vendor": False, "has_store": False})
    return jsonify(_account_payload(user))


@bp.post("/accounts/register")
def vendor_account_register():
    blocked = _guard(accounts=True)
    if blocked:
        return blocked

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    phone_country = (payload.get("phone_country") or "SZ").strip().upper()
    password = payload.get("password") or ""

    try:
        phone_number, phone_country = normalize_phone(payload.get("phone_number"), phone_country)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if not name or not email or len(password) < 6:
        return jsonify({"error": "Name, email, phone number and a password of at least 6 characters are required."}), 400

    existing = db.session.scalar(
        select(User).where(or_(User.email == email, User.phone_number == phone_number))
    )
    if existing is not None:
        response = _account_payload(existing)
        response["error"] = (
            "Vendor account already exists. Please sign in through Umcimby."
            if existing.account_type == "vendor"
            else "An Umcimby account already exists with these details."
        )
        return jsonify(response), 409

    user = User(
        name=name,
        email=email,
        phone_number=phone_number,
        phone_country=phone_country,
        account_type="vendor",
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({
        "created": True,
        "account": _account_payload(user),
    }), 201
