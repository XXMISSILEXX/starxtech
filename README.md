# StarX Project Daily Report System

Internal Flask app for project daily progress reports.

## Stack

- Python 3.12
- Flask full-stack with Jinja templates
- Bootstrap 5 and Chart.js
- PostgreSQL
- SQLAlchemy ORM
- Flask-Migrate / Alembic
- Flask-Login
- Pillow

## Local Setup On Ubuntu

Install PostgreSQL and Python tooling if needed:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql postgresql-contrib
```

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create local environment config:

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
SECRET_KEY=change-me
DATABASE_URL=postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report
UPLOAD_ROOT=storage/uploads
MAX_UPLOAD_MB=10
MAX_IMAGES_PER_SECTION=3
APP_ENV=local
```

Create a PostgreSQL database and user:

```bash
sudo -u postgres psql
```

```sql
CREATE USER starx WITH PASSWORD 'starx';
CREATE DATABASE starx_daily_report OWNER starx;
\q
```

Initialize and run migrations:

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

This repository includes an initial migration. If `migrations/` already exists, run only:

```bash
flask db upgrade
```

Seed the first super admin:

```bash
flask seed-admin --username admin --password 'Admin@123456' --email admin@example.com --full-name 'System Admin'
```

Run the app locally:

```bash
flask run
```

Health check:

```bash
curl http://127.0.0.1:5000/health
```

Quick checks:

```bash
flask --app run.py routes
flask shell
```

```python
from app.models import User, Project, DailyReport
User.query.count()
```
