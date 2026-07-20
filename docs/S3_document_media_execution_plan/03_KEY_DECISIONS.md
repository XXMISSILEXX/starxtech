# Quyết định cần chốt trước khi implement

## 1. Queue

**Chọn:** Celery + Redis.

- Redis là broker/result backend vận hành.
- PostgreSQL là source of truth.
- Result backend Redis có expiry ngắn.
- DB `MediaProcessingJob` quyết định trạng thái lâu dài.

## 2. Batch upload

**Chọn:** Có `UploadBatch` + `UploadBatchItem`.

Lý do:

- Lưu được item bị reject trước khi có StorageObject.
- Theo dõi partial success.
- Retry/cancel từng item rõ ràng.
- UI queue ổn định.
- Audit/counters dễ kiểm tra.

## 3. Strict complete sau khi revoke ACL

**Chọn:** Strict block.

Nếu user được presign nhưng sau đó bị revoke quyền trước khi complete:

- `complete-upload` phải bị chặn.
- Object pending để cleanup xử lý.
- Không active metadata.
- Không enqueue worker.

## 4. Video processing MVP

**Chọn:** Chỉ poster + metadata, không full transcode.

Worker video:

- `ffprobe` lấy duration/width/height.
- `ffmpeg` lấy poster frame.
- Không tạo bản MP4 preview 720p trong MVP.

## 5. Multipart upload

**Chọn:** Không làm MVP.

Thay vào đó:

- Giới hạn video ban đầu 300–500 MB/file.
- Nếu nhu cầu video lớn hơn, thêm multipart phase riêng.

## 6. Antivirus/quarantine

**Chọn MVP:** Chưa bắt buộc nhưng phải ghi nhận residual risk.

Mitigation tạm thời:

- allowlist file types.
- size caps.
- risky document disposition attachment.
- audit upload/download.
- không public share.
- nếu file từ nguồn không tin cậy, cần phase AV trước rollout rộng.

## 7. Batch limits ban đầu

Khuyến nghị:

```text
Max files / batch: 20
Max total batch size: 1 GiB
Frontend concurrency: 3
Video concurrency in worker: 1
Image worker concurrency: 1–2
Upload URL TTL: 5 phút, tối đa 10 phút
GET URL TTL: 2–5 phút
```

Per-file caps gợi ý:

```text
Image: 50 MB
Document: 200 MB
Video: 500 MB
Audio: 200 MB
```

## 8. Project documents root policy

Khuyến nghị MVP:

- Project assignment là baseline để vào project.
- Root folder có baseline view/upload theo role/project assignment.
- Folder ACL trong MVP là **allow-only add grants**.
- Không implement explicit deny.
- Nếu cần folder riêng tư, thêm `visibility=restricted` ở phase Project Documents.

## 9. Company Media default access

Khuyến nghị:

- ADMIN: full.
- VIEWER_ADMIN: view/download.
- PROJECT_MANAGER/REPORTER: không có mặc định.
- Nếu muốn toàn công ty xem ảnh, tạo role/grant riêng sau.

## 10. Polling hay SSE/WebSocket

**Chọn MVP:** Polling.

- `GET upload-batches/<id>` mỗi 2–5 giây trong lúc upload/processing.
- SSE/WebSocket để phase sau nếu cần realtime hơn.
