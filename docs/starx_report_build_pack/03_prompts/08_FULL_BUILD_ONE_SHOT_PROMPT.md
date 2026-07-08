# PROMPT 08 — One-shot Build Prompt

Dùng khi muốn giao cho coding agent xây toàn bộ MVP trong một lần. Nếu agent yếu hoặc context nhỏ, nên dùng từng phase 01–07 thay vì prompt này.

---

Hãy xây hoàn chỉnh MVP cho **StarX Project Daily Report System**.

Tech stack:

- Python 3.12
- Flask full-stack
- Jinja + Bootstrap 5 + Chart.js
- PostgreSQL
- SQLAlchemy + Flask-Migrate
- Flask-Login
- Pillow
- pytest
- Gunicorn-ready

Không dùng React/Vue/S3/mobile/notification trong MVP.

## Modules cần có

1. App factory + config `.env`.
2. Models + migrations:
   - users
   - projects
   - project_users
   - report_categories
   - daily_reports
   - daily_report_sections
   - report_attachments
   - persistent_issues
   - audit_logs
3. Seed admin command.
4. Auth:
   - login/logout/change password
5. Permission:
   - SUPER_ADMIN all
   - VIEWER_ADMIN read all only
   - REPORTER read/write only assigned projects
6. Admin user management.
7. Admin project management.
8. Project assignment.
9. Report category management.
10. Daily reports:
   - create/edit/detail/list
   - unique(project_id, report_date)
   - sections by category
11. Attachments:
   - max 3 images per section
   - jpg/png/webp only
   - verify + resize with Pillow
   - store local folder by project/date/report/section
   - serve through protected route
12. Persistent issues:
   - CRUD + close/reopen
13. Dashboard:
   - total dashboard with filters
   - project dashboard
   - status pie chart
   - reports over time bar chart
14. Audit logs.
15. README local setup.
16. Deployment guide Ubuntu + Gunicorn + Nginx.
17. Tests for auth, permission, reports, attachments.

## UI yêu cầu

- Bootstrap 5 đơn giản.
- Sidebar/menu.
- Header user/role/logout.
- Flash messages.
- Tables/cards/badges.
- Không cần UI cầu kỳ.

## Status labels

DailyReport overall_status:

- UPDATED: Cập nhật
- GOOD: Tốt
- PROCESSING: Đang xử lý
- ATTENTION: Cần chú ý
- CRITICAL: Khẩn cấp

Section status:

- INFO: Thông tin
- GOOD: Tốt
- PROCESSING: Đang xử lý
- ATTENTION: Cần chú ý
- CRITICAL: Khẩn cấp

Issue severity:

- LOW, MEDIUM, HIGH, CRITICAL

Issue status:

- OPEN, PROCESSING, RESOLVED, CLOSED

## Important validation

- Không tạo report trùng project/date.
- Category phải thuộc đúng project.
- Reporter không thấy project chưa được assign.
- Viewer không được write.
- Attachment không public trực tiếp.
- Không upload file không phải ảnh.
- Không upload quá 3 ảnh/section.

## Deliverables

Sau khi code xong:

- Liệt kê file đã tạo/sửa.
- Cung cấp command chạy local.
- Cung cấp command migration/seed.
- Cung cấp test command.
- Cung cấp hướng dẫn deploy ngắn.
- Nêu các phần chưa làm trong MVP.
