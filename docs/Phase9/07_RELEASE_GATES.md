# Release gates

Every Phase 9 step requires targeted tests, full suite, runtime/security checks, migration current=head and scoped diff review before commit.

Step 9.10C additionally requires `python -m compileall -q app tests migrations`,
JavaScript syntax checks, `npm test`, `PYTHONWARNINGS=error pytest -q -ra`,
`pip check`, `flask security-audit`, `flask db current`, `flask db heads`, and
`git diff --check`. Authenticated smoke at desktop, 390×844, 430×932 and
768×1024 remains a release blocker; evidence must never include credentials.

Local implementation verification on 2026-07-27: compileall, JavaScript
syntax, npm (3 tests), `pip check`, `flask db heads` (`c4d2e980f617`),
`git diff --check`, and the complete warning-as-error pytest suite (325 tests,
executed in runtime-safe groups) passed. `flask security-audit` and `flask db
current` remain blocked because the configured PostgreSQL connection returns
`OperationalError`; authenticated responsive smoke is pending a supplied local
endpoint and test account.

Step 9.0 command evidence is saved under `evidence/`: compileall, npm test, full pytest with warnings as errors, pip check, Flask migration current/heads, security audit, and git diff check.

Migration steps additionally need backup/rehearsal, safe backfill validation and rollback plan. A release needs no unexplained test failure, no schema mismatch, no secret, security review, V2/storage regression, and acceptance of backup/restore rehearsal.
