# Production Deploy Ubuntu — Flask + PostgreSQL + Gunicorn + Nginx

## 1. Cài packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib libpq-dev nginx supervisor certbot python3-certbot-nginx build-essential
```

## 2. Tạo Linux user chạy app

```bash
sudo adduser --system --group --home /opt/starx-report starxreport
```

## 3. Chuẩn bị source

```bash
sudo mkdir -p /opt/starx-report
sudo chown -R starxreport:starxreport /opt/starx-report
```

Copy source vào `/opt/starx-report`.

## 4. Tạo database production

```bash
sudo -u postgres psql
```

```sql
CREATE USER starx_report_prod WITH PASSWORD 'USE_A_STRONG_PASSWORD';
CREATE DATABASE starx_report_prod OWNER starx_report_prod;
GRANT ALL PRIVILEGES ON DATABASE starx_report_prod TO starx_report_prod;
\q
```

## 5. Tạo venv và cài requirements

```bash
cd /opt/starx-report
sudo -u starxreport python3 -m venv .venv
sudo -u starxreport .venv/bin/pip install --upgrade pip
sudo -u starxreport .venv/bin/pip install -r requirements.txt
```

## 6. Tạo `.env` production

```bash
sudo -u starxreport nano /opt/starx-report/.env
```

Ví dụ:

```env
APP_ENV=production
FLASK_DEBUG=false
SECRET_KEY=GENERATE_A_LONG_RANDOM_SECRET
DATABASE_URL=postgresql://starx_report_prod:USE_A_STRONG_PASSWORD@localhost:5432/starx_report_prod
UPLOAD_ROOT=/opt/starx-report/storage/uploads
MAX_UPLOAD_MB=10
MAX_IMAGES_PER_SECTION=3
MAX_IMAGE_WIDTH=1920
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

Tạo folder upload:

```bash
sudo -u starxreport mkdir -p /opt/starx-report/storage/uploads
```

## 7. Migration và seed admin

```bash
cd /opt/starx-report
sudo -u starxreport bash -lc 'source .venv/bin/activate && export FLASK_APP=run.py && flask db upgrade'

sudo -u starxreport bash -lc 'source .venv/bin/activate && export FLASK_APP=run.py && flask seed-admin --username admin --password "Admin@123456" --email admin@example.com --full-name "System Admin"'
```

Sau khi login lần đầu, đổi mật khẩu admin ngay.

## 8. Tạo systemd service

```bash
sudo nano /etc/systemd/system/starx-report.service
```

Nội dung:

```ini
[Unit]
Description=StarX Project Daily Report Flask App
After=network.target postgresql.service

[Service]
User=starxreport
Group=starxreport
WorkingDirectory=/opt/starx-report
Environment="PATH=/opt/starx-report/.venv/bin"
Environment="FLASK_APP=run.py"
ExecStart=/opt/starx-report/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable starx-report
sudo systemctl start starx-report
sudo systemctl status starx-report
```

Logs:

```bash
journalctl -u starx-report -f
```

## 9. Nginx reverse proxy

```bash
sudo nano /etc/nginx/sites-available/starx-report
```

Nội dung:

```nginx
server {
    listen 80;
    server_name report.yourdomain.com;

    client_max_body_size 20M;

    location /static/ {
        alias /opt/starx-report/app/static/;
        expires 7d;
    }

    # Không serve /storage/uploads public trực tiếp trong MVP.
    # Ảnh phải đi qua route /attachments/<id> để check quyền.

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/starx-report /etc/nginx/sites-enabled/starx-report
sudo nginx -t
sudo systemctl reload nginx
```

## 10. HTTPS Certbot

```bash
sudo certbot --nginx -d report.yourdomain.com
```

## 11. Backup cron

Tạo folder:

```bash
sudo mkdir -p /opt/backups/starx-report
sudo chown -R starxreport:starxreport /opt/backups/starx-report
```

Cron ví dụ:

```bash
sudo crontab -e
```

```cron
0 2 * * * /opt/starx-report/scripts/backup_db.sh >> /var/log/starx-report-backup.log 2>&1
15 2 * * * /opt/starx-report/scripts/backup_uploads.sh >> /var/log/starx-report-backup.log 2>&1
```

## 12. Update code production

```bash
cd /opt/starx-report
sudo -u starxreport git pull
sudo -u starxreport bash -lc 'source .venv/bin/activate && pip install -r requirements.txt'
sudo -u starxreport bash -lc 'source .venv/bin/activate && export FLASK_APP=run.py && flask db upgrade'
sudo systemctl restart starx-report
sudo systemctl status starx-report
```

## 13. Production checklist

- Debug off.
- HTTPS on.
- SECRET_KEY mạnh.
- Admin đổi mật khẩu mặc định.
- Upload folder không public.
- Backup chạy được.
- Viewer admin không write được.
- Reporter không thấy project chưa gán.
- Attachment check quyền.
