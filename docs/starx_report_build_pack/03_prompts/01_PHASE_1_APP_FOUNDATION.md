# PROMPT 01 — App Foundation + Database

Copy prompt này sau khi đã đưa MASTER CONTEXT.

---

Hãy tạo foundation cho Flask app **StarX Project Daily Report System**.

Yêu cầu:

1. Tạo cấu trúc project:

```text
starx-report/
  app/
    __init__.py
    config.py
    extensions.py
    models/
    auth/
    dashboard/
    users/
    projects/
    reports/
    issues/
    attachments/
    templates/
    static/
  migrations/
  tests/
  storage/uploads/
  .env.example
  requirements.txt
  run.py
  wsgi.py
  README.md
```

2. Cài extensions:

- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- python-dotenv
- psycopg2-binary hoặc psycopg[binary]
- Pillow
- gunicorn
- pytest

3. Config qua `.env`:

- SECRET_KEY
- DATABASE_URL
- UPLOAD_ROOT
- MAX_UPLOAD_MB
- MAX_IMAGES_PER_SECTION
- APP_ENV

4. Tạo app factory `create_app()`.

5. Register blueprint rỗng ban đầu cho:

- auth
- dashboard
- users
- projects
- reports
- issues
- attachments

6. Tạo base template Bootstrap 5:

- sidebar/menu đơn giản
- header user
- flash messages
- block content

7. Tạo trang `/health` trả JSON `{status: "ok"}`.

8. Tạo README hướng dẫn:

- tạo venv
- cài requirements
- tạo database PostgreSQL
- chạy migration
- chạy app local

Sau khi code xong, cung cấp command đầy đủ để chạy local trên Ubuntu.
