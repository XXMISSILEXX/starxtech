# Environment runbook

```bash
cd ~/Documents/Construction_Management
source .venv/bin/activate

set -a
source .env.s3-local
set +a

export FLASK_APP=wsgi.py
export APP_ENV=local
export FLASK_DEBUG=true
export SESSION_COOKIE_SECURE=false
export DATABASE_URL="$(sudo cat /srv/construction_relation_management/secrets/database_url)"
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0
export CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
export RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/2
```

Baseline:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
flask db current
flask db heads
flask routes > /tmp/phase9-routes.txt
```

Không in secret ra terminal log/tài liệu.

Worker:

```bash
bash scripts/start-media-worker.sh
```

App local theo command hiện tại của repository; không tự đổi port hoặc process manager nếu không cần.
