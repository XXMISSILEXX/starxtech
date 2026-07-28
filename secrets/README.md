# Docker Compose secrets

Không tạo secret thật trong repository. Trên host production, tạo các file
non-empty tại `/srv/starx-report/secrets/`:

- `app_secret_key`: Flask `SECRET_KEY` ngẫu nhiên, dài tối thiểu 32 ký tự.
- `database_url`: PostgreSQL SQLAlchemy URL.
- `storage_access_key_id`: S3-compatible access key có quyền tối thiểu cho một
  bucket/prefix riêng của StarX.
- `storage_secret_access_key`: secret S3-compatible tương ứng.
- `redis_password`: mật khẩu Redis ngẫu nhiên, riêng cho deployment này.

Production startup không tự seed admin. Tạo tài khoản bootstrap qua quy trình
release có kiểm soát sau migration, không lưu mật khẩu bootstrap ở Compose.

`database_url` nên dùng Unix socket; chỉ thay các placeholder trên host, không
đưa password vào tài liệu hay commit:

```text
postgresql+psycopg://starx_report:<PASSWORD>@host.docker.internal:5432/starx_report_prod
```

Khuyến nghị quyền host:

```bash
sudo chown -R root:root /srv/starx-report/secrets
sudo chmod 700 /srv/starx-report/secrets
sudo chmod 600 /srv/starx-report/secrets/*
```

Docker Compose mount secrets read-only vào `/run/secrets`. Kiểm tra quyền đọc
file của Docker/daemon trước; không nới quyền thành world-writable và không in
secret để chẩn đoán.
