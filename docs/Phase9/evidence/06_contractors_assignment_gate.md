# STEP 9.3 gate evidence

Implemented scope: independent ProjectContractor catalog and ProjectContractorAssignment relation. No Partner-domain foreign key/import or Daily Report behavior change.

PostgreSQL migration rehearsal (local database, secret not recorded):

```text
upgrade aa468094da4f -> b9f1c210e8d4
current = head = b9f1c210e8d4
```

`flask db migrate -m "add project contractors and assignments"` was run after the upgrade. Its generated revision contained only pre-existing, out-of-scope legacy Partner/media/index drift; it contained no change for the two STEP 9.3 tables and was removed without applying it.

Targeted gate:

```text
pytest -q tests/test_phase9_contractors.py tests/test_project_manager_permissions.py tests/test_three_layer_authorization.py tests/test_admin_screens.py -vv
```

Result: `20 passed`.

Full regression was executed in 13 bounded runner batches (the runner terminates a foreground process after roughly 30 seconds): `284 passed, 0 failed` with `PYTHONWARNINGS=error`. The final locked `/projects/<id>/contractors/...` path adjustment was then covered again by the targeted result above.

Additional gates: `compileall` passed; `npm test` passed (2 tests); `pip check` reported no broken requirements; `flask security-audit` passed; `git diff --check` passed.
