# 01. Hiện trạng RBAC và ACL

## Kết luận ngắn

StarX hiện dùng **RBAC một vai trò trên mỗi user** làm quyền nền, sau đó áp dụng scope theo dự án và ACL allow-only cho Folder/Album. Đây là nền tảng hợp lý cho MVP: quyền route không chỉ dựa vào UI và tài nguyên private vẫn được kiểm tra ở backend.

```text
User --(role_id)--> Role --(RolePermission)--> Permission code
  |                                      |
  +-- ProjectUser --> scope dự án --------+
  +-- user ACL ----> Folder/Album <---- role ACL
                         |
                         +--> File/Media kế thừa quyền container
```

Một request hợp lệ thông thường cần qua nhiều lớp: authenticated + active, `modules.<module>.access`, action permission, scope dự án (nếu có), và ACL khi tài nguyên bị hạn chế.

## Models và quan hệ

| Thành phần | Vai trò hiện tại |
| --- | --- |
| `users` / `User` | Có `role_id`; cột `role`/`legacy_role` còn tạm thời để tương thích. Một user hiện có một role. |
| `roles` / `Role` | Role hệ thống, `code` unique, name/description. Quan hệ 1-n với User. |
| `permissions` / `Permission` | Catalogue version-controlled: code, module/resource, action, group UI, dangerous flag. |
| `role_permissions` / `RolePermission` | Join table role-permission unique theo `(role_id, permission_id)`. |
| `project_users` / `ProjectUser` | Phân công user-project; là scope nghiệp vụ cho REPORTER/PROJECT_MANAGER. |
| `project_document_folder_permissions` | ACL user/role trên folder, principal XOR, unique theo folder+principal; flags view/upload/edit/delete/share. |
| `company_media_album_permissions` | ACL user/role trên album, cùng mô hình XOR/unique; flags view/download/upload/edit/delete/share. |

## Helpers và enforcement đã rà soát

- `User.can(code)` gọi `permissions.services.user_has_permission`.
- `user_has_permission` từ chối user inactive/anonymous, SUPER_ADMIN bypass, còn lại lấy quyền của **một** `role_id`; cache theo request trong `flask.g`; unknown code bị deny và ghi warning.
- `permission_required`, `any_permission_required`, `all_permissions_required` bảo vệ route bằng permission code.
- `app.auth.permissions` có module checks, role helpers và project-scope helpers. `ADMIN_ROLES` là SUPER_ADMIN/ADMIN; REPORTER/PROJECT_MANAGER phải có `ProjectUser` cho scope dự án.
- Project Documents: `app.project_documents.permissions` kết hợp module access, action code, project scope và ACL.
- Company Media: `app.company_media.permissions` kết hợp module access, action code và album ACL.

## Role hệ thống hiện có

| Role | Ý nghĩa hiện tại |
| --- | --- |
| `SUPER_ADMIN` | Bypass `current_user.can`; quyền DB role không mang ý nghĩa vận hành. |
| `ADMIN` | Default nhận hầu hết permission catalogue, trừ roles view/manage và system settings. |
| `VIEWER_ADMIN` | Default read-only; là global read đối với project documents; theo policy hiện hành đọc/download Company Media kể cả album restricted nhưng không mutate. |
| `PROJECT_MANAGER` | Quyền báo cáo/vấn đề và scope theo project assignment; một số quyền documents mặc định. |
| `REPORTER` | Báo cáo của mình/scope project assignment; quyền documents giới hạn. |

## Permission registry và UI role

`app.permissions.registry.PERMISSIONS` là nguồn catalogue; `sync_registry` upsert roles/permission rows. `sync-permissions --apply-defaults` chỉ bổ sung grants thiếu; `--reset-defaults` thay toàn bộ quyền role bằng `DEFAULTS`. Route `/admin/roles/<id>/permissions` nhóm theo `Permission.group_name`, gắn badge **Nguy hiểm**, audit save/reset và khóa chỉnh SUPER_ADMIN. `roles.view` cho xem, `roles.manage` cho ghi.

Group hiện có bao gồm Báo cáo ngày, tệp/ảnh báo cáo, Vấn đề, Dự án, Đầu mục, Đối tác và các thành phần đối tác, Users, Roles, Security/System, Project assignments, Hồ sơ tài liệu dự án và Company Media.

## Module access và module switch hiện tại

Các code `modules.reports.access`, `modules.partners.access`, `modules.project_documents.access`, `modules.company_media.access` là cổng phân hệ. `permitted_modules()` và `/modules` hiện chỉ kiểm tra các code này. Base sidebar chỉ hiện “Đổi phân hệ” khi đồng thời có reports và partners access; Project Documents có link riêng; Company Media chưa có một active-module/sidebar policy tương xứng. Direct URL vẫn được routes/module guards kiểm tra.

## ACL Project Documents

- ACL là folder-level, allow-only, user hoặc role.
- `_restriction_anchor` tìm folder hạn chế gần nhất; ACL của anchor áp dụng cho toàn bộ subtree.
- File kế thừa quyền folder; **không có file-level ACL**.
- ADMIN/SUPER_ADMIN bypass. VIEWER_ADMIN bypass ACL xem folder/file restricted; scope project read global nhưng write không được default grants.
- Với user thường, RBAC + project assignment + matching ACL flag đều cần khi có restriction.

## ACL Company Media

- ACL là album-level, allow-only, user hoặc role.
- Media kế thừa quyền album; **không có media/file-level ACL**.
- ADMIN/SUPER_ADMIN bypass restricted album theo action và RBAC còn quyết định action route.
- VIEWER_ADMIN theo policy hiện hành bypass ACL cho `view` và `download` (preview dùng view), nhưng backend chặn action ghi.
- User thường cần module access, action code và matching album ACL khi album restricted.

## Điểm mạnh

1. Permission catalogue và defaults nằm trong code, sync explicit, không tự mutate DB lúc boot.
2. Route checks có backend enforcement; UI không phải lớp bảo mật duy nhất.
3. ACL có XOR/unique constraints, không có deny conflict và không tạo duplicate principal.
4. Scope project, document ACL và media ACL tách đúng loại resource.
5. Role permission UI đã có nhóm, dangerous marker và audit thay đổi.

## Điểm yếu/rủi ro và chỗ dễ nhầm

| Chủ đề | Rủi ro/giải thích |
| --- | --- |
| Module access vs action | Có `modules.company_media.access` chưa đồng nghĩa có `albums.view`, `files.download` hay resource ACL. |
| Role permission vs ACL | ACL không tự cấp global action permission; một ACL upload chỉ có hiệu lực nếu role cũng có upload RBAC. |
| Restricted semantics | Folder dùng ancestor restricted gần nhất; Album chỉ có chính album. Tài liệu vận hành phải nói rõ khác biệt này. |
| Share và module switch | ACL share hiện không tự làm card/sidebar hiện nếu user thiếu module access; đây là UX/policy gap cho phase 6.1B. |
| VIEWER_ADMIN | Quy tắc global read khác giữa module cần được ghi rõ; Company Media đã chốt read/download restricted, Documents read restricted. |
| Single role | Một người kiêm nhiều nhiệm vụ phải chọn một role hoặc dùng scoped ACL; đây là tín hiệu để cân nhắc multi-role sau này. |
| Delete naming | Nhiều code dùng `delete` trong khi UI soft-delete ghi “Lưu trữ”; dễ hiểu sai mức độ phá hủy. |

