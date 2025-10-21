import os
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.exc import NoSuchTableError


db = SQLAlchemy()


def ensure_company_address_columns(app):
    inspector = inspect(db.engine)

    try:
        raw_columns = inspector.get_columns("company")
    except NoSuchTableError:
        return False

    columns = {column["name"] for column in raw_columns}
    column_info = {column["name"]: column for column in raw_columns}
    column_definitions = {
        "street": "street VARCHAR(120)",
        "street_number": "street_number VARCHAR(50)",
        "postal_code": "postal_code VARCHAR(20)",
        "city": "city VARCHAR(120)",
    }

    required_columns = set(column_definitions.keys())

    added_columns = set()
    dialect = db.engine.dialect.name

    with db.engine.begin() as connection:
        for column, ddl in column_definitions.items():
            if column in columns:
                continue

            statement = f"ALTER TABLE company ADD COLUMN {ddl}"
            if dialect == "postgresql":
                statement = f"ALTER TABLE company ADD COLUMN IF NOT EXISTS {ddl}"

            try:
                connection.execute(text(statement))
                added_columns.add(column)
            except Exception:
                app.logger.exception(
                    "Failed to add %%s column to company table", column
                )

        address_info = column_info.get("address")
        if address_info:
            if not address_info.get("nullable", True) and dialect == "postgresql":
                try:
                    connection.execute(
                        text("ALTER TABLE company ALTER COLUMN address DROP NOT NULL")
                    )
                    app.logger.info(
                        "Dropped NOT NULL constraint from legacy company.address column"
                    )
                except Exception:  # pragma: no cover - deployment safeguard
                    app.logger.exception(
                        "Failed to relax NOT NULL constraint on company.address"
                    )

            if dialect == "postgresql":
                try:
                    connection.execute(
                        text("ALTER TABLE company ALTER COLUMN address SET DEFAULT ''")
                    )
                except Exception:  # pragma: no cover - deployment safeguard
                    app.logger.exception(
                        "Failed to set default for company.address"
                    )

            connection.execute(
                text("UPDATE company SET address = '' WHERE address IS NULL")
            )

    if added_columns:
        columns.update(added_columns)
        app.logger.info(
            "Added missing company address columns: %s",
            ", ".join(sorted(added_columns)),
        )

    existing_columns = columns.intersection(required_columns)

    if not existing_columns:
        return False

    with db.engine.begin() as connection:
        for column in existing_columns:
            connection.execute(
                text(f"UPDATE company SET {column} = '' WHERE {column} IS NULL")
            )

        if "address" in columns and "street" in existing_columns:
            connection.execute(
                text(
                    "UPDATE company "
                    "SET street = address "
                    "WHERE (street = '' OR street IS NULL) AND address IS NOT NULL"
                )
            )
            app.logger.info(
                "Copied legacy address values into the new street column where needed"
            )

    return required_columns.issubset(columns)


def ensure_company_schema(app):
    """Ensure the company table has the structured address columns."""

    try:
        ensured = ensure_company_address_columns(app)
    except Exception:  # pragma: no cover - defensive logging for deployment issues
        app.logger.exception("Company schema upgrade failed")
        ensured = False

    app.config["COMPANY_SCHEMA_CHECKED"] = ensured
    return ensured


def create_app(test_config=None):
    app = Flask(__name__)

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url and database_url.startswith("postgresql://") and "+psycopg://" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not database_url:
        database_url = f"sqlite:///{instance_path / 'excelemail.db'}"

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from . import models  # noqa: F401
    from .routes import bp as main_bp

    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        ensure_company_schema(app)

    @app.before_request
    def ensure_company_schema_once():
        if app.config.get("COMPANY_SCHEMA_CHECKED"):
            return

        ensure_company_schema(app)

    return app
