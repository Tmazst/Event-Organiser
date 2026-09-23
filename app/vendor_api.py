import hmac

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import or_, select

from .extensions import db
from .models import VendorProduct, VendorStore


bp = Blueprint("vendor_api", __name__, url_prefix="/api/vendors")


def _enabled():
    return (
        current_app.config.get("VENDOR_FEATURE_ENABLED", False)
        and current_app.config.get("VENDOR_API_ENABLED", False)
    )


def _authorized():
    configured = current_app.config.get("VENDOR_API_KEY") or ""
    supplied = request.headers.get("X-Vendor-API-Key", "")
    return bool(configured and supplied and hmac.compare_digest(configured, supplied))


def _guard():
    if not _enabled():
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
