import csv
from datetime import datetime
from io import TextIOWrapper

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
        ensure_company_schema(current_app)
        companies = Company.query.order_by(Company.name).all()
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
    if request.method == "POST":
        if not current_app.config.get("COMPANY_SCHEMA_CHECKED"):
            ensure_company_schema(current_app)

        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Please choose a CSV file to upload.", "error")
            return redirect(url_for("main.upload_companies"))

        file.stream.seek(0)
        csv_file = TextIOWrapper(file.stream, encoding="utf-8")
        reader = csv.DictReader(csv_file)
        rows = [
            {k.lower(): (v or "").strip() for k, v in row.items() if k}
            for row in reader
        ]

        def import_companies(entries):
            added = 0
            skipped = 0

            for normalized in entries:
                name = normalized.get("name")
                street = normalized.get("street")
                street_number = normalized.get("street_number")
                postal_code = normalized.get("postal_code")
                city = normalized.get("city")

                if not all([name, street, street_number, postal_code, city]):
                    skipped += 1
                    continue

                if Company.query.filter_by(name=name).first():
                    skipped += 1
                    continue

                company = Company(
                    name=name,
                    street=street,
                    street_number=street_number,
                    postal_code=postal_code,
                    city=city,
                )
                db.session.add(company)
                added += 1

            return added, skipped

        try:
            added, skipped = import_companies(rows)
            db.session.commit()
        except ProgrammingError as exc:
            current_app.logger.warning(
                "Company upload failed; attempting schema upgrade", exc_info=exc
            )
            db.session.rollback()
            db.session.close()

            if not ensure_company_schema(current_app):
                flash(
                    "Could not adjust the company table automatically. Please retry later.",
                    "error",
                )
                return redirect(url_for("main.upload_companies"))

            try:
                added, skipped = import_companies(rows)
                db.session.commit()
            except ProgrammingError as exc2:  # pragma: no cover - defensive logging
                current_app.logger.exception(
                    "Company upload failed again after schema upgrade", exc_info=exc2
                )
                db.session.rollback()
                flash(
                    "Upload failed because the company table is still out of date.",
                    "error",
                )
                return redirect(url_for("main.upload_companies"))

        flash(
            f"Upload complete. Added {added} companies, skipped {skipped}.",
            "success" if added else "info",
        )
        return redirect(url_for("main.index"))

    return render_template("upload.html")
