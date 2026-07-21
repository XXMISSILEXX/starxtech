# 05. Module switch và access policy

## Policy đề xuất

- Màn **Đổi phân hệ** luôn hiện với user đã authenticated.
- Mỗi card module chỉ hiện khi user có module access **hoặc** có scoped ACL/resource access mà backend có thể xác định an toàn.
- Direct URL luôn được backend enforce; card/sidebar không phải authorization.
- User có module access nhưng chưa thấy resource nhận empty state rõ ràng, không phải 403 mơ hồ.

## Policy theo module

| Module | Card hiển thị khi | Nội dung hiển thị |
| --- | --- | --- |
| Company Media | `modules.company_media.access` hoặc được share album theo ACL (sau khi có helper accessible albums) | Có `albums.view` thấy album không restricted; chỉ có ACL thấy đúng album được share. |
| Project Documents | `modules.project_documents.access` hoặc scoped folder/project access khi hệ thống hỗ trợ discovery an toàn | Chỉ project/folder user được truy cập. |
| Partner | `modules.partners.access` | Chỉ resource có action view. |
| Daily Reports | `modules.reports.access` hoặc action/scope report tương ứng | Chỉ project/report trong scope. |

## Kết quả Phase 6.1B

`app.modules.services.get_accessible_modules(user)` hiện là nguồn card tập trung. Sidebar desktop/mobile luôn hiển thị **Đổi phân hệ** cho mọi authenticated user; `/modules/` cũng luôn render và trả empty state khi danh sách rỗng. Company Media dùng `company_media.permissions.access(user)`: global module access, ADMIN/SUPER_ADMIN/VIEWER_ADMIN, hoặc ACL active trên album đều làm module discoverable.

Company Media shared-only là một ngoại lệ scoped có chủ đích: ACL matching theo flag cho phép resource action tương ứng mà không cần global module/action grant. Index vẫn liệt kê bằng `view_album`, vì vậy danh sách tự là union không duplicate giữa global non-restricted view và direct/role ACL. Project Documents không thay policy trong phase này.

## Empty states

Ví dụ: “Bạn có quyền vào Hồ sơ dự án nhưng chưa được phân công hoặc chia sẻ folder nào.”, “Bạn có quyền Media nhưng chưa có album phù hợp.” Không nên tự suy diễn rằng không có resource là không có module.
