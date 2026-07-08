# PROMPT 02 — Models, Migrations, Seed Admin

---

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
