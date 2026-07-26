# Baseline and methodology

**VERIFIED.** Commands and outputs are retained in `evidence/`: Git baseline, Python/node/npm/pip versions, `flask routes`, migration current/heads, source/test inventories, DB schema/profile, permission registry/database, and automated checks. Exact runtime was Python 3.10.12 despite repository instruction/README saying Python 3.12; this is a compatibility risk, not a source change.

`git branch --show-current`: `rewrite/daily-report-create-v2`; HEAD `b45281086d72e950ef62a41dc21024e904198296`. Baseline `git status --short` became `?? docs/Pre_Phase9_Audit/` when audit output was created. `git diff --check` was clean before audit. Migration current and head both verified as `20260725_0026` using the supplied local read-only application environment.

Source of truth order used: source, migration, tests, PostgreSQL schema/data, route map/permission tables, then old docs. Read scope included 101 Python application files plus all 26 migrations and 35 test modules; focused full reads cover the files named in current-state documents. Runtime DB queries used SQLAlchemy inspection/SELECT only. PostgreSQL/Redis/MinIO/Celery runtime health is recorded as UNKNOWN unless a command result appears in evidence; no services were started or stopped.

Limit: browser/iPhone manual tests were not performed. No claim of manual validation is made.

Automated baseline: compileall, HEIC build, Node tests and all requested Node syntax checks passed. The full `PYTHONWARNINGS=error pytest -q` run emitted progress through 26% but the execution environment ended it before a final summary/exit result; it is **NOT COMPLETED**, not PASS. `pip check` passed. `flask security-audit` failed only its `database-checks` probe with `OperationalError` under the default command environment; its other listed checks passed. Full output is in `evidence/automated_test_results.txt`.
