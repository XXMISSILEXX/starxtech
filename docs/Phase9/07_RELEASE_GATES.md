# Release gates

Every Phase 9 step requires targeted tests, full suite, runtime/security checks, migration current=head and scoped diff review before commit.

Step 9.0 command evidence is saved under `evidence/`: compileall, npm test, full pytest with warnings as errors, pip check, Flask migration current/heads, security audit, and git diff check.

Migration steps additionally need backup/rehearsal, safe backfill validation and rollback plan. A release needs no unexplained test failure, no schema mismatch, no secret, security review, V2/storage regression, and acceptance of backup/restore rehearsal.
