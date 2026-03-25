from __future__ import annotations

import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///inventory.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class StorageLocation(db.Model):
    __tablename__ = "storage_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    room = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.String(500), nullable=True)

    items = db.relationship("InventoryItem", back_populates="location", lazy=True)


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    website = db.Column(db.String(255), nullable=True)
    contact = db.Column(db.String(255), nullable=True)

    items = db.relationship("InventoryItem", back_populates="vendor", lazy=True)


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(120), nullable=True)
    category = db.Column(db.String(120), nullable=True)
    qty_main_office = db.Column(db.Integer, nullable=False, default=0)
    qty_storage = db.Column(db.Integer, nullable=False, default=0)
    reorder_threshold = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    location_id = db.Column(db.Integer, db.ForeignKey("storage_locations.id"), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)

    location = db.relationship("StorageLocation", back_populates="items")
    vendor = db.relationship("Vendor", back_populates="items")
    requirements = db.relationship(
        "ClientRequirement",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy=True,
    )


class ClientRequirement(db.Model):
    __tablename__ = "client_requirements"

    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(150), nullable=False)
    project_name = db.Column(db.String(150), nullable=True)
    quantity_needed = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Needed")
    notes = db.Column(db.String(500), nullable=True)

    item_id = db.Column(db.Integer, db.ForeignKey("inventory_items.id"), nullable=False)
    item = db.relationship("InventoryItem", back_populates="requirements")


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    g.user = User.query.get(user_id) if user_id else None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user.id
        flash("Welcome back.", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    items = InventoryItem.query.order_by(InventoryItem.name.asc()).all()
    low_stock = [
        item
        for item in items
        if (item.qty_main_office + item.qty_storage) <= item.reorder_threshold
    ]
    requirements = ClientRequirement.query.order_by(ClientRequirement.client_name.asc()).all()
    return render_template(
        "index.html",
        items=items,
        low_stock=low_stock,
        requirements=requirements,
    )


@app.route("/inventory/add", methods=["POST"])
@login_required
def add_item():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Item name is required.", "error")
        return redirect(url_for("index"))

    item = InventoryItem(
        name=name,
        sku=request.form.get("sku", "").strip() or None,
        category=request.form.get("category", "").strip() or None,
        qty_main_office=max(int(request.form.get("qty_main_office", 0) or 0), 0),
        qty_storage=max(int(request.form.get("qty_storage", 0) or 0), 0),
        reorder_threshold=max(int(request.form.get("reorder_threshold", 0) or 0), 0),
        location_id=(int(request.form["location_id"]) if request.form.get("location_id") else None),
        vendor_id=(int(request.form["vendor_id"]) if request.form.get("vendor_id") else None),
        last_updated=datetime.utcnow(),
    )
    db.session.add(item)
    db.session.commit()
    flash("Inventory item added.", "success")
    return redirect(url_for("index"))


@app.route("/inventory/<int:item_id>/update", methods=["POST"])
@login_required
def update_item(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    item.name = request.form.get("name", item.name).strip()
    item.sku = request.form.get("sku", item.sku or "").strip() or None
    item.category = request.form.get("category", item.category or "").strip() or None
    item.qty_main_office = max(int(request.form.get("qty_main_office", item.qty_main_office) or 0), 0)
    item.qty_storage = max(int(request.form.get("qty_storage", item.qty_storage) or 0), 0)
    item.reorder_threshold = max(
        int(request.form.get("reorder_threshold", item.reorder_threshold) or 0), 0
    )
    item.location_id = int(request.form["location_id"]) if request.form.get("location_id") else None
    item.vendor_id = int(request.form["vendor_id"]) if request.form.get("vendor_id") else None
    item.last_updated = datetime.utcnow()

    db.session.commit()
    flash("Inventory updated.", "success")
    return redirect(url_for("index"))


@app.route("/inventory/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id: int):
    item = InventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Inventory item deleted.", "success")
    return redirect(url_for("index"))


@app.route("/requirements/add", methods=["POST"])
@login_required
def add_requirement():
    item_id = request.form.get("item_id")
    client_name = request.form.get("client_name", "").strip()
    if not item_id or not client_name:
        flash("Client name and item are required.", "error")
        return redirect(url_for("index"))

    requirement = ClientRequirement(
        item_id=int(item_id),
        client_name=client_name,
        project_name=request.form.get("project_name", "").strip() or None,
        quantity_needed=max(int(request.form.get("quantity_needed", 1) or 1), 1),
        status=request.form.get("status", "Needed"),
        notes=request.form.get("notes", "").strip() or None,
    )
    db.session.add(requirement)
    db.session.commit()
    flash("Client requirement added.", "success")
    return redirect(url_for("index"))


@app.route("/requirements/<int:requirement_id>/status", methods=["POST"])
@login_required
def update_requirement_status(requirement_id: int):
    requirement = ClientRequirement.query.get_or_404(requirement_id)
    requirement.status = request.form.get("status", requirement.status)
    requirement.quantity_needed = max(
        int(request.form.get("quantity_needed", requirement.quantity_needed) or 1), 1
    )
    db.session.commit()
    flash("Requirement status updated.", "success")
    return redirect(url_for("index"))


@app.route("/requirements/<int:requirement_id>/delete", methods=["POST"])
@login_required
def delete_requirement(requirement_id: int):
    requirement = ClientRequirement.query.get_or_404(requirement_id)
    db.session.delete(requirement)
    db.session.commit()
    flash("Requirement removed.", "success")
    return redirect(url_for("index"))


@app.route("/locations/add", methods=["POST"])
@login_required
def add_location():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Location name is required.", "error")
        return redirect(url_for("settings"))

    existing = StorageLocation.query.filter_by(name=name).first()
    if existing:
        flash("Location already exists.", "error")
        return redirect(url_for("settings"))

    location = StorageLocation(
        name=name,
        room=request.form.get("room", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
    )
    db.session.add(location)
    db.session.commit()
    flash("Storage location added.", "success")
    return redirect(url_for("settings"))


@app.route("/locations/<int:location_id>/delete", methods=["POST"])
@login_required
def delete_location(location_id: int):
    location = StorageLocation.query.get_or_404(location_id)
    for item in location.items:
        item.location_id = None
    db.session.delete(location)
    db.session.commit()
    flash("Storage location deleted.", "success")
    return redirect(url_for("settings"))


@app.route("/vendors/add", methods=["POST"])
@login_required
def add_vendor():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Vendor name is required.", "error")
        return redirect(url_for("settings"))

    existing = Vendor.query.filter_by(name=name).first()
    if existing:
        flash("Vendor already exists.", "error")
        return redirect(url_for("settings"))

    vendor = Vendor(
        name=name,
        website=request.form.get("website", "").strip() or None,
        contact=request.form.get("contact", "").strip() or None,
    )
    db.session.add(vendor)
    db.session.commit()
    flash("Vendor added.", "success")
    return redirect(url_for("settings"))


@app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
@login_required
def delete_vendor(vendor_id: int):
    vendor = Vendor.query.get_or_404(vendor_id)
    for item in vendor.items:
        item.vendor_id = None
    db.session.delete(vendor)
    db.session.commit()
    flash("Vendor deleted.", "success")
    return redirect(url_for("settings"))


@app.route("/settings")
@login_required
def settings():
    return render_template(
        "settings.html",
        locations=StorageLocation.query.order_by(StorageLocation.name.asc()).all(),
        vendors=Vendor.query.order_by(Vendor.name.asc()).all(),
    )


@app.context_processor
def inject_lookups():
    if g.user is None:
        return {"all_locations": [], "all_vendors": [], "all_items": []}

    return {
        "all_locations": StorageLocation.query.order_by(StorageLocation.name.asc()).all(),
        "all_vendors": Vendor.query.order_by(Vendor.name.asc()).all(),
        "all_items": InventoryItem.query.order_by(InventoryItem.name.asc()).all(),
    }


def init_db() -> None:
    with app.app_context():
        db.create_all()
        seed_admin_if_missing()


def seed_admin_if_missing() -> None:
    default_username = os.environ.get("DEFAULT_ADMIN_USER", "admin")
    default_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "changeme")

    if User.query.filter_by(username=default_username).first() is None:
        user = User(username=default_username)
        user.set_password(default_password)
        db.session.add(user)
        db.session.commit()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
