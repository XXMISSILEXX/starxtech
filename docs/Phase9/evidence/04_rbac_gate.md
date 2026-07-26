# Step 9.1 RBAC gate

| Command | Result |
| --- | --- |
| Targeted RBAC suite | PASS: 25 passed in 17.07s |
| `PYTHONWARNINGS=error pytest -q -ra` | PASS: 274 passed in 182.38s |
| `python -m compileall -q app tests migrations` | PASS |
| `npm test` | PASS: 2 passed, 0 failed |
| `pip check` | PASS: No broken requirements found. |
| `flask db current` / `flask db heads` | PASS: `20260725_0026 (head)` |
| `flask security-audit` | PASS: all 30 checks passed. |
| `git diff --check` | PASS |

No migration was required. Tests use additive registry synchronization and do not reset DB defaults.
