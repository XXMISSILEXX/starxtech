# Step 9.2 Customer migration and gate

## Local PostgreSQL migration rehearsal

```text
flask db upgrade
20260725_0026 -> aa468094da4f, add customers and project grouping
flask db current / flask db heads
aa468094da4f (head)
```

Read-only validation after upgrade:

```text
customers=1
unclassified=1
projects_without_customer=0
project_customer_ids=(1,),(1,)
```

## Gates

| Command | Result |
| --- | --- |
| Customer + project targeted suite | PASS: 23 passed in 15.85s |
| `PYTHONWARNINGS=error pytest -q -ra` | PASS: 279 passed in 185.79s |
| `python -m compileall -q app tests migrations` | PASS |
| `npm test` | PASS: 2 passed, 0 failed |
| `pip check` | PASS: No broken requirements found. |
| `flask security-audit` | PASS: all 30 checks passed. |
| `git diff --check` | PASS |

The migration was manually narrowed after Alembic autogenerate exposed unrelated existing schema drift. No Partner/media/RBAC drift was included.
