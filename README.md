# Shipment Planner

A lightweight Flask application for managing shipments. Add companies manually and create shipments by selecting origins and destinations from the saved companies.

## Features

- Add company records manually with structured addresses (street, number, postal code, city).
- Create shipments with purchase order, SAP, order number, price, weight, and time slot details.
- Store data in a local SQLite database.
- View the ten most recent shipments.

## Requirements

- Python 3.10+
- pip

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the application

```bash
flask --app run run --debug
```

Open http://127.0.0.1:5000 in your browser.

For a production WSGI server (matching the Render deployment command below), use:

```bash
gunicorn run:app
```

### Initial setup

1. Navigate to the **Add Company** page.
2. Enter the company's name, street, street number, postal code, and city, then save it. Repeat for each company you need.
3. Use the **Create Shipment** form to add new shipments.

Uploaded companies are validated to avoid duplicates and rows missing required columns. Shipments require all fields to be filled, and the application ensures origin and destination companies are different.

## Deploying to Render

The repository includes a [`render.yaml`](render.yaml) blueprint that provisions a free-tier PostgreSQL database and a Python web
service. To deploy:

1. Push this repository to your own GitHub account.
2. Log in to [Render](https://render.com) and choose **New + → Blueprint**.
3. Provide the repository URL and keep the default region and instance type.
4. Render will install dependencies with `pip install -r requirements.txt` and start the service with `gunicorn run:app`.
5. Once live, add companies through the `/companies/upload` page (manual entry form), then begin creating shipments from the home page.

The application automatically picks up the `DATABASE_URL` and `SECRET_KEY` environment variables Render injects. Locally, it
falls back to a SQLite database inside the Flask instance folder and a development secret key.
