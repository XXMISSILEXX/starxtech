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
