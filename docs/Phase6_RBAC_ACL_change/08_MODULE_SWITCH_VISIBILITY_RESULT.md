# 08. Kết quả Module Switch Visibility — Phase 6.1B

## Vấn đề trước khi sửa

Sidebar chỉ hiển thị **Đổi phân hệ** khi user đồng thời có Reports và Partners access. `/modules/` tự render cards bằng các boolean rời rạc. Company Media guard yêu cầu module access, nên user chỉ có album ACL không có lối navigation hay direct access usable.

## Helper cuối cùng

`app.modules.services.get_accessible_modules(user)` trả card có `key`, label tiếng Việt, description, icon, URL và `reason` (`role_access` hoặc `scoped_acl`). `/modules/` dùng helper này; không coi Users/Roles/Admin là module cards.

Policy hiện thực:

- Reports/Partners/Documents tiếp tục theo module access hiện có; Documents không đổi scoped policy trong phase này.
- Company Media visible khi có module access, active direct/role album ACL, hoặc thuộc SUPER_ADMIN/ADMIN/VIEWER_ADMIN.
- Sidebar desktop/mobile luôn có entry **Đổi phân hệ** cho authenticated user.
- Danh sách rỗng hiển thị: “Bạn chưa được cấp quyền truy cập phân hệ nào. Vui lòng liên hệ quản trị viên.”

## Company Media role/ACL policy

`company_media.permissions.access()` cho phép module guard nếu có global access **hoặc** active album ACL. `view_album()`/file helpers đánh giá theo action:

- Global module + album view: thấy album non-restricted.
- Direct/role `can_view`: thấy và mở đúng album shared, kể cả không có global module access.
- Direct/role `can_download`: download file; `can_view` chỉ cho preview, không tự download.
- Direct/role ACL không làm lộ album khác; index duyệt mỗi album một lần nên không duplicate.
- ADMIN/SUPER_ADMIN bypass theo RBAC; VIEWER_ADMIN read/download restricted read-only theo policy đã chốt.
- Empty Company Media index: “Bạn chưa có album nào được cấp quyền truy cập.”

## Manual smoke test

1. User có global media + albums.view: thấy card, thấy non-restricted albums, preview/download theo action grants.
2. User chỉ có direct hoặc role ACL `can_view`: sidebar có Đổi phân hệ, module switch có Company Media, index chỉ có shared album và detail/preview được.
3. Thêm `can_download`: signed download được; chỉ `can_view` trả 403 ở download endpoint.
4. User không global access, không ACL: không có media card và `/company-media/` trả 403.
5. VIEWER_ADMIN thấy module/restricted albums read-only, không thấy action mutate.

## Không làm trong Phase 6.1B

- Không thêm role/default grants, per-user global permission, migration, ZIP download hay storage namespace.
- Không thêm file-level ACL.
- Không thay đổi Project Documents, nghiệp vụ Daily Reports/ReportAttachment hoặc Partner Management.
