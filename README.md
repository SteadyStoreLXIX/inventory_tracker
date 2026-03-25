# IT MSP Inventory Tracker

A lightweight inventory management web app for MSP teams that need to track stock levels at the main office, in storage, and across client-specific requirements.

## Features
- Authentication system with session-based login/logout.
- Full inventory CRUD operations (create, read, update, delete).
- Track quantities at the **main office** and in **storage**.
- Record exact storage location (room/shelf) for each item.
- Link inventory items to purchase vendors and vendor websites.
- Track client/project requirement requests and lifecycle statuses.
- Low-stock alerts based on reorder thresholds.
- Shared database support: point all app instances to the same DB via `DATABASE_URL`.

## Screenshots
### Login
![Login screen](docs/screenshots/login-screen.svg)

### Dashboard
![Dashboard screen](docs/screenshots/dashboard-screen.svg)

## Tech stack
- Python + Flask
- Flask-SQLAlchemy (SQLite by default, but supports Postgres/MySQL through SQLAlchemy URLs)

## Quick start
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Set admin seed credentials:
   ```bash
   export DEFAULT_ADMIN_USER='admin'
   export DEFAULT_ADMIN_PASSWORD='changeme'
   ```
4. Start the app:
   ```bash
   python app.py
   ```
5. Open `http://localhost:5000` and login.

## Shared database deployment
By default, the app uses a local SQLite file: `sqlite:///inventory.db`.

To share one central database between multiple computers, set `DATABASE_URL` before starting the app.

Example for Postgres:
```bash
export DATABASE_URL='postgresql+psycopg://user:password@db-server:5432/inventory'
python app.py
```

Each computer can access the same live data as long as they all point to the same database server.
