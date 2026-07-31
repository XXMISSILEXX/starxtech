# Test and verification plan

| Requirement | Environment | Required assertion |
| --- | --- | --- |
| Sequential presign replay | SQLite + FakeStorage | one item/object/key; counter once; replay marker. |
| Metadata filename/size/MIME conflict | SQLite + FakeStorage | 409 `idempotency_conflict`, non-retryable, no rows/signing. |
| Concurrent presign | PostgreSQL, two independent connections/barrier | one item/object/key/counter; loser replay; no orphan. |
| Complete twice | SQLite + FakeStorage | one active object, one media file, one enqueue. |
| Concurrent complete | PostgreSQL + FakeStorage/controlled signer | one media/job; both compatible success, no 500. |
| Finalize twice | SQLite + FakeStorage | same persisted counts/status, no mutation. |
| Expired presign / no restart | SQLite + FakeStorage + browser | 410, no session/object/item replacement. |
| Browser lifecycle | Node/jsdom | preserve ID in current selection; understand replay/conflict/410; no localStorage. |
| Migration upgrade/downgrade | disposable PostgreSQL and SQLite migration coverage | exact schema and rollback, no deletion. |
| Duplicate preflight failure | disposable PostgreSQL fixture | fails before unique constraint; no silent canonicalization. |
| Regression | existing targeted Python/Node | Phase 1/2/3A limits, safe errors, ACL and shared upload behavior. |

SQLite/FakeStorage verifies state machine and contracts only. PostgreSQL integration is mandatory for concurrency because SQLite does not establish PostgreSQL constraint timing, row locks, isolation or upsert behavior. Browser tests must not call real S3. Manual staging uses a private non-production bucket to exercise POST, expiry, HEAD validation, timeout retry and two tabs without logging URL/key/bucket/provider body.

Acceptance: same session/key/metadata never creates more than one canonical item/object/key/counter increment; metadata conflict is safe 409; complete/finalize side effects happen once; expired presign creates no replacement session; migration preflight is clean; regression tests pass.
