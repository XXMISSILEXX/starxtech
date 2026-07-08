# ===== 00_MASTER_CONTEXT_COPY_PASTE.md =====

# PROMPT 00 — MASTER CONTEXT

Copy toàn bộ prompt này vào Codex/AI coding agent trước khi bắt đầu bất kỳ phase nào.

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
- Attachments, tối đa 3 ảnh/section.
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
- Mỗi section tối đa 3 ảnh.
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



# ===== 01_PHASE_1_APP_FOUNDATION.md =====

# PROMPT 01 — App Foundation + Database

Copy prompt này sau khi đã đưa MASTER CONTEXT.

---
Hãy đọc nội dung file Agents.md, sau đó thực hiện: 
Hãy tạo foundation cho Flask app **StarX Project Daily Report System**.

Yêu cầu:

1. Tạo cấu trúc project:

```text
starx-report/
  app/
    __init__.py
    config.py
    extensions.py
    models/
    auth/
    dashboard/
    users/
    projects/
    reports/
    issues/
    attachments/
    templates/
    static/
  migrations/
  tests/
  storage/uploads/
  .env.example
  requirements.txt
  run.py
  wsgi.py
  README.md
```

2. Cài extensions:

- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- python-dotenv
- psycopg2-binary hoặc psycopg[binary]
- Pillow
- gunicorn
- pytest

3. Config qua `.env`:

- SECRET_KEY
- DATABASE_URL
- UPLOAD_ROOT
- MAX_UPLOAD_MB
- MAX_IMAGES_PER_SECTION
- APP_ENV

4. Tạo app factory `create_app()`.

5. Register blueprint rỗng ban đầu cho:

- auth
- dashboard
- users
- projects
- reports
- issues
- attachments

6. Tạo base template Bootstrap 5:

- sidebar/menu đơn giản
- header user
- flash messages
- block content

7. Tạo trang `/health` trả JSON `{status: "ok"}`.

8. Tạo README hướng dẫn:

- tạo venv
- cài requirements
- tạo database PostgreSQL
- chạy migration
- chạy app local

Sau khi code xong, cung cấp command đầy đủ để chạy local trên Ubuntu.



# ===== 02_PHASE_2_MODELS_MIGRATIONS_SEED.md =====

# PROMPT 02 — Models, Migrations, Seed Admin

---
Hãy đọc nội dung file Agents.md, sau đó thực hiện: 
Hãy thêm toàn bộ SQLAlchemy models và migration cho hệ thống.

Models cần có:

- User
- Project
- ProjectUser
- ReportCategory
- DailyReport
- DailyReportSection
- ReportAttachment
- PersistentIssue
- AuditLog

Yêu cầu:

1. Tạo enum/constants cho role và status:

- UserRole: SUPER_ADMIN, VIEWER_ADMIN, REPORTER
- ProjectStatus: active, paused, completed, archived
- DailyReportStatus: UPDATED, GOOD, PROCESSING, ATTENTION, CRITICAL
- SectionStatus: INFO, GOOD, PROCESSING, ATTENTION, CRITICAL
- IssueSeverity: LOW, MEDIUM, HIGH, CRITICAL
- IssueStatus: OPEN, PROCESSING, RESOLVED, CLOSED

2. Thêm relationship hợp lý giữa models.

3. Thêm unique constraints:

- User.username unique
- User.email unique nếu có
- Project.code unique
- ProjectUser(project_id, user_id) unique
- ReportCategory(project_id, name) unique
- DailyReport(project_id, report_date) unique
- DailyReportSection(daily_report_id, report_category_id) unique

4. Thêm timestamps.

5. Thêm soft delete field `deleted_at` cho bảng quan trọng.

6. Tạo Flask CLI command:

```bash
flask seed-admin --username admin --password 'Admin@123456' --email admin@example.com --full-name 'System Admin'
```

Command này:

- Nếu chưa có SUPER_ADMIN thì tạo.
- Nếu username đã tồn tại thì báo rõ.
- Password phải hash.

7. Tạo migration bằng Flask-Migrate.

8. Cập nhật README command:

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
flask seed-admin ...
```

Sau khi làm xong, cung cấp danh sách file đã tạo/sửa và command test nhanh bằng Flask shell hoặc route health.



# ===== 03_PHASE_3_AUTH_AND_PERMISSIONS.md =====

# PROMPT 03 — Auth + Permissions

---
Hãy đọc nội dung file Agents.md, sau đó thực hiện 
Hãy xây module authentication và permission cho StarX Project Daily Report System.

Yêu cầu chức năng:

1. Login:

- GET /login
- POST /login
- Dùng username hoặc email.
- Check password hash.
- Chặn user inactive.
- Set `last_login_at`.

2. Logout:

- POST /logout

3. Change password:

- GET /change-password
- POST /change-password
- User đang login được đổi password.
- Cần nhập current password.

4. Login required:

- Các route khác ngoài /login và /health phải cần đăng nhập.

5. Permission decorators:

- `role_required(*roles)`
- `viewer_or_admin_required()` nếu cần
- `can_read_project(project_id)`
- `can_write_project(project_id)`
- `project_read_required(project_id_arg='project_id')`
- `project_write_required(project_id_arg='project_id')`

Rule:

- SUPER_ADMIN: read/write all.
- VIEWER_ADMIN: read all, write none.
- REPORTER: read/write only assigned projects.

6. UI:

- Login page Bootstrap đơn giản.
- Base layout hiển thị user và role.
- Menu ẩn/hiện theo role.

7. Security:

- CSRF protection nếu có dùng Flask-WTF.
- Session cookie config từ config.py.
- Không log password.

8. Tests tối thiểu:

- login đúng/sai.
- inactive user không login được.
- VIEWER_ADMIN bị chặn route write.
- REPORTER không đọc được project chưa được gán.

Sau khi làm xong, cung cấp command chạy test và cách tạo user admin seed để login.



# ===== 04_PHASE_4_ADMIN_USERS_PROJECTS_CATEGORIES.md =====

# PROMPT 04 — Admin Users, Projects, Categories

---

Hãy xây các màn hình quản trị cho SUPER_ADMIN.

## A. User Management

Routes:

```text
GET  /admin/users
GET  /admin/users/create
POST /admin/users/create
GET  /admin/users/<id>/edit
POST /admin/users/<id>/edit
POST /admin/users/<id>/deactivate
POST /admin/users/<id>/activate
POST /admin/users/<id>/reset-password
```

Fields:

- full_name
- username
- email
- role
- is_active
- password khi tạo

Validation:

- username required unique
- email unique nếu nhập
- password tối thiểu 8 ký tự khi tạo
- role nằm trong SUPER_ADMIN, VIEWER_ADMIN, REPORTER

## B. Project Management

Routes:

```text
GET  /admin/projects
GET  /admin/projects/create
POST /admin/projects/create
GET  /admin/projects/<id>/edit
POST /admin/projects/<id>/edit
POST /admin/projects/<id>/archive
GET  /admin/projects/<id>/users
POST /admin/projects/<id>/users
```

Fields:

- code
- name
- description
- status
- start_date
- expected_end_date

Project assignment:

- Admin chọn nhiều REPORTER để gán vào project.
- Không gán VIEWER_ADMIN bắt buộc vì viewer xem toàn bộ.
- Cho phép remove reporter khỏi project.

## C. Report Categories

Routes:

```text
GET  /admin/projects/<project_id>/categories
POST /admin/projects/<project_id>/categories/create
POST /admin/categories/<id>/edit
POST /admin/categories/<id>/deactivate
POST /admin/categories/<id>/activate
```

Fields:

- name
- description
- icon
- sort_order
- is_active
- is_required

Validation:

- Không trùng name trong cùng project.
- Nếu category đã được dùng trong report, không xóa cứng, chỉ deactivate.

## UI

- Bootstrap table.
- Badge role/status.
- Nút create/edit/deactivate.
- Flash message rõ ràng.

## Audit

Ghi audit log cho:

- create/update/deactivate/activate user
- create/update/archive project
- assign/remove project user
- create/update/deactivate category

## Tests

- VIEWER_ADMIN không truy cập được admin write routes.
- REPORTER không truy cập được admin routes.
- SUPER_ADMIN tạo project/category/user thành công.

Sau khi xong, liệt kê file đã tạo/sửa và command chạy test.



# ===== 05_PHASE_5_DAILY_REPORTS_ATTACHMENTS.md =====

# PROMPT 05 — Daily Reports + Attachments

---

Hãy xây module Daily Report và Attachment.

## A. Daily report routes

```text
GET  /reports
GET  /projects/<project_id>/reports
GET  /projects/<project_id>/reports/create
POST /projects/<project_id>/reports/create
GET  /reports/<report_id>
GET  /reports/<report_id>/edit
POST /reports/<report_id>/edit
POST /reports/<report_id>/delete
```

Permission:

- SUPER_ADMIN: all.
- VIEWER_ADMIN: read only.
- REPORTER: read/write only assigned project.
- Delete report: SUPER_ADMIN only.

## B. Create/Edit report form

Fields:

- report_date
- overall_status
- highlight
- summary_note optional
- sections dynamic list

Each section:

- report_category_id
- status
- content
- attachments max 3 images

Rules:

- Unique(project_id, report_date). Nếu trùng thì redirect hoặc báo user sửa report hiện có.
- report_category_id phải thuộc project.
- Không cho lặp category trong cùng report.
- Nếu category inactive, không hiện trong create mới nhưng vẫn hiển thị trong report cũ.
- Content required nếu section được thêm.

## C. Attachments

Routes:

```text
GET  /attachments/<id>
POST /attachments/<id>/delete
```

Upload có thể xử lý ngay trong create/edit report form.

Rules:

- Mỗi section tối đa 3 ảnh active.
- Chỉ nhận jpg/jpeg/png/webp.
- Dùng Pillow để verify image.
- Resize ảnh nếu width > 1920.
- Lưu folder:

```text
storage/uploads/projects/project_<id>_<slug>/<yyyy>/<mm>/<dd>/report_<id>/section_<id>/<uuid>.<ext>
```

- Metadata lưu DB.
- Route `/attachments/<id>` phải check quyền xem project trước khi trả file.
- Không expose static upload folder trực tiếp qua Nginx trong MVP.

## D. UI

Report list:

- Filter project/status/date.
- Table report_date, project, status, highlight, created_by, updated_at.

Report detail:

- Header project/date/status.
- Highlight.
- Sections cards.
- Ảnh thumbnail trong từng section, click mở full image route.

Create/edit:

- Form Bootstrap đơn giản.
- Cho thêm/xóa section bằng JavaScript thuần.
- Upload nhiều ảnh.
- Hiển thị ảnh hiện có khi edit và nút delete.

## E. Audit

Ghi audit log cho:

- create report
- update report
- delete report
- upload attachment
- delete attachment

## F. Tests

- Reporter tạo report cho project được gán thành công.
- Reporter không tạo report cho project chưa gán.
- Viewer admin không tạo/sửa được.
- Không tạo trùng project/date.
- Không upload quá 3 ảnh/section.
- Không upload file không phải ảnh.

Sau khi xong, cung cấp command test và hướng dẫn thao tác manual trên UI.



# ===== 06_PHASE_6_DASHBOARD_ISSUES_CHARTS.md =====

# PROMPT 06 — Dashboard, Persistent Issues, Charts

---
Hãy đọc nội dung file Agents.md, sau đó thực hiện 
Hãy xây dashboard và module persistent issues.

## A. Persistent Issues

Routes:

```text
GET  /projects/<project_id>/issues
GET  /projects/<project_id>/issues/create
POST /projects/<project_id>/issues/create
GET  /issues/<id>/edit
POST /issues/<id>/edit
POST /issues/<id>/close
POST /issues/<id>/reopen
```

Fields:

- title
- description
- severity: LOW, MEDIUM, HIGH, CRITICAL
- status: OPEN, PROCESSING, RESOLVED, CLOSED
- opened_date
- due_date
- owner_user_id optional

Permission:

- SUPER_ADMIN: all.
- VIEWER_ADMIN: read only.
- REPORTER: read/write assigned project.

## B. Dashboard tổng `/dashboard`

Filter:

- project_id optional
- from_date
- to_date
- overall_status optional
- reporter optional

Cards:

- total_reports
- good_reports
- processing_reports
- attention_reports
- critical_reports
- open_issues

Charts:

- Pie chart: report count by overall_status.
- Bar chart: report count by date or month.

Tables:

- latest reports.
- open issues.

Permission:

- SUPER_ADMIN và VIEWER_ADMIN xem all.
- REPORTER chỉ thấy dữ liệu project được gán.

## C. Project dashboard `/projects/<project_id>/dashboard`

Hiển thị:

- Project header.
- Danh sách ngày báo cáo bên trái hoặc table đơn giản.
- Cards thống kê.
- Bảng lịch sử báo cáo.
- Issue xuyên suốt đang mở.
- Nút thêm báo cáo mới nếu user có quyền write.

## D. API chart endpoints

Có thể render chart bằng data inline trong template hoặc API JSON. Nếu dùng API:

```text
GET /api/dashboard/status-chart
GET /api/dashboard/report-count-chart
```

Phải filter theo quyền user.

## E. UI

- Bootstrap cards.
- Badge status.
- Chart.js.
- Không cần giao diện quá đẹp.

## F. Tests

- Dashboard của reporter không lộ dữ liệu project chưa gán.
- Viewer admin xem được all nhưng không thấy nút write.
- Counts đúng với dữ liệu seed.

Sau khi làm xong, cung cấp command chạy test và hướng dẫn tạo dữ liệu mẫu để xem chart.



# ===== 07_PHASE_7_AUDIT_SECURITY_BACKUP_DEPLOY.md =====

# PROMPT 07 — Audit, Security, Backup, Deploy

---
Hãy đọc nội dung file Agents.md, sau đó thực hiện: 
Hãy hoàn thiện phần vận hành production cho Flask app.

## A. Audit log

Tạo helper:

```python
log_audit(action, entity_type, entity_id=None, old_values=None, new_values=None)
```

Ghi:

- actor_user_id
- action
- entity_type
- entity_id
- old_values_json
- new_values_json
- ip_address
- user_agent
- created_at

Đảm bảo các thao tác quan trọng đều gọi audit:

- user CRUD
- project CRUD
- assignment
- category CRUD
- report create/update/delete
- attachment upload/delete
- issue create/update/close/reopen

## B. Security hardening

- Đảm bảo production không bật debug.
- `.env.example` đầy đủ nhưng không có secret thật.
- Session cookie Secure/HttpOnly/SameSite.
- CSRF cho form.
- Validate file upload kỹ.
- Không expose upload folder public.
- Route attachment check quyền.
- Add max content length.

## C. Backup scripts

Tạo scripts:

```text
scripts/backup_db.sh
scripts/backup_uploads.sh
scripts/restore_db.sh
```

Yêu cầu:

- Backup PostgreSQL bằng `pg_dump`.
- Backup uploads bằng `tar.gz`.
- Folder backup mặc định `/opt/backups/starx-report`.
- Có timestamp trong file.
- Có hướng dẫn cron hằng ngày.

## D. Production deploy docs

Tạo tài liệu `DEPLOY_UBUNTU.md` gồm:

- Cài packages Ubuntu.
- Tạo user Linux `starxreport`.
- Clone/copy source vào `/opt/starx-report`.
- Tạo venv.
- Cài requirements.
- Tạo PostgreSQL DB/user.
- Tạo `.env`.
- Chạy migration.
- Seed admin.
- Gunicorn systemd service.
- Nginx reverse proxy.
- HTTPS với Certbot.
- Backup cron.
- Cách update code.
- Cách xem logs.

## E. Final smoke test checklist

Tạo checklist:

- login admin
- create user
- create project
- assign reporter
- create category
- login reporter
- create report
- upload images
- view dashboard
- login viewer
- confirm viewer cannot edit
- backup DB/uploads

Sau khi xong, liệt kê file đã tạo/sửa và command deploy chính.



# ===== 08_FULL_BUILD_ONE_SHOT_PROMPT.md =====

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



# ===== 09_QA_AUDIT_PROMPT.md =====

# PROMPT 09 — QA / Code Audit Prompt

Dùng sau khi coding agent đã xây xong MVP.

---

Hãy audit toàn bộ codebase **StarX Project Daily Report System**.

Mục tiêu: tìm lỗi logic, lỗi phân quyền, lỗi upload file, lỗi database constraint, lỗi bảo mật và thiếu sót vận hành.

Kiểm tra bắt buộc:

## 1. Auth & permission

- Route nào cần login nhưng bị public?
- VIEWER_ADMIN có write được ở đâu không?
- REPORTER có xem/sửa được project chưa được assign không?
- Attachment route có check quyền không?
- API chart có filter theo quyền không?

## 2. Database

- Có unique(project_id, report_date) chưa?
- Có unique daily_report_section(daily_report_id, report_category_id) chưa?
- Category có unique(project_id, name) chưa?
- Có soft delete không?
- Query có vô tình lấy deleted rows không?

## 3. Upload ảnh

- Có check extension không?
- Có check MIME thật/Pillow verify không?
- Có giới hạn size không?
- Có giới hạn 3 ảnh/section không?
- Stored filename có UUID không?
- Upload folder có bị public không?
- Có xử lý ảnh lỗi/corrupt không?

## 4. Daily report logic

- Tạo report trùng ngày xử lý đúng không?
- Category thuộc sai project có bị chặn không?
- Inactive category có được xử lý đúng khi edit report cũ không?
- Reporter edit report của project khác có bị chặn không?

## 5. Dashboard

- Count status có đúng không?
- Filter date/project/status có đúng không?
- Reporter dashboard có bị lộ dữ liệu không?

## 6. Security

- `.env` có bị commit không?
- Debug production tắt chưa?
- CSRF có chưa?
- Password hash đúng chưa?
- Error page có lộ stack trace không?

## 7. Deployment

- Gunicorn config ổn chưa?
- Nginx không serve uploads public chưa?
- Backup script có chạy được không?
- README có đủ command không?

Kết quả audit cần trả về:

1. Danh sách lỗi nghiêm trọng cần sửa ngay.
2. Danh sách lỗi trung bình.
3. Danh sách cải tiến sau MVP.
4. Patch cụ thể hoặc hướng dẫn sửa từng file.
5. Test cần thêm để chống regression.
