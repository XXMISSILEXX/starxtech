# Batch upload plan

## UX and state machine

Folder/album page has accessible drag/drop zone plus “Chọn nhiều tệp” input (`multiple`). It accepts mixed allowed file types and creates a client queue with stable `client_file_id`. Each item displays name, type, size, progress and one state: **Chờ tải lên**, **Đang tải**, **Đã upload**, **Đang xử lý preview**, **Hoàn tất**, or **Lỗi**. Rejected items explain error before upload; retry/cancel applies per item; partial success never discards completed siblings.

`presign-batch` validates all candidate metadata but returns per-item accepted/rejected results. Accepted items receive distinct StorageObject, object key and signed policy. Browser uploads accepted files with bounded concurrency (recommend 3; video can reserve one slot), progress per XHR/fetch capability, then calls `complete-upload` per successful object. Complete drives derivative state: image/video show processing placeholder; document/audio complete immediately. Poll `GET upload-batches/<id>` initially; WebSocket/SSE is deferred.

## Limits and security defaults to approve

- Max files/batch: recommend 20 initially.
- Max total declared batch size: recommend 1 GiB, additionally enforce per target quota.
- Per-file caps and allowlist are business-approved by type; reject before presign.
- Presign-batch rate limit by user/target/IP; concurrency 3; cap pending batches/user.
- Backend generates key/bucket/status, rechecks RBAC/ACL on every complete, HEAD verifies uploaded object, and pending cleanup removes incomplete items.

No original/derivative URL is embedded for the whole album. Grid uses placeholders and lazily asks for signed thumbnail/original only when visible/clicked. Cancel before upload marks item cancelled; cancel after direct S3 PUT cannot guarantee network abort, so completion is refused/cleanup handles it. Upload failure leaves item failed/pending according to verified state; complete failure is retriable only if same authorized pending object still passes HEAD; processing failure leaves original available and placeholder visible.
