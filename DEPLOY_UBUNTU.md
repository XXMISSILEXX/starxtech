# Deploy Ubuntu Production

This guide deploys StarX Project Daily Report System to `/opt/starx-report` with PostgreSQL, Gunicorn, Nginx, HTTPS, and daily backups.

## 1. Install Ubuntu Packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib libpq-dev nginx certbot python3-certbot-nginx build-essential
```

## 2. Create Linux User

```bash
sudo adduser --system --group --home /opt/starx-report starxreport
sudo mkdir -p /opt/starx-report
sudo chown -R starxreport:starxreport /opt/starx-report
```

Clone or copy the source into `/opt/starx-report`.

## 3. Create PostgreSQL DB/User

```bash
sudo -u postgres psql
```

```sql
CREATE USER starx_report_prod WITH PASSWORD 'CHANGE_THIS_STRONG_PASSWORD';
CREATE DATABASE starx_report_prod OWNER starx_report_prod;
GRANT ALL PRIVILEGES ON DATABASE starx_report_prod TO starx_report_prod;
\q
```

## 4. Create Virtualenv And Install Requirements

```bash
cd /opt/starx-report
sudo -u starxreport python3 -m venv .venv
sudo -u starxreport .venv/bin/pip install --upgrade pip
sudo -u starxreport .venv/bin/pip install -r requirements.txt
```

## 5. Create Production `.env`

```bash
sudo -u starxreport cp /opt/starx-report/.env.example /opt/starx-report/.env
sudo -u starxreport nano /opt/starx-report/.env
```

Use production values:

```env
APP_ENV=production
FLASK_DEBUG=false
FLASK_APP=run.py
SECRET_KEY=GENERATE_A_LONG_RANDOM_SECRET
DATABASE_URL=postgresql+psycopg://starx_report_prod:CHANGE_THIS_STRONG_PASSWORD@127.0.0.1:5432/starx_report_prod
UPLOAD_ROOT=/opt/starx-report/storage/uploads
MAX_UPLOAD_MB=10
MAX_IMAGES_PER_SECTION=3
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

Create uploads folder:

```bash
sudo -u starxreport mkdir -p /opt/starx-report/storage/uploads
```

## 6. Run Migration And Seed Admin

```bash
cd /opt/starx-report
sudo -u starxreport bash -lc 'source .venv/bin/activate && flask db upgrade'
sudo -u starxreport bash -lc 'source .venv/bin/activate && flask seed-admin --username admin --password "CHANGE_ME_NOW" --email admin@example.com --full-name "System Admin"'
```

Log in once and change the admin password immediately.

## 7. Gunicorn Systemd Service

```bash
sudo nano /etc/systemd/system/starx-report.service
```

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

```bash
sudo systemctl daemon-reload
sudo systemctl enable starx-report
sudo systemctl start starx-report
sudo systemctl status starx-report
```

## 8. Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/starx-report
```

```nginx
server {
    listen 80;
    server_name report.example.com;

    client_max_body_size 20M;

    location /static/ {
        alias /opt/starx-report/app/static/;
        expires 7d;
    }

    # Do not expose /storage/uploads directly.
    # Attachments must go through /attachments/<id> for permission checks.

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/starx-report /etc/nginx/sites-enabled/starx-report
sudo nginx -t
sudo systemctl reload nginx
```

## 9. HTTPS With Certbot

```bash
sudo certbot --nginx -d report.example.com
```

## 10. Backup Cron

```bash
sudo mkdir -p /opt/backups/starx-report
sudo chown -R starxreport:starxreport /opt/backups/starx-report
```

Install cron as the `starxreport` user:

```bash
sudo crontab -u starxreport -e
```

```cron
0 2 * * * /opt/starx-report/scripts/backup_db.sh >> /var/log/starx-report-backup.log 2>&1
15 2 * * * /opt/starx-report/scripts/backup_uploads.sh >> /var/log/starx-report-backup.log 2>&1
```

Manual backup/restore:

```bash
sudo -u starxreport /opt/starx-report/scripts/backup_db.sh
sudo -u starxreport /opt/starx-report/scripts/backup_uploads.sh
sudo -u starxreport /opt/starx-report/scripts/restore_db.sh /opt/backups/starx-report/db/starx_report_db_YYYYmmdd_HHMMSS.sql.gz
```

## 11. Update Code

```bash
cd /opt/starx-report
sudo -u starxreport git pull
sudo -u starxreport bash -lc 'source .venv/bin/activate && pip install -r requirements.txt'
sudo -u starxreport bash -lc 'source .venv/bin/activate && flask db upgrade'
sudo systemctl restart starx-report
sudo systemctl status starx-report
```

## 12. Logs

```bash
journalctl -u starx-report -f
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
sudo tail -f /var/log/starx-report-backup.log
```

## 13. Production Checks

- `APP_ENV=production`
- `FLASK_DEBUG=false`
- strong `SECRET_KEY`
- `SESSION_COOKIE_SECURE=true`
- HTTPS enabled
- uploads folder is not public in Nginx
- `/attachments/<id>` checks permissions
- backup scripts run successfully
