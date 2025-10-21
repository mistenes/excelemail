import csv
from datetime import datetime
from io import TextIOWrapper

from flask import Blueprint, flash, redirect, render_template, request, url_for

from . import db
from .models import Company, Shipment


bp = Blueprint("main", __name__)


@bp.route("/")
def index():
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
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Please choose a CSV file to upload.", "error")
            return redirect(url_for("main.upload_companies"))

        added = 0
        skipped = 0

        file.stream.seek(0)
        csv_file = TextIOWrapper(file.stream, encoding="utf-8")
        reader = csv.DictReader(csv_file)
        for row in reader:
            name = row.get("name") or row.get("Name")
            address = row.get("address") or row.get("Address")
            if not name or not address:
                skipped += 1
                continue

            if Company.query.filter_by(name=name.strip()).first():
                skipped += 1
                continue

            company = Company(name=name.strip(), address=address.strip())
            db.session.add(company)
            added += 1

        db.session.commit()

        flash(
            f"Upload complete. Added {added} companies, skipped {skipped}.",
            "success" if added else "info",
        )
        return redirect(url_for("main.index"))

    return render_template("upload.html")
