# RBAC và Custom Roles

## Nguyên tắc

Role chỉ là tập permission. Không viết logic mới dựa trên tên custom role.

Authorization tài nguyên project:

```text
current_user active
AND modules.reports.access
AND current_user.can(action_permission)
AND can_read_project/project scope hiện tại
```

Đối với mutation nhạy cảm, dùng helper quản lý project phù hợp hoặc active membership scope theo thiết kế hiện tại; không chỉ dựa UI.

## Permission catalogue đề xuất

Codex phải kiểm tra registry hiện tại và tái sử dụng code có ý nghĩa tương đương, không tạo duplicate.

### Navigation

```text
reports.today.view
project_operations.view
reports.configuration.view
```

Dashboard: tái sử dụng general permission hiện tại nếu có và bổ sung scope permissions khi thiếu:

```text
dashboards.system.view
dashboards.customer.view
dashboards.project.view
dashboards.contractor.view
```

### Scope

```text
projects.scope_all
```

Permission này cho custom global viewer/manager; SUPER_ADMIN vẫn bypass. User không có scope_all chỉ thấy project qua cơ chế `ProjectUser`/helper hiện tại.

### Customer

```text
customers.view
customers.create
customers.edit
customers.archive
```

### Contractor catalog

```text
project_contractors.view
project_contractors.create
project_contractors.edit
project_contractors.archive
```

### Assignment

```text
contractor_assignments.view
contractor_assignments.manage
contractor_assignments.end
```

### ProjectUpdate

```text
project_updates.view
project_updates.create
project_updates.edit
project_updates.edit_all
project_updates.delete
```

## Default grants đề xuất

| Role mặc định | Quyền Phase 9 |
|---|---|
| SUPER_ADMIN | bypass/all |
| ADMIN | toàn bộ Phase 9, trừ quyền hệ thống đặc biệt theo policy hiện tại |
| VIEWER_ADMIN | view Customer/Contractor/Assignment/Update + all dashboards + `projects.scope_all`, không mutate |
| PROJECT_MANAGER legacy | không dựa tên role; grant theo defaults hiện tại và assigned projects |
| REPORTER legacy | Today, project/report view/create theo defaults hiện tại; không contractor/update mutation mặc định |

DB có custom/legacy roles khác registry defaults. Migration/sync không được reset quyền hiện tại một cách mù quáng.

## Custom role mẫu

### Nhân viên báo cáo

```text
modules.reports.access
reports.today.view
reports.view
reports.create
```

Project scope qua assignment hiện tại.

### Điều phối nhà thầu

```text
modules.reports.access
project_operations.view
project_contractors.view
contractor_assignments.view
contractor_assignments.manage
contractor_assignments.end
project_updates.view
project_updates.create
project_updates.edit
```

### Quản lý cập nhật dự án

```text
modules.reports.access
project_operations.view
project_updates.view
project_updates.create
project_updates.edit_all
```

### Ban điều hành read-only

```text
modules.reports.access
project_operations.view
projects.scope_all
dashboards.system.view
dashboards.customer.view
dashboards.project.view
dashboards.contractor.view
customers.view
project_contractors.view
contractor_assignments.view
project_updates.view
reports.view
issues.view
```

### Quản trị cấu hình báo cáo

```text
modules.reports.access
reports.configuration.view
projects.manage
project_assignments.manage
report_categories.manage
```

## UI/backend rules

- Sidebar item dựa permission.
- Button dựa permission và resource helper.
- Direct URL luôn backend enforce.
- 403 rõ bằng tiếng Việt.
- Unknown permission deny.
- Permission mutation có audit.
