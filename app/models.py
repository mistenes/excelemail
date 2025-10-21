from datetime import datetime

from . import db


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)

    shipments_origin = db.relationship(
        "Shipment", back_populates="origin", foreign_keys="Shipment.origin_id"
    )
    shipments_destination = db.relationship(
        "Shipment",
        back_populates="destination",
        foreign_keys="Shipment.destination_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - repr for debugging
        return f"<Company {self.name}>"


class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    origin_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    po_number = db.Column(db.String(120), nullable=False)
    sap_number = db.Column(db.String(120), nullable=False)
    order_number = db.Column(db.String(120), nullable=False)
    order_date = db.Column(db.Date, nullable=False)
    price = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    time_slot = db.Column(db.String(120), nullable=False)

    origin = db.relationship(
        "Company", foreign_keys=[origin_id], back_populates="shipments_origin"
    )
    destination = db.relationship(
        "Company", foreign_keys=[destination_id], back_populates="shipments_destination"
    )

    def __repr__(self) -> str:  # pragma: no cover - repr for debugging
        return f"<Shipment {self.id}>"
