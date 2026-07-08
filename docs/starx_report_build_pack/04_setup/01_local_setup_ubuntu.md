# Local Setup Ubuntu — StarX Project Daily Report

Tài liệu này giả định bạn dùng Ubuntu và PostgreSQL local.

## 1. Cài package hệ thống

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib libpq-dev build-essential
```

Kiểm tra:

```bash
python3 --version
psql --version
```

## 2. Tạo database PostgreSQL

```bash
sudo -u postgres psql
```

Trong psql:

```sql
CREATE USER starx_report WITH PASSWORD 'change_this_password';
CREATE DATABASE starx_report OWNER starx_report;
GRANT ALL PRIVILEGES ON DATABASE starx_report TO starx_report;
\q
```

## 3. Clone hoặc tạo source

Ví dụ:

```bash
cd ~/Documents
mkdir -p starx-report
cd starx-report
```

Sau khi coding agent tạo source, cấu trúc nên có:

```text
app/
migrations/
tests/
storage/uploads/
requirements.txt
run.py
wsgi.py
.env.example
```

## 4. Tạo virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Tạo `.env`

```bash
cp .env.example .env
nano .env
```

Ví dụ `.env` local:

```env
APP_ENV=development
FLASK_DEBUG=true
SECRET_KEY=local_dev_secret_change_me
DATABASE_URL=postgresql://starx_report:change_this_password@localhost:5432/starx_report
UPLOAD_ROOT=./storage/uploads
MAX_UPLOAD_MB=10
MAX_IMAGES_PER_SECTION=3
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

## 6. Set biến môi trường Flask

```bash
export FLASK_APP=run.py
export FLASK_ENV=development
```

Nếu dùng python-dotenv thì có thể không cần export nhiều, tùy code.

## 7. Chạy migration

Lần đầu:

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

Các lần sau khi model thay đổi:

```bash
flask db migrate -m "describe change"
flask db upgrade
```

## 8. Seed admin đầu tiên

```bash
flask seed-admin \
  --username admin \
  --password 'Admin@123456' \
  --email admin@example.com \
  --full-name 'System Admin'
```

## 9. Chạy app local

```bash
flask run --host=127.0.0.1 --port=5000
```

Mở:

```text
http://127.0.0.1:5000
```

Login:

```text
username: admin
password: Admin@123456
```

## 10. Quy trình test manual nhanh

1. Login admin.
2. Tạo user reporter.
3. Tạo user viewer admin.
4. Tạo project.
5. Tạo category cho project.
6. Gán reporter vào project.
7. Login reporter.
8. Tạo báo cáo ngày.
9. Upload 1-3 ảnh cho một đầu mục.
10. Xem dashboard project.
11. Login viewer admin.
12. Kiểm tra viewer xem được nhưng không có nút sửa/tạo.

## 11. Chạy test

```bash
pytest -q
```

## 12. Lỗi thường gặp

### Không connect được PostgreSQL

Kiểm tra DATABASE_URL, user/password/database.

```bash
psql postgresql://starx_report:change_this_password@localhost:5432/starx_report
```

### Flask không thấy app

```bash
export FLASK_APP=run.py
```

### Upload không lưu được ảnh

Kiểm tra folder:

```bash
mkdir -p storage/uploads
chmod -R 755 storage
```

### Migration bị lệch

Trong dev có thể reset DB nếu chưa có dữ liệu quan trọng:

```bash
sudo -u postgres dropdb starx_report
sudo -u postgres createdb starx_report -O starx_report
flask db upgrade
```
