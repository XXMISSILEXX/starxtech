# Proposed fix plan (no implementation)

## Design principles

- Repair confirmed behavior first; do not change storage provider, objects, or media data merely to address the client contract.
- Keep original downloads private and server-authorized.
- Maintain current effective limits initially; configuration separation must not silently change product capacity.
- Preserve existing top-level `url` consumers while standardizing success/error contracts.

## Phase 1 — Single-download contract and storage-state hardening

### Goal

Make Company Media and Project Documents menu single-download navigate after the POST and validate that Company Media never signs an inactive/deleted storage object.

### Expected files

- `app/company_media/routes.py`, `app/company_media/services.py`
- `app/project_documents/routes.py`, `app/project_documents/services.py` only as needed to use the same successful contract
- `app/static/js/project-document-preview.js`
- Browser/route regression tests for both modules

### API contract

Use a backward-compatible success body:

```json
{
  "ok": true,
  "url": "<short-lived signed URL>",
  "expires_at": "<timestamp>",
  "filename": "<display filename>",
  "disposition": "attachment"
}
```

Keep top-level `url` and `expires_at`; do not switch to a nested `download` object in this endpoint. The helper must validate `ok` and non-empty `url`, then call `window.location.assign(url)`. Do not use blob downloads, popup windows, or a cross-origin `download` attribute.

### Compatibility, tests, risks, rollback

- Backward compatible for existing consumers of `url`.
- Add normal/missing URL, unauthorized, archived, missing/inactive object, provider-failure sanitization, and browser navigation tests.
- Include Project Documents because it shares the defect; preserve bulk and Daily Report paths.
- No migration or environment change.
- Deploy backend and versioned JS atomically. Roll back the pair together if browser navigation regression appears.

## Phase 2 — Company Media limits and error contract

### Goal

Give Company Media its own resolved limit configuration and distinguish user-correctable errors.

### Expected files

- `app/config.py`, `app/__init__.py`, `.env.example`, `docker-compose.yml`, README/deployment guidance
- `app/storage/services.py`, `app/storage/validation.py`
- Company Media routes/services/template/JS and tests

### Proposed settings and initial defaults

| Setting | Initial default | Source of baseline |
|---|---:|---|
| `COMPANY_MEDIA_MAX_SELECTION_FILES` | 500 | Current selection cap |
| `COMPANY_MEDIA_MAX_SELECTION_BYTES` | 2 GiB | Current selection cap |
| `COMPANY_MEDIA_MAX_FILES_PER_BATCH` | 50 | Current storage batch cap |
| `COMPANY_MEDIA_MAX_PRESIGN_BATCH_BYTES` | 512 MiB | Current storage batch cap |
| `COMPANY_MEDIA_MAX_FILE_BYTES` | 300 MiB | Current absolute cap |
| `COMPANY_MEDIA_UPLOAD_CONCURRENCY` | 3 | Current JS behavior |
| `COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS` | 7,200 s | Current selection TTL |

Category caps remain explicit: image 50 MiB and effective video 300 MiB under current shared type limits. Do not label 300 MiB as the image limit.

### Error contract

Use one envelope for Company Media application errors:

```json
{
  "ok": false,
  "error": {
    "code": "selection_total_bytes_exceeded",
    "message": "Tổng dung lượng đã chọn vượt quá giới hạn.",
    "details": {"actual_bytes": 0, "max_bytes": 0},
    "retryable": false
  }
}
```

Define stable codes for invalid/exceeded selection count/bytes, empty batch, batch count/bytes, file size, declared quota count/bytes, expired session, target mismatch, idempotency conflict, provider upload failure, and HEAD verification failure. Provider XML/raw messages remain client-side sanitized and must not be reflected.

### Compatibility, tests, risks, rollback

- When new settings are unset, use the existing shared settings as fallback.
- Start production values equal to current effective behavior.
- Test status, code, `details`, retryability, and no provider-data leakage.
- No migration.
- Rollback by unsetting new Company Media settings after code supports fallbacks.

## Phase 3 — Selection UX and retry/session lifecycle

### Goal

Show current/maximum limits before upload, make invalid state explicit and accessible, and make retry semantics intentional.

### Expected files

- `app/templates/company_media/album.html`
- `app/static/js/company-media-upload.js`
- Company Media route/service and storage service/model files only if idempotency is approved
- UI and session tests

### UX behavior

- Server renders resolved limits; JS does not own product constants.
- Display: selected files/max, selected bytes/max, per-file cap by type, files/bytes per batch, and concurrent uploads.
- Update on add/remove/drop; use B/KiB/MiB/GiB; announce changes with `aria-live`.
- Disable upload for invalid selection, but retain backend enforcement.
- Show actual/max and a text/icon state for normal, near limit, count exceeded, byte exceeded, per-file exceeded, expired session, and partial failure.

### Idempotency decision and migration assessment

Application-only reuse of an existing item can improve ordinary retries but cannot guarantee race safety. If the accepted requirement is “same selection session + same client file ID never creates a second pending object,” use a database-enforced key. That likely requires an additive migration, for example a nullable selection-session reference on upload items plus a partial unique constraint for non-null session rows, with an intentional backfill plan.

Do **not** create a migration until the desired retry semantics, concurrent-tab behavior, and legacy-row policy are approved. If race-safe uniqueness is not required, no migration is necessary; document residual concurrent retry risk.

### Lifecycle

Decide whether to add a user-visible cancel endpoint. It should be authenticated, scoped to actor/album/session, idempotent, and distinct from generic cleanup. It must not delete an already finalized/owned file. This is a product/lifecycle decision, not necessary to fix single download.

## Phase 4 — Regression, operations, and rollout

### Goal

Validate the repaired browser/provider path without exposing signed URLs or modifying production data.

### Expected files

- Tests, README, staging/CloudFly checklist, and operational documentation.

### Verification

- Use FakeStorage/browser tests for contract and navigation.
- Use a non-production staging bucket for signed-GET, Content-Disposition, Unicode filename, expiry, CORS, and HEIC derivative checks.
- Log only stable event code/module/file ID/status class; never log signed URLs, bucket/key, credentials, or provider response body.

### Rollout and rollback

1. Add tests and deploy Phase 1 backend + versioned frontend together.
2. Smoke-test one safe staging file before production.
3. Add limits/error/UI in a separately observable release.
4. Deploy any idempotency migration before code that depends on its unique constraint.
5. Roll back code/frontend as matched versions; leave additive schema in place on rollback.
