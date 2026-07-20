# Current state

## Upload/report attachment hiện tại

`ReportAttachment` hiện là upload local filesystem: metadata gồm `original_filename`, `stored_filename`, `file_path`, MIME, size và kích thước ảnh. `app.reports.services._store_attachment` nhận bytes vào Flask, Pillow verify/resize ảnh, ghi dưới `UPLOAD_ROOT/project_...`, và `attachments.view` dùng `send_file` sau kiểm tra quyền. Attachment bị soft-delete metadata, audit create/delete, giới hạn ba ảnh trên report section, chỉ nhận JPG/JPEG/PNG/WebP.

Điểm tốt cần giữ: UUID filename, relative-path traversal guard, private authorization trước khi xem, audit, soft-delete. Khoảng trống với mục tiêu mới: không có storage abstraction, signed URL, direct browser upload, metadata trạng thái pending, checksum, thumbnail key, video/audio/document, cleanup orphan, hoặc object lifecycle.

## RBAC và project scope hiện tại

RBAC canonical có `Role`, `Permission`, `RolePermission`, `User.role_id`, `current_user.can` và `permission_required`. Registry version-controlled, sync bằng CLI rõ ràng. SUPER_ADMIN bypass; các role khác nhận grant từ `DEFAULTS`.

Project có `ProjectUser` unique theo project/user. Helpers report hiện dùng module permission kết hợp assignment: admin/viewer có scope toàn bộ, PROJECT_MANAGER/REPORTER chỉ scope project được gán; REPORTER edit report của mình. Đây là mẫu nên tái sử dụng, nhưng document ACL cần scope riêng vì một user được gán project không tự động được xem mọi folder nếu folder có ACL hạn chế.

## Khoảng trống trước S3

- Config chưa có endpoint/bucket/region/credentials object storage hay provider interface.
- Report upload dùng Flask process bytes/Pillow; không phù hợp file lớn/video.
- Không có bảng storage object, job cleanup, thumbnail upload contract, hay policy allowlist theo loại file.
- Không có ACL resource-level. Permission hiện chỉ module-level/global role.
- Không có signed URL revocation thực sự; chỉ có thể chặn issuance mới sau revoke.

Khuyến nghị không chuyển report attachment cũ trong phase này. Xây storage abstraction riêng, test kỹ, rồi mới có migration/conversion proposal riêng nếu được duyệt.
