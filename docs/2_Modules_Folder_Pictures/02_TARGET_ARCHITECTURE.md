# Kiến trúc mục tiêu

## Sơ đồ tổng thể

```text
[Browser]
   |
   | 1. Login, browse, drag/drop, request presign
   v
[Flask Web App]
   |
   | metadata/RBAC/ACL/audit
   v
[PostgreSQL]
   |
   | enqueue task
   v
[Redis Broker]
   |
   | consume task
   v
[Celery Worker]
   |
   | download original / upload derivatives
   v
[S3/Object Storage Private Bucket]
```

## Luồng upload tổng quát

```text
1. User mở folder/album.
2. User kéo thả nhiều file.
3. Frontend gọi presign-batch.
4. Flask kiểm tra RBAC + ACL + quota + allowlist.
5. Flask tạo UploadBatch/UploadBatchItem/StorageObject pending.
6. Flask trả signed upload URL riêng từng item.
7. Browser upload trực tiếp lên S3.
8. Browser gọi complete-upload từng file.
9. Flask HEAD object, verify size/type/checksum.
10. Flask active StorageObject và domain file.
11. Nếu ảnh/video: tạo MediaProcessingJob + gửi Celery task.
12. Worker tạo thumbnail/preview/poster.
13. UI polling batch status và cập nhật grid.
```

## Luồng xem/tải file

```text
1. User click thumbnail/file.
2. Browser gọi signed-url endpoint.
3. Flask kiểm tra login + RBAC + ACL + file active.
4. Flask trả signed GET URL ngắn hạn.
5. Browser mở ảnh/video/document từ S3.
```

## Module Project Documents

```text
Project
  └── ProjectDocumentFolder
        ├── child folders
        └── ProjectDocumentFile
              └── StorageObject
                    └── StorageDerivative(s)
```

Đặc điểm:

- Folder tree nhiều cấp bằng `parent_id`.
- Rename/move folder không ảnh hưởng object key.
- Folder ACL kế thừa/allow-only.
- File kế thừa quyền từ folder trong MVP.
- Search/list luôn authorization-filtered trước pagination.

## Module Company Media

```text
CompanyMediaAlbum
  └── CompanyMediaFile
        └── StorageObject
              └── StorageDerivative(s)
```

Đặc điểm:

- Album một cấp.
- Không có folder con.
- Album ACL allow-only.
- Album grid + media grid + lightbox/gallery.
- Cover lấy từ derivative của media trong album hoặc được chọn thủ công.

## Không ảnh hưởng module cũ

```text
Daily Reports
  -> ReportAttachment local filesystem giữ nguyên.

Partner Management
  -> lifecycle/archive/restore giữ nguyên.
```

Không có shared upload route nào được dùng bởi ReportAttachment cũ nếu chưa có migration riêng.
