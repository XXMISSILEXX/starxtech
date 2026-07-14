# Triển khai Docker Compose + Cloudflared

## Kiến trúc

```text
Internet (HTTPS) -> Cloudflare Tunnel -> cloudflared -> web:6655
                                                    -> PostgreSQL host qua Unix socket
```

Chỉ `cloudflared` và `web` nằm trong Docker network `appnet`. Service `web`
không publish port ra Internet; Cloudflare public hostname phải trỏ tới
`http://web:6655`, không phải `127.0.0.1`. Upload được app phục vụ qua endpoint
phân quyền `/attachments/<id>`, không public thư mục upload.

## 1. Chuẩn bị host

```bash
sudo install -d -m 700 /srv/construction_relation_management/secrets
sudo install -d -o 1000 -g 1000 -m 750 /srv/construction_relation_management/uploads
sudo install -d -o 1000 -g 1000 -m 750 /srv/construction_relation_management/tmp
```

Tạo bốn secret files theo [secrets/README.md](secrets/README.md). Không tạo
`.env.docker` cho secret và không commit bất kỳ file nào trong thư mục secrets.
Đặt public hostname trước khi chạy Compose (ví dụ minh họa, thay bằng domain thật):

```bash
export TRUSTED_HOSTS=report.example.internal
```

## 2. PostgreSQL ngoài Docker

Compose mount `/var/run/postgresql` read-only vào container. Dùng URL Unix
socket trong secret `database_url`, dạng:

```text
postgresql+psycopg://ubuntu:<PASSWORD>@/construction_relation_management?host=/var/run/postgresql
```

Tạo database và role theo chính sách của host; database phải do app role sở hữu
hoặc được cấp quyền đầy đủ. Ví dụ tên role `ubuntu` chỉ là minh họa, không copy
password vào shell history hay repository. PostgreSQL không cần và không nên
public ra Internet.

Troubleshooting:

- `connection refused`: kiểm tra socket mount, `unix_socket_directories`, role,
  database name và service PostgreSQL trên host.
- `permission denied for table`: sửa owner/grant của database/schema/table cho
  app role.
- `role/database does not exist`: tạo đúng role và database, sau đó cấp owner;
  entrypoint không tự tạo, drop hay reset database.

## 3. Build và vận hành app

```bash
docker compose config
docker compose build --no-cache
docker compose up -d web
docker compose ps
```

Mặc định `RUN_MIGRATIONS`, `RUN_SECURITY_AUDIT`, `SEED_ADMIN` đều là `false`.
Không bật `reset-database` trong production. Sau khi `web` healthy, chạy từng
thao tác có kiểm soát:

```bash
docker compose exec web flask db upgrade
docker compose exec web flask seed-admin --username admin --password "$(cat /srv/construction_relation_management/secrets/admin_password)" --email admin@example.com --full-name "System Admin"
docker compose exec web flask security-audit
```

Lệnh seed chỉ dùng một lần trong terminal tin cậy; không đưa password vào file
shell/script hoặc log. Audit chấp nhận `memory://` với `WARN` vì rate-limit là
per-worker và reset khi restart, nhưng sẽ fail với guard production, database,
migration hoặc thiếu `SUPER_ADMIN`.

## 4. Cloudflare Tunnel

Tạo remotely-managed tunnel trong Cloudflare Zero Trust, lưu token vào secret
`cloudflare_tunnel_token`, cấu hình public hostname origin là `http://web:6655`,
rồi chạy:

```bash
docker compose up -d cloudflared
docker compose logs --tail=100 cloudflared
```

Cloudflared chờ healthcheck của `web`. HTTPS kết thúc ở Cloudflare, nên
`SESSION_COOKIE_SECURE=true` là bắt buộc. Không test đăng nhập qua HTTP local
khi setting này đang bật; nếu cần debug local, tạm bật mapping `127.0.0.1:6655`
và dùng cấu hình local riêng với `SESSION_COOKIE_SECURE=false`—không commit thay
đổi đó vào production Compose.

## 5. Khắc phục sự cố

- `CSRF token missing`: kiểm tra form dùng `FlaskForm`/`hidden_tag()`, cookie
  trình duyệt không bị chặn và truy cập qua hostname HTTPS đúng.
- Login lặp lại trên HTTP local: đây là hành vi đúng với secure cookie; dùng
  HTTPS tunnel hoặc config local riêng như trên.
- Upload lỗi: xác nhận host uploads/tmp thuộc UID:GID `1000:1000` và có quyền
  ghi; không `chmod 777`.
- Token Cloudflared không đọc được: kiểm tra secret file và quyền Docker mount,
  không in token ra log.

## Backup

Backup PostgreSQL độc lập bằng quy trình database của host. Backup upload riêng:

```bash
sudo tar -C /srv/construction_relation_management -czf uploads-backup.tar.gz uploads
```

Có thể dùng `rsync` thay cho tar. Không đưa secret folder vào backup không mã hóa.
