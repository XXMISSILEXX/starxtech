# Definition of Done

Start Phase 9 only after decisions in 20 are signed, migration current/head are rechecked, DB backup/rehearsal owner is assigned, and V2 API contract in 09 is retained. Each sub-phase is done only with: clean targeted migration rehearsal and rollback plan; model/service/route/RBAC tests; project isolation; full V2/storage regression; CSRF/private access review; query/performance evidence; Chrome + iPhone Safari manual evidence where upload UI changes; documentation and route/bookmark updates.

Release gate: no unexplained full-test failure, no schema-head mismatch, no source/test/config mutation outside planned diff, no secret in docs, security audit reviewed, production backup/restore rehearsal accepted, and final `git diff --check` clean. Current audit itself is not a release and does not claim browser manual testing.
