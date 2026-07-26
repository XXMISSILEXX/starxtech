# Step 9.0 baseline gate output

| Command | Result |
| --- | --- |
| `python -m compileall -q app tests migrations` | PASS (exit 0) |
| `npm test` | PASS: 2 tests, 2 passed, 0 failed, 0 skipped/todo |
| `PYTHONWARNINGS=error pytest -q -ra` | PASS: 268 passed in 181.73s |
| `pip check` | PASS: No broken requirements found. |
| `flask db current` | PASS: `20260725_0026 (head)` |
| `flask db heads` | PASS: `20260725_0026 (head)` |
| `flask security-audit` | PASS: all 30 checks passed, including RBAC schema/users, migration state, password hash and active SUPER_ADMIN. |
| `git diff --check` | PASS before Phase9 docs; re-run before commit. |

Security audit used the documented local runtime environment. No secret values appear in this evidence.
