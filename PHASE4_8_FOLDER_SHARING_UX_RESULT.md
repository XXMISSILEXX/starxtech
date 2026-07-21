# Phase 4.8 — Folder Sharing UX

Chia sẻ chỉ áp dụng ở cấp thư mục. Tệp không có ACL hoặc UI chia sẻ riêng; mọi tệp kế thừa quyền từ thư mục chứa nó.

RBAC vẫn là lớp quyền nền. Folder ACL chỉ cho phép hành động trên thư mục bị hạn chế khi user hoặc role có cờ tương ứng. Năm cờ ACL là `view`, `upload`, `edit`, `delete` (Lưu trữ) và `share`. Quyền tải xuống cần RBAC `project_document_files.download` và ACL `view`.

Màn hình **Chia sẻ thư mục** cho phép tìm user đang hoạt động hoặc role, dùng preset Chỉ xem + tải xuống, Cộng tác viên, Quản lý thư mục, hoặc Tùy chỉnh. Chọn một principal đã có ACL sẽ chuyển form sang cập nhật; có thể gỡ entry trực tiếp bằng POST có CSRF.

Kiểm tra thủ công: đăng nhập actor có `project_document_folders.share`, mở một folder và chọn **Chia sẻ thư mục**. Thử thêm user/role, sửa quyền, gỡ quyền, rồi xác nhận user không có RBAC share nhận 403 và không thấy CTA. Với restricted folder, đăng nhập principal được cấp để xác nhận quyền được kế thừa bởi tệp.
