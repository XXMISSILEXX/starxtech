# Test và gate commands

## Fast source gate

```bash
python -m compileall -q app tests migrations
npm test
pip check
git diff --check
```

## Daily Report immutable regression

```bash
PYTHONWARNINGS=error pytest -q \
  tests/test_daily_report_create_v2.py \
  tests/test_report_create_entry.py \
  tests/test_reports_attachments.py \
  tests/test_security_hardening.py
```

## Full suite

```bash
PYTHONWARNINGS=error pytest -q -ra
```

## Runtime

```bash
flask db current
flask db heads
flask security-audit
redis-cli -n 0 ping
curl -fsS http://192.168.1.159:9000/minio/health/live >/dev/null
python -m celery -A app.celery_worker:celery_app inspect ping --timeout=5
```

## JavaScript syntax

Use only files that exist after inspecting source:

```bash
find app/static/js -type f -name '*.js' -print0 \
  | xargs -0 -n1 node --check
```

## Migration step gate

```bash
flask db current
flask db heads
# upgrade local only after backup/rehearsal decision
flask db upgrade
flask db current
```

Full suite is required before every commit, unless the user explicitly authorizes a documented exception. No skip/xfail workaround.
