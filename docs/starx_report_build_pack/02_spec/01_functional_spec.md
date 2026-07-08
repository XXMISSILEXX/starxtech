# Functional Specification — StarX Project Daily Report

## 1. Module Authentication

### Chức năng

- Đăng nhập.
- Đăng xuất.
- Đổi mật khẩu.
- Admin reset mật khẩu user.
- Chặn user inactive.

### Quy tắc

- Không có đăng ký tự do.
- User chỉ được tạo bởi Admin tổng.
- Password phải hash bằng Werkzeug hoặc thư viện tương đương.
- Session cookie bật HttpOnly, SameSite, Secure khi production.

## 2. Module User Management

Dành cho Admin tổng.

### Trường user

- Họ tên.
- Username.
- Email.
- Role.
- Active/inactive.
- Password hash.
- Last login.

### Chức năng

- Danh sách user.
- Tạo user.
- Sửa user.
- Khóa/mở user.
- Reset mật khẩu.
- Gán user vào project.

## 3. Module Project Management

Dành cho Admin tổng.

### Trường project

- Code.
- Name.
- Description.
- Status: active, paused, completed, archived.
- Start date.
- Expected end date.
- Created by.

### Chức năng

- Tạo/sửa project.
- Archive project.
- Gán reporter vào project.
- Xem danh sách project.

## 4. Module Report Category

Đầu mục báo cáo theo từng project.

### Ví dụ

- Tiến độ Thi công.
- Nhà thầu phụ.
- Phối hợp BQLDA / CĐT.
- Nhân sự & Tuyển dụng.
- Phần mềm & Công nghệ.
- Hồ sơ Pháp lý.

### Trường dữ liệu

- Project.
- Name.
- Description.
- Icon hoặc emoji.
- Sort order.
- Is active.
- Is required.

### Quy tắc

- Không cho trùng tên category trong cùng project.
- Không xóa cứng category đã có report dùng rồi.
- Khi không dùng nữa thì set inactive.

## 5. Module Daily Report

### Trường báo cáo ngày

- Project.
- Report date.
- Overall status.
- Highlight.
- Summary note.
- Created by.
- Updated by.

### Overall status

- UPDATED: Cập nhật.
- GOOD: Tốt.
- PROCESSING: Đang xử lý.
- ATTENTION: Cần chú ý.
- CRITICAL: Khẩn cấp.

### Quy tắc

- Một project chỉ có một báo cáo trong một ngày.
- Reporter chỉ được tạo/sửa report của project được giao.
- Viewer admin không được tạo/sửa/xóa.
- Điểm nổi bật nên bắt buộc.

## 6. Module Daily Report Section

Mỗi báo cáo có nhiều section, mỗi section gắn với một report category.

### Trường section

- Daily report.
- Report category.
- Status.
- Content.
- Sort order.

### Section status

- INFO: Thông tin.
- GOOD: Tốt.
- PROCESSING: Đang xử lý.
- ATTENTION: Cần chú ý.
- CRITICAL: Khẩn cấp.

### Quy tắc

- Category phải thuộc đúng project của report.
- MVP nên không cho lặp category trong cùng một report.
- Nếu cần nhiều ý, người dùng xuống dòng trong cùng content.

## 7. Module Attachments

### Chức năng

- Upload ảnh vào từng section.
- Hiển thị ảnh trong detail report.
- Xóa ảnh nếu có quyền.

### Quy tắc

- Tối đa 3 ảnh/section.
- Chỉ nhận jpg, jpeg, png, webp.
- Tối đa 5-10MB/ảnh tùy config.
- Dùng UUID làm stored filename.
- Kiểm tra MIME thật bằng Pillow.
- Resize ảnh quá lớn về max width 1600 hoặc 1920 px.
- Ảnh phải được trả qua route `/attachments/<id>` có check quyền.

## 8. Module Persistent Issues

Vấn đề xuyên suốt của project.

### Trường issue

- Project.
- Title.
- Description.
- Severity: LOW, MEDIUM, HIGH, CRITICAL.
- Status: OPEN, PROCESSING, RESOLVED, CLOSED.
- Opened date.
- Due date.
- Closed date.
- Owner.

### Chức năng

- Tạo issue.
- Sửa issue.
- Đóng/reopen issue.
- Hiển thị issue đang mở trên dashboard.

## 9. Module Dashboard

### Dashboard tổng

Dành cho Admin tổng và Admin chỉ xem.

Filter:

- Project.
- From date.
- To date.
- Status.
- Reporter.

Hiển thị:

- Tổng project active.
- Tổng report.
- Ngày tốt.
- Đang xử lý.
- Cần chú ý.
- Khẩn cấp.
- Issue đang mở.
- Pie chart status.
- Bar chart số report theo thời gian.
- Bảng report mới nhất.
- Bảng issue đang mở.

### Dashboard project

Dành cho user có quyền với project.

Hiển thị:

- Project header.
- Bộ lọc ngày.
- Card thống kê.
- Timeline/list ngày báo cáo.
- Bảng lịch sử report.
- Issue xuyên suốt.
- Nút thêm báo cáo nếu có quyền.
