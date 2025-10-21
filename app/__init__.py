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
        columns = {column["name"] for column in inspector.get_columns("company")}
    except NoSuchTableError:
        return

    column_definitions = {
        "street": "street VARCHAR(120)",
        "street_number": "street_number VARCHAR(30)",
        "postal_code": "postal_code VARCHAR(20)",
        "city": "city VARCHAR(120)",
    }

    missing_columns = [
        (column, ddl)
        for column, ddl in column_definitions.items()
        if column not in columns
    ]

    if missing_columns:
        with db.engine.begin() as connection:
            for column, ddl in missing_columns:
                connection.execute(text(f"ALTER TABLE company ADD COLUMN {ddl}"))
        added = ", ".join(column for column, _ in missing_columns)
        app.logger.info("Added missing company address columns: %s", added)

    with db.engine.begin() as connection:
        for column in column_definitions:
            connection.execute(
                text(f"UPDATE company SET {column} = '' WHERE {column} IS NULL")
            )

        if "address" in columns:
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
        ensure_company_address_columns(app)

    return app
