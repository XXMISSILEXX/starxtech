# S3 storage architecture

## StorageObject và object key

Lưu một `StorageObject` metadata chung; bucket private, object không public. DB chỉ lưu bucket, `object_key`, optional `thumbnail_object_key`, tên gốc, MIME, extension, size, checksum, media dimensions/duration, uploader, state và timestamps. Không lưu signed URL.

Object key không chứa project/folder/album name để rename/move không copy object:

```text
originals/YYYY/MM/<uuid>.<normalized-ext>
thumbnails/YYYY/MM/<uuid>.webp
```

Có thể thêm immutable namespace provider/env (`starx/prod/...`) ở bucket policy, không từ user input. `original_filename` chỉ metadata/display; tuyệt đối không ghép vào path/key.

## Direct upload flow

1. User drag/drop hoặc chọn nhiều file; frontend gửi danh sách metadata đến `presign-batch`, cùng folder/album target.
2. Backend kiểm tra CSRF, module RBAC, project scope/ACL, allowlist, batch limit/quota; tạo một `UploadBatch`, một `UploadBatchItem` và một `StorageObject(status=pending)` cho **mỗi file hợp lệ**; sinh UUID key riêng từng object.
3. Backend trả signed upload policy URL/fields riêng từng item. Item bị reject trả lỗi theo item, không hủy các file hợp lệ.
4. Browser upload trực tiếp S3 song song với concurrency giới hạn; không qua Flask và không được tự chọn object key.
5. UI gọi `complete-upload` riêng từng file. Backend recheck RBAC/ACL, pending state, expected key, và S3 `HEAD` object; khi hợp lệ chuyển active, tạo link file/domain record atomically, rồi enqueue Celery nếu là image/video.
6. Document/audio không cần media processing MVP. Viewer/download recheck quyền mỗi lần và trả signed GET URL ngắn hạn; browser redirect/open URL đó.

Không cho client chọn `object_key`, bucket, owner, file status, storage size, hoặc file association. Failed completion giữ `pending`/`failed`, không hiện list active.

## Presigned POST vs PUT

**Khuyến nghị Presigned POST** cho browser upload khi S3-compatible provider hỗ trợ: policy ràng buộc exact key, `content-length-range`, content type/prefix, success status và expiry. Nó giảm việc client thay đổi header/key ngoài ý định.

**Presigned PUT** đơn giản hơn và phổ biến hơn ở một số provider; dùng được nếu backend ký exact key, expected content type/content length (nếu provider enforce), TTL ngắn và completion HEAD verify. Không tin declared MIME/size chỉ vì PUT thành công. Multipart upload/delegated S3 UploadId để phase sau cho file rất lớn; MVP nên cap video để tránh complexity.

## Signed URL TTL và CORS

- Upload: 5 phút (tối đa 10 phút); client hết hạn phải request key/presign mới, pending key cũ cleanup. GET URL không bao giờ lưu database.
- View inline image/video: 2–5 phút. Download attachment: 1–5 phút, `Content-Disposition: attachment` cho risky document; URL đã phát không revoke được trước expiry.
- Bucket CORS: chỉ exact HTTPS origins của app (local dev riêng), methods POST/PUT/GET/HEAD cần thiết, headers tối thiểu (`Content-Type`, `x-amz-*`/provider required), expose tối thiểu ETag/checksum, max-age vừa phải. Không `*` origin/headers/credentials.

## Thumbnail policy

Browser có thể tạo preview tức thời để UX, nhưng Celery worker là nguồn derivative chính thức. Image pipeline tạo thumbnail WebP và preview WebP/JPEG từ original; video pipeline dùng ffprobe lấy duration/width/height và tạo poster frame WebP/JPEG, không transcode full video trong MVP. Worker ghi `StorageDerivative`, không ghi đè original. Trong lúc worker chưa xong hoặc thất bại UI dùng placeholder. PDF/document/audio dùng icon MIME.

## Pending cleanup và failure

Cron/CLI job tương lai lấy pending quá 24 giờ, đánh dấu failed/deleted và gọi delete-object best effort; job idempotent, audit cleanup. Complete phải HEAD object và reject absent/zero/too-large/mismatch. Metadata archive không xóa S3 ngay; retention worker xóa object sau approved retention, có retry/dead-letter log. S3 versioning/lifecycle policy là optional provider safeguard, không thay thế DB state.
