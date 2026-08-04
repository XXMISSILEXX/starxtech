# Findings — Phase 11 Delta: Private media cache and Company Media

## Summary

- Read all changed U1/U2 code named in `PHASE11-DELTA-SCOPE.md`, the changed migrations and tests, and unchanged authorization, provider, quota, media-processing and deployment callers reached by the new paths.  The latter were read only because a new cache, upload-cleanup route, or signed-delivery contract reaches them; they are not a re-audit of Phase 10.
- No new confirmed authorization bypass, public-object exposure, path traversal, cache-key collision, original-media preview fallback, or provider-error disclosure was found in the delta.
- The new Company Media cancellation intentionally cleans database metadata only.  It leaves possibly uploaded pending bytes in S3; this is documented as a deferred operational reconciliation design, not misclassified below as a newly discovered vulnerability.
- Files read in the primary scope: 33 changed/supporting files.  Old Company Media and storage baseline behaviour not reached by the delta remains covered by `findings-3b-uploads.md`, `findings-5-company-media.md`, `findings-7-attachments.md`, and `findings-12-deploy-iac.md`.

## Authorization and delivery matrix

| Flow | Object resolution and authority | Delta control | Result |
|---|---|---|---|
| Branding logo | `branding.logo` requires the global login hook; current active branding resolves server-side | Cache source is a hashed derivative/original identity and has no user-controlled path | Clean |
| Own avatar | Account route is self-only before cache use | Cached avatar is served only after account authorization | Clean |
| Report attachment thumbnail | `can_view_report` executes before derivative lookup | Processing placeholder on missing derivative; no original fallback | Clean |
| Project document thumbnail | document-view capability executes before derivative/poster lookup | Private cache or short signed derivative response only | Clean |
| Company Media thumbnail | album/file view ACL and active-file checks execute before derivative lookup | Private cache or short signed derivative response only | Clean |
| Company Media single download | distinct download ACL is checked before signing | `SignedDownloadError` gives stable application error rather than provider detail | Clean |
| Upload-session cancellation | album upload ACL, then session target lock, then owner/admin test | Transactional DB-only cleanup preserves completed/referenced rows | Clean for authorization/integrity |

## Explicitly checked and found clean

- `app/storage/cache.py:1-5,94-109,111-130,313-340` states and implements the required order: callers authorize first, cache derives a SHA-256 path from server-owned identity, then materialises a source.  It constrains extensions, validates regular files under a non-symlink root, uses `O_NOFOLLOW`/`lstat`, an advisory key lock, an exact-size check and atomic replacement.  A request cannot select a cache filename or an S3 key.
- Cache sources shown by the new routes are derivatives/posters only.  `app/company_media/routes.py:166-179` chooses `thumbnail` or `poster`; it returns the existing processing placeholder if no derivative exists.  The changed report/project-document paths have the same no-original-fallback property.  This conforms to the deliberate Phase 10/CLAUDE media rule.
- `deploy/nginx/starx-report.conf:9-15` marks the cache location `internal`; `docker-compose.yml:45-50,96-99` exposes no cache port and mounts it only into `web`.  In the default `send_file` delivery mode Flask still authorizes before bytes are emitted.  In `x_accel` mode the internal location accepts only the validated relative cache path emitted by the cache service.
- Cancellation has two independent authorization checks: route-level `upload_album` (`app/company_media/routes.py:128-137`) and locked session ownership/admin authorization (`app/company_media/upload_cleanup.py:65-90`).  The target tuple is checked before cleanup.  A user authorized to upload album A cannot cancel a session belonging to album B, and an album uploader cannot cancel another uploader's session unless an ADMIN/SUPER_ADMIN.
- Cleanup locks the selection, items and candidate storage rows (`upload_cleanup.py:93-159`), skips completed items, and calls `_storage_object_is_disposable` before deleting metadata.  Tests cover target mismatch, ownership, replay, completed-file preservation and provider non-invocation.
- Company Media presign persists the canonical selection/item state before provider signing (`app/storage/services.py:419-533`) and uses the unique selection/client-file-id migration plus savepoint replay handling.  Concurrent repeated client IDs do not receive a second canonical storage object or consume quota twice.
- The routes are POST for all state changes and remain protected by the application-wide Flask-WTF CSRF hook.  New GET thumbnail routes have no mutable action.  `ENDPOINTS-g5.md` records every changed endpoint and its module-gate outcome.

## Accepted design / operational risks

### CM-OP-001 — Cancelled Company Media upload bytes can remain in S3 without an in-repository reconciliation owner

- **Classification:** Accepted, documented operational limitation; not a confirmed authorization or data-exposure vulnerability.
- **Confidence:** High.
- **Location:** `app/company_media/upload_cleanup.py:1-5,93-99,152-159`; `app/company_media/routes.py:128-144`; `docs/Phase11_Fix_Single_Download_CONFIG_AND_UI/VERIFICATION_REPORT.md:234-239`; Phase 5 implementation/investigation records listed in the scope map.
- **Evidence:** The cleanup module deliberately imports no provider and deletes only disposable DB rows.  Consequently, an object that reached S3 before a user cancels can remain under a private pending key after its `StorageObject` row has been removed.  The Phase 5 documents explicitly choose this DB-only boundary and defer bucket reconciliation; the changed Phase 11 tests deliberately assert that cleanup never calls the provider.
- **Impact:** An authorized uploader can consume private bucket capacity with abandoned upload bytes until a separate object-store lifecycle/reconciliation process removes them.  It does not grant an attacker a URL, bucket listing, object key, or read access: objects remain private and all application read routes depend on database-backed objects and ACL checks.
- **Why it is not a finding:** Calling S3 or silently deleting unknown keys from an HTTP cancel endpoint would violate the project’s intentional async/S3-only ownership boundary.  The condition is a known, documented operations decision, not an accidental failure of a stated security invariant.
- **Required release evidence:** The production owner should provide a bucket lifecycle/reconciliation policy for the Company Media pending-key prefix, retention period, alert/usage threshold, and an approved runbook.  This audit did not contact S3, list keys, or run the mutating cleanup CLI.

### STORAGE-OP-002 — Presigned POST capacity allowance needs production-provider observation

- **Classification:** Unverified operational capacity risk, not a confirmed bypass.
- **Location:** `app/config.py:94-99`; `.env.example:73`; Company Media resolved limits in `app/storage/limits.py` and presign path in `app/storage/services.py:419-533`.
- **Evidence:** The configured 1 MiB multipart overhead is deliberately added to the provider POST `content-length-range` because CloudFly evaluates multipart request size, while completion HEAD-checks the exact declared object bytes.  Session and quota accounting use declared file bytes.  This is an explicit compatibility compromise, not an unconstrained upload.
- **Impact:** Repeated abandoned POSTs may temporarily consume slightly more physical capacity than declared accounting observes, especially together with CM-OP-001.  Completion rejects an object whose final object size is not the declared size.
- **Needed verification:** In staging against the actual provider, upload at the byte boundary and reject oversized object bodies; observe quota/bucket metrics and confirm lifecycle removal of expired/cancelled pending keys.  Do not infer provider behaviour from the fake provider tests.

## Needs verification

- Exercise cache miss/hit and `x_accel` delivery in a production-like Compose host with the bind directory owned/writable by container UID 1000 (`Dockerfile:13-25`) and readable by Nginx.  Source configuration is coherent; host ownership and actual Nginx routing are deployment facts not established by unit tests.
- Confirm production logging/redaction and provider error categories without recording signed URLs, storage keys, bucket names or credentials in the audit record.

## Test evidence

Passed read-only suites during this audit:

```text
PYTHONWARNINGS=error .venv/bin/python -m pytest -q -ra \
  tests/test_media_cache.py tests/test_signed_download_contract.py \
  tests/test_company_media_permissions_ux.py tests/test_company_media_phase4_idempotency.py \
  tests/test_company_media_phase5_cleanup.py tests/test_company_media_upload_limits.py
# 76 passed
```

The environment’s virtualenv reports Python 3.10, while production is pinned to Python 3.12.  These tests establish application behaviour but do not substitute for the required 3.12 deployment smoke test.
