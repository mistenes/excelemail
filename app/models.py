from datetime import datetime

from . import db


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    street = db.Column(db.String(120), nullable=False)
    street_number = db.Column(db.String(50), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(120), nullable=False)

    shipments_origin = db.relationship(
        "Shipment", back_populates="origin", foreign_keys="Shipment.origin_id"
    )
    shipments_destination = db.relationship(
        "Shipment",
        back_populates="destination",
        foreign_keys="Shipment.destination_id",
    )

    @property
    def formatted_address(self) -> str:
        """Return a human-readable address string."""

        street_part = " ".join(
            part for part in (self.street, self.street_number) if part
        ).strip()
        city_part = " ".join(
            part for part in (self.postal_code, self.city) if part
        ).strip()
        return ", ".join(part for part in (street_part, city_part) if part)

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
