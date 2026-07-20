# Product requirements

## Project Documents

Mỗi project có cây folder nhiều cấp, tạo/đổi tên/lưu trữ và đề xuất move folder. Một folder chứa file metadata liên kết StorageObject: document, image, video, audio, hoặc loại được allowlist. Cần breadcrumb, search/filter đơn giản, grid/list, image thumbnail/album preview, viewer ảnh/video và download/open signed URL. Quyền kế thừa từ folder; MVP không cần ACL riêng từng file.

Share là allow cho user hoặc role, với quyền xem, upload, edit metadata, archive và share. Search phải chỉ trả record user có quyền view. Folder/file lifecycle là active/archived/restore; không hard-delete metadata trong luồng người dùng.

## Company Media

Album cấp ngoài duy nhất, không folder con. Album có cover, event date, description và chứa trực tiếp image/video. Cần grid album, grid media, lightbox/gallery, placeholder video thumbnail, search/filter và view-only mode. ACL album đơn giản: view, upload, manage album, archive file; share user/role.

## Non-goals MVP

- Public share link, CDN public, S3 public object, backend transcoding/thumbnail worker, antivirus bắt buộc, video processing, file versioning, OCR/full-text, collaboration realtime, quota billing, recycle bin object restore, và per-file override ACL.
- Không thay đổi report attachment hiện có hoặc serve file bytes qua Flask.

## Business questions cần chốt

- Assignment project có mặc định cấp `view` folder không, hay chỉ là điều kiện nền cho ACL?
- Folder root do ai quản lý và có cần root per project tự tạo?
- Size/loại file allowlist, retention, quota, và policy archive/delete object thực tế.
- Có bắt buộc preview PDF an toàn hay chỉ download attachment; cover album chọn tay hay tự động.
