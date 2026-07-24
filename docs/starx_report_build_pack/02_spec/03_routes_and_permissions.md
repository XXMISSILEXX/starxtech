# Routes and Permissions

## 1. Auth

```text
GET  /login
POST /login
POST /logout
GET  /change-password
POST /change-password
```

## 2. Dashboard

```text
GET /reports/dashboard
GET /reports/projects/<project_id>/dashboard
GET /api/reports/dashboard/status-chart
GET /api/reports/dashboard/report-count-chart
```

Permission:

- SUPER_ADMIN: all.
- VIEWER_ADMIN: all read.
- REPORTER: only assigned projects.

## 3. Admin users

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

Permission: SUPER_ADMIN only.

## 4. Admin projects

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

Permission: SUPER_ADMIN only.

## 5. Categories

```text
GET  /admin/projects/<project_id>/categories
POST /admin/projects/<project_id>/categories/create
POST /admin/categories/<id>/edit
POST /admin/categories/<id>/deactivate
POST /admin/categories/<id>/activate
```

Permission: SUPER_ADMIN only.

## 6. Reports

```text
GET  /reports
GET  /reports/projects/<project_id>/reports
GET  /reports/projects/<project_id>/reports/create
POST /reports/projects/<project_id>/reports/create
GET  /reports/<report_id>
GET  /reports/<report_id>/edit
POST /reports/<report_id>/edit
POST /reports/<report_id>/delete
```

Permission:

- Read: SUPER_ADMIN, VIEWER_ADMIN, assigned REPORTER.
- Create/edit: SUPER_ADMIN, assigned REPORTER.
- Delete: SUPER_ADMIN only in MVP.

## 7. Attachments

```text
GET  /attachments/<id>
POST /sections/<section_id>/attachments/upload
POST /attachments/<id>/delete
```

Permission:

- View: user must have project access.
- Upload/delete: SUPER_ADMIN or assigned REPORTER.
- VIEWER_ADMIN cannot upload/delete.

## 8. Issues

```text
GET  /reports/issues
GET  /reports/projects/<project_id>/issues
POST /reports/projects/<project_id>/issues/create
GET  /reports/issues/<id>/edit
POST /reports/issues/<id>/edit
POST /reports/issues/<id>/close
POST /reports/issues/<id>/reopen
```

Permission:

- Read: SUPER_ADMIN, VIEWER_ADMIN, assigned REPORTER.
- Write: SUPER_ADMIN, assigned REPORTER.

## 9. Permission helpers cần viết

- `role_required(*roles)`
- `project_read_required(project_id)`
- `project_write_required(project_id)`
- `report_read_required(report_id)`
- `report_write_required(report_id)`

Rule quan trọng:

```text
SUPER_ADMIN: read/write all
VIEWER_ADMIN: read all, write none
REPORTER: read/write only assigned project
```
