# PROMPT 00 — MASTER CONTEXT

---

Bạn là senior full-stack engineer. Hãy xây hệ thống độc lập tên **StarX Project Daily Report System**.

Mục tiêu: xây một web app nội bộ đơn giản để quản lý báo cáo tiến độ dự án hằng ngày.

Công nghệ bắt buộc:

- Python 3.12
- Flask full-stack
- Jinja templates
- Bootstrap 5
- Chart.js
- PostgreSQL
- SQLAlchemy ORM
- Flask-Migrate/Alembic
- Flask-Login
- Pillow để kiểm tra/resize ảnh
- Không dùng React/Vue trong MVP
- Không dùng ERP/FSM/hệ thống khác

Role người dùng:

1. `SUPER_ADMIN`: Admin tổng, toàn quyền.
2. `VIEWER_ADMIN`: Admin chỉ xem, xem toàn bộ nhưng không sửa/xóa/tạo.
3. `REPORTER`: Người báo cáo/quản lý dự án, chỉ xem/tạo/sửa báo cáo của project được phân quyền.

Core modules:

- Auth/login/logout/change password.
- User management.
- Project management.
- Gán user vào project.
- Report categories / đầu mục báo cáo theo project.
- Daily report.
- Daily report sections.
- Attachments, tối đa 10 ảnh/section.
- Persistent issues / vấn đề xuyên suốt.
- Dashboard tổng.
- Dashboard project.
- Audit log đơn giản.

Database entities:

- users
- projects
- project_users
- report_categories
- daily_reports
- daily_report_sections
- report_attachments
- persistent_issues
- audit_logs

Important rules:

- Một project chỉ có một daily report cho một report_date: unique(project_id, report_date).
- Category không được trùng tên trong cùng project.
- Reporter chỉ thấy project được gán trong `project_users`.
- VIEWER_ADMIN không được write bất kỳ dữ liệu nào.
- Attachment không được public trực tiếp; phải serve qua `/attachments/<id>` và kiểm tra quyền.
- Mỗi section tối đa 10 ảnh.
- Chỉ nhận jpg, jpeg, png, webp.
- Dùng UUID cho stored filename.
- Resize ảnh lớn về max width 1920px.
- Không commit `.env`.
- Không làm quá phức tạp.

Status:

Daily report overall_status:

- UPDATED: Cập nhật
- GOOD: Tốt
- PROCESSING: Đang xử lý
- ATTENTION: Cần chú ý
- CRITICAL: Khẩn cấp

Report section status:

- INFO: Thông tin
- GOOD: Tốt
- PROCESSING: Đang xử lý
- ATTENTION: Cần chú ý
- CRITICAL: Khẩn cấp

Persistent issue severity:

- LOW
- MEDIUM
- HIGH
- CRITICAL

Persistent issue status:

- OPEN
- PROCESSING
- RESOLVED
- CLOSED

Yêu cầu coding style:

- Code rõ ràng, boring, dễ bảo trì.
- Tách blueprint theo module: auth, dashboard, users, projects, reports, issues, attachments.
- Có `app/models/` tách model theo file hoặc một file models.py nếu đơn giản.
- Có decorators kiểm tra quyền.
- Có service layer đơn giản cho logic phức tạp.
- Có templates Bootstrap đơn giản, không cần đẹp phức tạp.
- Có migration.
- Có seed command tạo SUPER_ADMIN đầu tiên.
- Có README hướng dẫn chạy local.
- Có test tối thiểu cho auth, permission, reports, attachments.

Mỗi lần code, hãy:

1. Kiểm tra kiến trúc hiện tại trước.
2. Không phá chức năng đã có.
3. Sau khi sửa, chạy test/lint nếu có.
4. Ghi rõ file đã tạo/sửa.
5. Ghi rõ command để chạy.

Không xây notification, mobile app, React frontend, S3, workflow duyệt, export PDF phức tạp trong MVP.
