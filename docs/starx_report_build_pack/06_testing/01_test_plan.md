# Test Plan — StarX Project Daily Report

## 1. Auth tests

- Login admin đúng password thành công.
- Login sai password thất bại.
- User inactive không login được.
- Logout thành công.
- Change password yêu cầu current password đúng.

## 2. Permission tests

### SUPER_ADMIN

- Tạo user được.
- Tạo project được.
- Tạo category được.
- Gán reporter vào project được.
- Tạo/sửa report mọi project được.

### VIEWER_ADMIN

- Xem dashboard tổng được.
- Xem project dashboard được.
- Xem report detail được.
- Không truy cập được create/edit/delete route.
- Không upload/delete attachment được.

### REPORTER

- Chỉ thấy project được gán.
- Tạo report trong project được gán được.
- Sửa report trong project được gán được.
- Không xem project chưa gán.
- Không tạo report cho project chưa gán.
- Không xem attachment của project chưa gán.

## 3. User management tests

- Tạo user thiếu username bị lỗi.
- Tạo username trùng bị lỗi.
- Tạo email trùng bị lỗi nếu email nhập.
- Reset password thành công.
- Deactivate user xong user không login được.

## 4. Project tests

- Tạo project code trùng bị lỗi.
- Archive project không xóa dữ liệu.
- Gán reporter trùng không tạo duplicate.
- Remove reporter khỏi project thì reporter mất quyền xem project.

## 5. Category tests

- Tạo category thành công.
- Category trùng tên trong cùng project bị lỗi.
- Category cùng tên ở project khác được phép.
- Inactive category không hiện trong create report mới.
- Report cũ dùng inactive category vẫn hiển thị được.

## 6. Daily report tests

- Tạo report thành công.
- Tạo report trùng project/date bị lỗi.
- Tạo report với category sai project bị chặn.
- Tạo report có duplicate category bị lỗi.
- Edit report giữ đúng section.
- Delete report chỉ SUPER_ADMIN được làm.

## 7. Attachment tests

- Upload jpg/png/webp thành công.
- Upload file txt/pdf/exe bị chặn.
- Upload ảnh corrupt bị chặn.
- Upload quá max size bị chặn.
- Upload ảnh thứ 4 trong cùng section bị chặn.
- Stored filename dùng UUID, không dùng filename gốc.
- Attachment route yêu cầu login.
- User không có quyền project không xem được attachment.

## 8. Dashboard tests

- Tổng số report đúng.
- Count theo status đúng.
- Filter project đúng.
- Filter date đúng.
- Reporter dashboard không lộ project khác.
- Pie/bar chart data đúng.

## 9. Issue tests

- Tạo issue thành công.
- Sửa issue thành công.
- Close issue set status/closed_date đúng.
- Reopen issue clear hoặc cập nhật closed_date hợp lý.
- Viewer admin không tạo/sửa issue được.

## 10. Smoke test trước production

1. Login admin.
2. Tạo reporter.
3. Tạo viewer admin.
4. Tạo project ABHL.
5. Tạo categories:
   - Tiến độ Thi công
   - Nhà thầu phụ
   - Phối hợp BQLDA / CĐT
   - Nhân sự & Tuyển dụng
   - Phần mềm & Công nghệ
   - Hồ sơ Pháp lý
6. Gán reporter vào ABHL.
7. Login reporter.
8. Tạo report hôm nay.
9. Thêm 3 section.
10. Upload 3 ảnh cho 1 section.
11. Xem dashboard project.
12. Tạo issue xuyên suốt.
13. Login viewer admin.
14. Xác nhận xem được nhưng không sửa được.
15. Chạy backup DB/uploads.
