# StarX Project Daily Report System

Internal Flask app for project daily progress reports and partner management.

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
RATELIMIT_STORAGE_URI=memory://
RATELIMIT_LOGIN_LIMIT='5 per minute'
RATELIMIT_EXPORT_LIMIT='10 per hour'
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
flask sync-permissions --apply-defaults
```

This repository includes an initial migration. If `migrations/` already exists, run only:

```bash
flask db upgrade
```

The partner management module is included in migration `20260708_0003_partner_module.py`.
After upgrading, users with access to both modules choose between:

- Báo cáo hàng ngày
- Quản lý đối tác

## Partner Management Demo Data

Create example companies, partner fields, partners, and relationships:

```bash
flask seed-partner-demo
```

Then visit:

```text
/modules
```

Choose:

```text
Quản lý đối tác
```

Usage guide: [PARTNER_MANAGEMENT_GUIDE.md](PARTNER_MANAGEMENT_GUIDE.md)

Seed the first super admin:

```bash
flask seed-admin --username admin --password 'Admin@123456' --email admin@example.com --full-name 'System Admin'
```

Mật khẩu admin phải có ít nhất 12 ký tự và chứa ít nhất 3 trong 4 nhóm: chữ hoa, chữ thường, số, ký tự đặc biệt. Lệnh seed tạo hoặc cập nhật chính tài khoản được chỉ định thành `SUPER_ADMIN` và không in mật khẩu.

## RBAC canonical

Sau migration, đồng bộ registry quyền có kiểm soát:

```bash
flask sync-permissions --apply-defaults
```

Lệnh mặc định chỉ tạo/cập nhật metadata vai trò và quyền. Dùng `--reset-defaults --confirm "RESET DEFAULTS"` khi chủ động muốn thay toàn bộ grant mặc định của các system role.

## Reset local và kiểm tra bảo mật

```bash
flask reset-local-dev --confirm "RESET DATABASE" --admin-password 'StrongPass123!'
```

Lệnh này reset database local, chạy migration, và tạo admin mặc định (`admin` / `admin@example.com` / `System Admin`). Thêm `--with-demo` để tạo dữ liệu mẫu Quản lý đối tác. Để reset riêng database, dùng `flask reset-database --confirm "RESET DATABASE"`; uploads được giữ mặc định, thêm `--delete-uploads` chỉ khi cần.

Trên production, reset bị từ chối nếu không có `--allow-production`. Luôn backup trước khi dùng override này.

```bash
flask security-audit
```

`memory://` là rate-limit storage mặc định cho local/internal. Redis là tuỳ chọn, nhưng nên dùng storage chia sẻ khi chạy nhiều worker production. Xem checklist chi tiết tại [SECURITY_AUDIT_CHECKLIST.md](SECURITY_AUDIT_CHECKLIST.md).

Run the app locally:

```bash
flask run
```

Health check:

```bash
curl http://127.0.0.1:5000/health
```

`/healthz` cũng trả `{"status":"ok"}` và được dùng bởi Docker healthcheck.

Quick checks:

```bash
flask --app run.py routes
flask shell
```

```python
from app.models import User, Project, DailyReport
User.query.count()
```

## Production Operations

- Ubuntu deployment guide: [DEPLOY_UBUNTU.md](DEPLOY_UBUNTU.md)
- Docker Compose + Cloudflared: [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md)
- Smoke test checklist: [PRODUCTION_SMOKE_TEST.md](PRODUCTION_SMOKE_TEST.md)
- Backup scripts:
  - `scripts/backup_db.sh`
  - `scripts/backup_uploads.sh`
  - `scripts/restore_db.sh`
