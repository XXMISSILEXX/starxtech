# Batch Upload + Drag/Drop Flow

## UX requirement

Folder/album page must have:

- Drag/drop zone.
- Button “Chọn nhiều tệp”.
- `<input type=file multiple>`.
- Multi-file queue.
- Mixed allowed types in one batch.
- Per-file progress.
- Per-file retry/cancel.
- Partial success.
- Placeholder while worker processes preview.

## Per-item states

```text
Chờ tải lên
Đang tải
Đã upload
Đang xử lý preview
Hoàn tất
Lỗi
Đã hủy
```

## API flow

### 1. Presign batch

```http
POST /project-documents/files/presign-batch
POST /company-media/files/presign-batch
```

Payload example:

```json
{
  "target_id": 123,
  "files": [
    {
      "client_file_id": "f-1",
      "filename": "hop-dong.pdf",
      "mime_type": "application/pdf",
      "size": 2450000,
      "checksum_sha256": null
    },
    {
      "client_file_id": "f-2",
      "filename": "anh.jpg",
      "mime_type": "image/jpeg",
      "size": 5000000
    }
  ]
}
```

Response example:

```json
{
  "upload_batch_id": 88,
  "items": [
    {
      "client_file_id": "f-1",
      "accepted": true,
      "upload_batch_item_id": 991,
      "storage_object_id": 501,
      "method": "POST",
      "url": "https://s3...",
      "fields": {},
      "expires_at": "2026-07-20T10:10:00Z"
    },
    {
      "client_file_id": "f-2",
      "accepted": false,
      "error": "Loại file không được hỗ trợ"
    }
  ]
}
```

### 2. Browser uploads to S3

- Each accepted file uses its own signed URL/policy.
- Frontend concurrency default: 3.
- Video can reserve one slot to avoid blocking all progress.

### 3. Complete per file

```http
POST /project-documents/files/complete-upload
POST /company-media/files/complete-upload
```

Backend:

- Recheck RBAC/ACL.
- HEAD S3 object.
- Verify key/size/type/checksum.
- Active `StorageObject`.
- Create domain file record.
- Enqueue Celery job if image/video.
- Update batch counters.

### 4. Poll status

```http
GET /project-documents/upload-batches/<id>
GET /company-media/upload-batches/<id>
```

Response must be sanitized:

- Only creator or authorized target user can read.
- Do not expose unauthorized item names/counts.

## Limits

Recommended MVP:

```text
max_files_per_batch = 20
max_total_batch_size = 1 GiB
frontend_concurrency = 3
max_pending_batches_per_user = 3
upload_url_ttl = 5 minutes
```

## Error handling

### Rejected before upload

- Show item-level error.
- No StorageObject.
- UploadBatchItem status rejected.

### Upload fails

- Item failed/pending.
- Retry creates new presign or reuses same pending object only if still valid.
- No active file.

### Complete fails

- Permission revoked, HEAD mismatch, expired state.
- No active file.
- No worker job.
- Object cleanup handles orphan.

### Processing fails

- Original remains available.
- Placeholder shown.
- Admin/user may retry in future policy.
