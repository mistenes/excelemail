from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import ProgrammingError

from . import db, ensure_company_schema
from .models import Company, Shipment


bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    try:
        companies = Company.query.order_by(Company.name).all()
    except ProgrammingError as exc:
        current_app.logger.warning(
            "Company query failed; attempting schema upgrade", exc_info=exc
        )
        db.session.rollback()
        if not ensure_company_schema(current_app):
            flash(
                "The company table could not be upgraded automatically. Please try again later.",
                "error",
            )
            companies = []
        else:
            try:
                companies = Company.query.order_by(Company.name).all()
            except ProgrammingError as exc2:  # pragma: no cover - defensive logging
                current_app.logger.exception(
                    "Company query failed again after schema upgrade", exc_info=exc2
                )
                flash(
                    "The company records could not be loaded after an automatic upgrade.",
                    "error",
                )
                companies = []
    shipments = (
        Shipment.query.order_by(Shipment.created_at.desc())
        .limit(10)
        .all()
        if companies
        else []
    )
    return render_template(
        "index.html", companies=companies, shipments=shipments
    )


@bp.route("/shipments", methods=["POST"])
def create_shipment():
    form = request.form
    required_fields = [
        "origin_id",
        "destination_id",
        "po_number",
        "sap_number",
        "order_number",
        "order_date",
        "price",
        "weight",
        "time_slot",
    ]
    missing = [field for field in required_fields if not form.get(field)]
    if missing:
        flash(f"Missing fields: {', '.join(missing)}", "error")
        return redirect(url_for("main.index"))

    if form.get("origin_id") == form.get("destination_id"):
        flash("Origin and destination must be different companies.", "error")
        return redirect(url_for("main.index"))

    try:
        order_date = datetime.strptime(form["order_date"], "%Y-%m-%d").date()
        price = float(form["price"])
        weight = float(form["weight"])
    except ValueError:
        flash("Date must be YYYY-MM-DD and price/weight must be numbers.", "error")
        return redirect(url_for("main.index"))

    shipment = Shipment(
        origin_id=int(form["origin_id"]),
        destination_id=int(form["destination_id"]),
        po_number=form["po_number"].strip(),
        sap_number=form["sap_number"].strip(),
        order_number=form["order_number"].strip(),
        order_date=order_date,
        price=price,
        weight=weight,
        time_slot=form["time_slot"].strip(),
    )

    db.session.add(shipment)
    db.session.commit()

    flash("Shipment created successfully.", "success")
    return redirect(url_for("main.index"))


@bp.route("/companies/upload", methods=["GET", "POST"])
def upload_companies():
    if not current_app.config.get("COMPANY_SCHEMA_CHECKED"):
        ensure_company_schema(current_app)

    if request.method == "POST":
        fields = ["name", "street", "street_number", "postal_code", "city"]
        company_data = {field: request.form.get(field, "").strip() for field in fields}
        missing = [field for field, value in company_data.items() if not value]

        if missing:
            flash(
                "All company details are required (name, street, street number, postal code, city).",
                "error",
            )
            return redirect(url_for("main.upload_companies"))

        try:
            existing = Company.query.filter_by(name=company_data["name"]).first()
        except ProgrammingError as exc:
            current_app.logger.warning(
                "Company lookup failed; attempting schema upgrade", exc_info=exc
            )
            db.session.rollback()
            if not ensure_company_schema(current_app):
                flash(
                    "Could not prepare the company table automatically. Please retry later.",
                    "error",
                )
                return redirect(url_for("main.upload_companies"))
            try:
                existing = Company.query.filter_by(name=company_data["name"]).first()
            except ProgrammingError as exc2:  # pragma: no cover - defensive logging
                current_app.logger.exception(
                    "Company lookup failed again after schema upgrade", exc_info=exc2
                )
                flash(
                    "Could not read the company table after an automatic upgrade. Please retry later.",
                    "error",
                )
                return redirect(url_for("main.upload_companies"))

        if existing:
            flash("A company with this name already exists.", "info")
            return redirect(url_for("main.upload_companies"))

        def create_company():
            company = Company(
                name=company_data["name"],
                street=company_data["street"],
                street_number=company_data["street_number"],
                postal_code=company_data["postal_code"],
                city=company_data["city"],
            )
            if hasattr(company, "address"):
                street_part = " ".join(
                    part
                    for part in (
                        company_data["street"],
                        company_data["street_number"],
                    )
                    if part
                ).strip()
                city_part = " ".join(
                    part
                    for part in (
                        company_data["postal_code"],
                        company_data["city"],
                    )
                    if part
                ).strip()
                company.address = ", ".join(
                    part for part in (street_part, city_part) if part
                )
            return company

        try:
            db.session.add(create_company())
            db.session.commit()
        except ProgrammingError as exc:
            current_app.logger.warning(
                "Company create failed; attempting schema upgrade", exc_info=exc
            )
            db.session.rollback()
            if not ensure_company_schema(current_app):
                flash(
                    "Could not adjust the company table automatically. Please retry later.",
                    "error",
                )
                return redirect(url_for("main.upload_companies"))

            try:
                db.session.add(create_company())
                db.session.commit()
            except ProgrammingError as exc2:  # pragma: no cover - defensive logging
                current_app.logger.exception(
                    "Company create failed again after schema upgrade", exc_info=exc2
                )
                db.session.rollback()
                flash(
                    "Saving the company failed because the table is still out of date.",
                    "error",
                )
                return redirect(url_for("main.upload_companies"))

        flash("Company added successfully.", "success")
        return redirect(url_for("main.index"))

    return render_template("upload.html")
