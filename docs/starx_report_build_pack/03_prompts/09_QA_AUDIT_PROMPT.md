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
