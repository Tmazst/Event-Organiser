from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from .extensions import db
from .models import VendorProduct, VendorStore


bp = Blueprint("vendors", __name__)


def owned_store():
    return db.session.scalar(select(VendorStore).where(VendorStore.owner_id == current_user.id))


@bp.route("/vendor/setup", methods=["GET", "POST"])
@login_required
def setup_store():
    if current_user.account_type != "vendor":
        return ("Not found", 404)
    store = owned_store()
    if request.method == "POST":
        values = {
            "store_name": request.form.get("store_name", "").strip(),
            "contact_phone": request.form.get("contact_phone", "").strip(),
            "contact_email": request.form.get("contact_email", "").strip().lower() or None,
            "location": request.form.get("location", "").strip(),
            "offering_summary": request.form.get("offering_summary", "").strip(),
        }
        if not all((values["store_name"], values["contact_phone"], values["location"], values["offering_summary"])):
            flash("Enter the store name, contact phone, location and what you supply.", "error")
        else:
            if store is None:
                store = VendorStore(owner_id=current_user.id)
                db.session.add(store)
            for field, value in values.items():
                setattr(store, field, value)
            db.session.commit()
            flash("Your vendor store has been saved.", "success")
            return redirect(url_for("vendors.dashboard"))
    return render_template("vendors/setup.html", store=store)


@bp.get("/vendor")
@login_required
def dashboard():
    if current_user.account_type != "vendor":
        return redirect(url_for("vendors.directory"))
    store = owned_store()
    if store is None:
        return redirect(url_for("vendors.setup_store"))
    return render_template("vendors/dashboard.html", store=store)


@bp.post("/vendor/products")
@login_required
def add_product():
    if current_user.account_type != "vendor":
        return ("Not found", 404)
    store = owned_store()
    if store is None:
        return redirect(url_for("vendors.setup_store"))

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    price_unit = request.form.get("price_unit", "").strip() or None
    price_input = request.form.get("price", "").strip()
    publish_price = request.form.get("publish_price") == "yes"
    price = None
    price_error = None
    if price_input:
        try:
            price = Decimal(price_input).quantize(Decimal("0.01"))
            if price < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            price_error = "Enter a valid product price."

    if not name:
        flash("Enter a product or service name.", "error")
    elif price_error:
        flash(price_error, "error")
    elif publish_price and price is None:
        flash("Enter a price before choosing to publish it.", "error")
    else:
        db.session.add(VendorProduct(
            name=name,
            description=description,
            price=price,
            price_unit=price_unit,
            publish_price=publish_price,
            store_id=store.id,
        ))
        db.session.commit()
        flash("Product added to your store.", "success")
    return redirect(url_for("vendors.dashboard"))


@bp.post("/vendor/products/<int:product_id>/delete")
@login_required
def delete_product(product_id):
    product = db.get_or_404(VendorProduct, product_id)
    if product.store.owner_id != current_user.id:
        return ("Not found", 404)
    db.session.delete(product)
    db.session.commit()
    flash("Product removed from your store.", "success")
    return redirect(url_for("vendors.dashboard"))


@bp.get("/vendors")
@login_required
def directory():
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
    return render_template("vendors/directory.html", stores=stores, query=query)


@bp.get("/vendors/<int:store_id>")
@login_required
def store_detail(store_id):
    store = db.get_or_404(VendorStore, store_id)
    return render_template("vendors/store_detail.html", store=store)
