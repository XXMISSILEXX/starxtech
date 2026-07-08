# PROMPT 07 — Audit, Security, Backup, Deploy

---

Hãy hoàn thiện phần vận hành production cho Flask app.

## A. Audit log

Tạo helper:

```python
log_audit(action, entity_type, entity_id=None, old_values=None, new_values=None)
```

Ghi:

- actor_user_id
- action
- entity_type
- entity_id
- old_values_json
- new_values_json
- ip_address
- user_agent
- created_at

Đảm bảo các thao tác quan trọng đều gọi audit:

- user CRUD
- project CRUD
- assignment
- category CRUD
- report create/update/delete
- attachment upload/delete
- issue create/update/close/reopen

## B. Security hardening

- Đảm bảo production không bật debug.
- `.env.example` đầy đủ nhưng không có secret thật.
- Session cookie Secure/HttpOnly/SameSite.
- CSRF cho form.
- Validate file upload kỹ.
- Không expose upload folder public.
- Route attachment check quyền.
- Add max content length.

## C. Backup scripts

Tạo scripts:

```text
scripts/backup_db.sh
scripts/backup_uploads.sh
scripts/restore_db.sh
```

Yêu cầu:

- Backup PostgreSQL bằng `pg_dump`.
- Backup uploads bằng `tar.gz`.
- Folder backup mặc định `/opt/backups/starx-report`.
- Có timestamp trong file.
- Có hướng dẫn cron hằng ngày.

## D. Production deploy docs

Tạo tài liệu `DEPLOY_UBUNTU.md` gồm:

- Cài packages Ubuntu.
- Tạo user Linux `starxreport`.
- Clone/copy source vào `/opt/starx-report`.
- Tạo venv.
- Cài requirements.
- Tạo PostgreSQL DB/user.
- Tạo `.env`.
- Chạy migration.
- Seed admin.
- Gunicorn systemd service.
- Nginx reverse proxy.
- HTTPS với Certbot.
- Backup cron.
- Cách update code.
- Cách xem logs.

## E. Final smoke test checklist

Tạo checklist:

- login admin
- create user
- create project
- assign reporter
- create category
- login reporter
- create report
- upload images
- view dashboard
- login viewer
- confirm viewer cannot edit
- backup DB/uploads

Sau khi xong, liệt kê file đã tạo/sửa và command deploy chính.
