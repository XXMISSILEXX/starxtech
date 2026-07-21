# 04. Naming và grouping permission

## Hiện trạng

Catalogue hiện dùng code hai phần như `modules.company_media.access`, `company_media_files.upload`, `roles.manage`. Đây là nhất quán ở mức resource/action, có `group_name` tiếng Việt cho UI và `is_dangerous` cho badge. Một số legacy resource names khác phong cách (`reports`, `report_attachments`, `partner_fields`) nhưng không cần đổi ngay vì sẽ gây migration/route regression.

## Chuẩn đề xuất cho permission mới

```text
modules.<module>.access
<module>.<resource>.view
<module>.<resource>.create
<module>.<resource>.edit
<module>.<resource>.archive
<module>.<resource>.restore
<module>.<resource>.delete
<module>.<resource>.share
<module>.<resource>.download
<module>.<resource>.upload
```

Catalogue hiện dùng `<resource>.<action>` thay vì ba phần; tiếp tục convention hiện tại cho resource mới trong cùng app (`company_media_files.upload`) để không tạo hai style. Chuẩn ba phần là hướng đặt tên domain rộng hơn, không phải nhiệm vụ migrate Phase 6.1A.

## Archive và delete

UI soft-delete nên ghi **Lưu trữ**. Code hiện dùng `can_delete`/`.delete` cho nhiều route soft-delete; tài liệu/label phải nói rõ đây không phải hard delete. Với permission mới, ưu tiên `.archive`; chỉ dùng `.delete` khi có hard-delete thật. Không rename code hiện tại trong phase này.

## Dangerous permissions

Đánh dấu dangerous cho archive/delete, restore, share, `roles.manage`, `users.manage`, system/admin settings, project assignments và các quyền xuất/nhập dữ liệu nếu có. Restore cũng cần dangerous: nó tái công bố dữ liệu và hiện chưa nhất quán ở catalogue.

## Nhóm UI role permissions đề xuất

1. Phân hệ
2. Quản trị (Users, Roles, Security, System)
3. Dự án và phân công dự án
4. Báo cáo và Vấn đề
5. Hồ sơ dự án
6. Thư viện media
7. Đối tác
8. Cấu hình danh mục/trường dữ liệu

Các điểm mơ hồ cần xử lý ở phase sau: `.delete` nhưng UI archive; action `manage` gom nhiều thao tác; `modules.*.access` không biểu thị quyền đọc resource; `project_documents`/`company_media` là module name trong khi actions dùng `project_document_*`/`company_media_*` resources.

