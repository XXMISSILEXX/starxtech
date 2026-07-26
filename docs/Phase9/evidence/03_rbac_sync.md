# Step 9.1 permission sync

Reviewed CLI behavior: `--apply-defaults` inserts missing registry rows and missing grants for system roles only. It does not delete grants; deletion is restricted to `--reset-defaults`, which was not used.

```text
flask sync-permissions --apply-defaults
roles=0 permissions=24 grants=35 deprecated-orphan=0
```

Post-sync read-only inventory: `permissions=124`, `grants=231`, and legacy/custom roles remain `005,PARTNER,PROJECT_MANAGER,PROJECT_STAFF,REPORTER`.

The command was run only against the documented local database. No secret values, custom-role reset, or legacy-grant deletion occurred.
