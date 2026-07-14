# Docker Compose secrets

Không tạo secret thật trong repository. Trên host production, tạo các file
non-empty tại `/srv/construction_relation_management/secrets/`:

- `app_secret_key`: Flask `SECRET_KEY` ngẫu nhiên, dài tối thiểu 32 ký tự.
- `database_url`: PostgreSQL SQLAlchemy URL.
- `admin_password`: mật khẩu khởi tạo `SUPER_ADMIN` (ít nhất 12 ký tự, đủ 3
  nhóm ký tự theo policy của app).
- `cloudflare_tunnel_token`: token của remotely-managed Cloudflare Tunnel.

`database_url` nên dùng Unix socket; chỉ thay các placeholder trên host, không
đưa password vào tài liệu hay commit:

```text
postgresql+psycopg://ubuntu:<PASSWORD>@/construction_relation_management?host=/var/run/postgresql
```

Khuyến nghị quyền host:

```bash
sudo chown -R root:root /srv/construction_relation_management/secrets
sudo chmod 700 /srv/construction_relation_management/secrets
sudo chmod 600 /srv/construction_relation_management/secrets/*
```

Docker Compose mount secrets read-only vào `/run/secrets`. Nếu `cloudflared`
không đọc được token do host permission, kiểm tra quyền đọc file của Docker/daemon
trước; không nới quyền thành world-writable và không in token để chẩn đoán.
