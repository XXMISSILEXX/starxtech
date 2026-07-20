# Test plan

## Automated tests

### Authorization and lifecycle

- Module access and default-grant matrix for SUPER_ADMIN, ADMIN, VIEWER_ADMIN, PROJECT_MANAGER and REPORTER.
- Project assignment prerequisite; folder/album ACL user and role grants; no matching allow means no view.
- Inherited/restricted folder rule, upload/edit/delete/share enforcement, and UI controls consistent with backend.
- Unauthorized user cannot browse, search, infer count, presign, complete, or receive signed URL.
- Archived folder/file/album/media excluded from active lists; detail/restore policy and audit verified.
- All mutations POST-only with CSRF; GET has no side effect; audit action and actor assertions.

### Folder/document behavior

- Create/rename/move supports parent tree; duplicate active sibling names rejected; cross-project destination rejected.
- Self/descendant cycle rejected, including concurrent/retry-safe service test.
- Rename/move changes only metadata; StorageObject `object_key` remains identical.
- File must belong to folder/project matching presign scope; search filters only authorized active records.
- Folder archive visibility behavior for descendants matches selected policy.

### Storage contract (use fake S3 client; no real network)

- Presign rejects extension/MIME/size/quota/ACL failures and emits expected exact generated key.
- Presign creates pending metadata, never active file visible; response has expiry but no credentials beyond signed policy.
- Complete calls HEAD and accepts expected key/size/status; transition pending → active is idempotent once.
- Missing object, changed size/type/checksum, expired/failed status and repeated completion fail safely.
- Thumbnail key is linked and optional; image/video/document placeholder behavior is correct.
- Pending cleanup marks state and deletes only exact eligible prefix/key; retry/idempotency and audit tested.
- Signed GET only generated after current authorization; revoke ACL prevents new URL. Verify URL is not persisted/logged.

### Batch upload

- `presign-batch` accepts mixed valid types and rejects invalid files per item; each accepted item creates separate pending StorageObject/key/policy and client cannot override key.
- Reject too many files, total batch size/quota excess and duplicate client file ID; accepted siblings still proceed when another item is rejected.
- Complete one item independently, partial batch status/counters correct, failed item retry/cancel semantics correct, and incomplete batch pending cleanup is idempotent.
- ACL revoked after presign blocks strict complete; HEAD/authorization failure never creates visible file or worker job.

### Celery/media worker

- Image derivative success with fake S3/Pillow; video poster/metadata with mocked ffprobe/ffmpeg or tiny fixture.
- Worker ignores inactive/deleted/failed object; duplicate task/job is idempotent; timeout and max retry set terminal failed state.
- Generated derivative key is server-only, temp directory cleanup runs on success/error, and signed URL is never persisted.
- Daily Report local `ReportAttachment`, Partner module and canonical RBAC regression suites remain unchanged.

### Company media

- Album only one level: no child-folder route/model path accepted.
- Album view/upload/manage/delete/share ACL; file media type restricted image/video.
- Grid pagination/filter includes only authorized album files; cover must belong to same active album or approved object.

## Manual tests

- Browser direct upload image, permitted document/audio, max-size rejection, interrupted upload then cleanup, and expired presign retry.
- Large image canvas thumbnail and original viewer; CORS from actual app origin; video first-frame success and placeholder fallback.
- Many-image folder collage/grid, signed lightbox, video controls, document attachment disposition.
- Mobile cards, keyboard modal/lightbox, view-only/share/revoke flow, archived badges and restore.
- S3 console verifies bucket private, public access blocked, prefix/IAM policy minimal, CORS exact origin, no signed URLs in database/audit.

## Regression tests

- Existing report attachment upload/view/delete and path traversal tests must remain unchanged.
- Existing project assignment, canonical RBAC, Viewer-admin read-only behavior, audit and CSRF tests all run.
- Batch limits, worker queue routing/retry/reconcile and ACL-revoke-during-upload tests run with Celery eager/fake transport; one integration suite runs private test bucket + Redis separately.
- Run migration dry review only after approved schema work; this investigation creates no migration.
