# Acceptance Checklist

## Global

- [ ] Daily Reports local attachments still work.
- [ ] Partner module still works.
- [ ] Existing RBAC tests pass.
- [ ] No public S3 object.
- [ ] No signed URL persisted.
- [ ] No GET mutation.
- [ ] CSRF on POST.
- [ ] Security audit no FAIL.

## Storage foundation

- [ ] StorageObject table exists.
- [ ] UploadBatch/Item works.
- [ ] Presign-batch returns per-item accepted/rejected.
- [ ] Object key generated server-side.
- [ ] Complete HEAD verifies object.
- [ ] Strict ACL recheck on complete.
- [ ] Pending cleanup dry-run works.

## Worker

- [ ] Redis/Celery running.
- [ ] Image thumbnail generated.
- [ ] Image preview generated.
- [ ] Video poster generated.
- [ ] Video metadata saved.
- [ ] Duplicate tasks idempotent.
- [ ] Failed tasks terminal after retries.
- [ ] Temp files cleaned.
- [ ] Original not deleted on derivative failure.

## Project Documents

- [ ] Folder tree works.
- [ ] Rename/move works.
- [ ] Cycle blocked.
- [ ] ACL view/upload/edit/delete/share works.
- [ ] Unauthorized folder not visible/searchable.
- [ ] Bulk upload mixed file types works.
- [ ] Image/video previews work.
- [ ] Documents/audio signed download works.
- [ ] Archive/restore works.

## Company Media

- [ ] Album only one level.
- [ ] No child folder.
- [ ] Album ACL works.
- [ ] Bulk upload images/videos works.
- [ ] Gallery/lightbox works.
- [ ] Cover works.
- [ ] Archive/restore works.

## Manual testing

- [ ] Upload 20 mixed files.
- [ ] Upload invalid files and see per-item errors.
- [ ] Interrupt upload and cleanup.
- [ ] Revoke ACL after presign and complete fails.
- [ ] Mobile drag/drop/file picker works.
- [ ] Worker restart does not lose jobs.
- [ ] Redis restart reconciles from DB.
- [ ] S3 bucket private verified.
