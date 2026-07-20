# Executive Summary

## Bài toán

Cần xây dựng thêm 2 module mới cho hệ thống Flask hiện tại:

- Module quản lý tài liệu/hồ sơ dự án.
- Module quản lý ảnh/video toàn công ty.

Hai module này cần:

- Lưu file trên S3/Object Storage.
- Metadata lưu trong PostgreSQL.
- Upload trực tiếp từ browser lên S3 bằng signed URL.
- Bulk upload nhiều file, nhiều loại file, drag/drop.
- Thumbnail/preview/poster được tạo bởi worker riêng.
- Phân quyền rõ ràng theo RBAC + ACL resource-level.
- Không ảnh hưởng Daily Reports và Partner Management hiện có.

## Lựa chọn kiến trúc

Chọn kiến trúc:

```text
Browser
  -> Flask Web App
  -> PostgreSQL metadata/RBAC/ACL
  -> Redis broker/result backend
  -> Celery Workers
  -> S3/Object Storage private bucket
```

## Tách trách nhiệm

### Flask web app

- Login/session.
- RBAC canonical.
- Folder/album ACL.
- Metadata CRUD.
- Presign upload.
- Complete upload.
- Signed URL cấp quyền xem/tải.
- Không xử lý bytes file lớn.
- Không ffmpeg/Pillow trong web request.

### PostgreSQL

- Source of truth:
  - StorageObject.
  - StorageDerivative.
  - UploadBatch.
  - UploadBatchItem.
  - MediaProcessingJob.
  - ProjectDocumentFolder/File/ACL.
  - CompanyMediaAlbum/File/ACL.
  - AuditLog.

### Redis

- Celery broker.
- Celery result backend ngắn hạn.
- Không coi Redis là source of truth.

### Celery worker

- Image derivative:
  - thumbnail WebP.
  - preview WebP/JPEG.
- Video derivative:
  - ffprobe metadata.
  - poster frame.
- Cleanup/reconcile.
- Retry, timeout, idempotency.

### S3/Object Storage

- Bucket private.
- Không public object.
- Object key UUID.
- Original và derivative lưu dưới prefix riêng.

## Nguyên tắc sản phẩm

- User có thể kéo thả nhiều file.
- Một batch có thể gồm ảnh, video, PDF, DOCX, XLSX, MP3, v.v.
- File hợp lệ được upload; file không hợp lệ hiển thị lỗi riêng.
- Upload từng file độc lập, complete từng file độc lập.
- Partial success được chấp nhận.
- UI hiển thị tiến trình từng file.
- Worker fail không làm mất original; UI dùng placeholder.
- Không hard delete metadata trong luồng người dùng; dùng archive/restore.

## Thứ tự triển khai

1. Storage foundation + batch presign contract.
2. Redis/Celery worker foundation.
3. Project Documents core.
4. Project Documents upload/preview/share.
5. Company Media core.
6. Company Media gallery/ACL.
7. Hardening/deploy/monitoring.
