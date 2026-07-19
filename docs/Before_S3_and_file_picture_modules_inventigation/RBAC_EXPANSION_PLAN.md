# Mini RBAC expansion plan

## Hiện trạng

- `User.role` là `String(50)`, có check constraint; enum ở `app/models/enums.py`: `SUPER_ADMIN`, `ADMIN`, `VIEWER_ADMIN`, `PROJECT_MANAGER`, `REPORTER`. Không có `READONLY_ADMIN`; đây nên là alias/migration mapping được quyết định rõ, không tự thêm lặng lẽ.
- Quy tắc nằm tập trung một phần trong `app/auth/permissions.py`, nhưng còn lặp tại `app/admin/routes.py`, services dashboard/report và Jinja.
- `ProjectUser` là scope project hiện hữu; `role_in_project` tồn tại nhưng authorization hiện không đọc cột này.
- `SUPER_ADMIN` hiện không thật sự “all access” theo tên: một số helper gộp với `ADMIN`, một số write chỉ `SUPER_ADMIN`; cần registry minh bạch.

## Kiến trúc đề xuất, giữ đơn giản

Thêm ba bảng additive:

| Bảng | Cột chính |
|---|---|
| `roles` | `id`, `code` unique, `name`, `description`, `is_system`, `sort_order`, timestamps |
| `permissions` | `id`, `code` unique, `module`, `group_name`, `name`, `description`, `action`, `resource`, `is_dangerous`, `sort_order`, timestamps; thêm `is_deprecated` nullable/default false nếu cần |
| `role_permissions` | `role_id`, `permission_id`, `created_at`, unique `(role_id, permission_id)` |

Giữ `users.role` string. `Role.code` map trực tiếp vào giá trị đó. Không thêm `users.role_id` ở Phase A. `current_user.can(code)` tìm `Role.code == current_user.role`, với bypass `SUPER_ADMIN` chỉ khi user active/authenticated. Permission thiếu hoặc role không tồn tại: deny.

### Scope

Dùng permission cho **action/module**, domain helper cho resource scope. Ví dụ `reports.edit` + `can_edit_report(user, report)` kiểm tra project assignment/own. Không tạo hàng loạt code `reports.edit_own`, `reports.edit_project`, `reports.edit_all` ngay bây giờ. Nếu sau này một action cần scope khác nhau theo role, thêm một `scope` tối giản vào `role_permissions` (`own|project|department|all`) hoặc policy mapping; không nhân đôi toàn bộ permission code.

## Permission registry và sync

Tạo `app/permissions/registry.py` (hoặc `app/auth/permission_registry.py`) chứa immutable definitions theo từng module. Mỗi definition có code, module, group, label, description, action/resource, dangerous, sort order, deprecated. Module mới export list rồi registry tổng hợp.

CLI tương lai: `flask sync-permissions`.

- Upsert theo `permissions.code`; cập nhật metadata an toàn.
- Tạo role system nếu chưa có và seed mapping mặc định bằng explicit option, ví dụ `--apply-defaults`.
- Không tự xóa permission/role permission cũ; đánh dấu deprecated và báo cáo orphan.
- Chạy trong production sau deploy code/migration: `docker compose exec web flask sync-permissions` (không chạy ở investigation này). Ghi command vào runbook, chạy một lần có backup/approval.

## API đề xuất

```python
current_user.can("partners.view")
user_has_permission(user, "partners.view")
@permission_required("partners.manage")
@any_permission_required("documents.view", "documents.view_project")
@all_permissions_required("documents.view", "documents.download")
```

Decorator deny anonymous/inactive/unknown permission bằng 403 tiếng Việt. Cache tập permission trên `flask.g` theo request, không cache cross-request cho đến khi có invalidation rõ ràng. Domain helper vẫn chịu trách nhiệm scope:

`can_access_module`, `can_edit_report`, `can_delete_report`, `can_view_project_document`, `can_download_object`, `can_manage_partner`.

## Default mapping đề xuất

- `SUPER_ADMIN`: bypass, toàn quyền; hạn chế ai được gán role này và bảo vệ super-admin cuối cùng.
- `READONLY_ADMIN` (quyết định alias với `VIEWER_ADMIN`): chỉ `*.view`, dashboard, metadata; không create/edit/delete/manage. Download phải tick riêng.
- `ADMIN`: nghiệp vụ all-scope được cấp; `users.manage` chỉ nếu doanh nghiệp muốn. `roles.manage` mặc định chỉ SUPER_ADMIN.
- `PROJECT_MANAGER`: report/issue theo project được gán; có thể `partners.view` nếu tick; không partner write mặc định.
- `REPORTER`: xem/tạo/sửa report theo quyền+project, không đối tác mặc định; own/project rule cần chốt.

## Admin UI

Thêm `Quản trị hệ thống → Vai trò & phân quyền`: danh sách role, detail grouped theo `module/group_name`, checkbox, badge `is_dangerous`, Lưu, Khôi phục mặc định, Chọn tất cả quyền xem, Bỏ chọn. Backend phải block role system ngoài policy, tự hạ quyền của chính mình nếu cần, và mọi thao tác khiến không còn active `SUPER_ADMIN`. Audit `role_permission.grant/revoke/reset` với actor, target role, permission delta.

## Strategy chuyển đổi

1. Migration roles/permissions/role_permissions + registry/CLI + tests; giữ helpers cũ làm adapter.
2. Khóa module selection và partner routes theo permission; thay Jinja bằng `current_user.can`.
3. Chuyển report/issues/attachments, vẫn giữ `ProjectUser` scope.
4. Module documents/event photos được viết từ đầu với registry+scope; S3 sau cùng.
5. Chỉ sau khi ổn định mới cân nhắc `users.role_id`; không cần cho MVP.
