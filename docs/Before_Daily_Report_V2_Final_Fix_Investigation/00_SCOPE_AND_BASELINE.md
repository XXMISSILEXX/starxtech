# Scope and baseline

Investigation date: 2026-07-25. This directory records research only. No production controller, template, CSS, route, model, migration, dependency, or decoder was changed.

The sole code change is the failing characterization test in `tests_js/daily-report-create-v2.test.js`; it deliberately exposes the duplicate-date regression and does not change expectations of existing tests.

Commands run:

```text
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
python -m compileall -q app tests migrations
npm run build:heic-preview
npm test
PYTHONWARNINGS=error pytest -q tests/test_daily_report_create_v2.py tests/test_report_create_entry.py tests/test_reports_route_namespace.py
PYTHONWARNINGS=error pytest -q
pip check
```

Results: compileall succeeded; the targeted Python suite passed (18 passed); the full Python command completed with no reported failure; `pip check` had no output; `npm test` fails only on the newly added characterization test, as intended by the investigation. The existing two JS tests pass but do not cover save failure, HEIC, or status rendering.

`flask db current` could not connect to PostgreSQL (`psycopg.OperationalError: connection is bad`); migration head from the repository is `20260725_0026 (head)`. Database current revision is therefore unknown.
