# Phân tích hệ thống StarX Project Daily Report

## 1. Bối cảnh

Hệ thống cần xây là một dashboard báo cáo tiến độ dự án nội bộ, lấy cảm hứng từ dashboard HTML/Netlify hiện có. Hệ thống mới sẽ độc lập hoàn toàn, có database PostgreSQL, đăng nhập, phân quyền, tạo dự án, tạo báo cáo ngày, đính kèm ảnh và dashboard tổng hợp.

Mục tiêu không phải xây ERP, FSM hay phần mềm quản lý dự án lớn. Mục tiêu là xây một hệ thống báo cáo ngày dùng được thật, đơn giản, dễ vận hành.

## 2. Người dùng chính

### Admin tổng

Toàn quyền hệ thống:

- Tạo/sửa/khóa user.
- Tạo/sửa/khóa project.
- Tạo đầu mục báo cáo cho từng project.
- Gán người báo cáo vào project.
- Xem toàn bộ dashboard.
- Tạo/sửa báo cáo như người báo cáo.
- Quản lý vấn đề xuyên suốt.

### Admin chỉ xem

Quyền chỉ đọc:

- Xem toàn bộ project.
- Xem toàn bộ dashboard.
- Xem lịch sử báo cáo.
- Xem vấn đề xuyên suốt.
- Không được tạo, sửa, xóa dữ liệu.

### Người báo cáo / quản lý dự án

Quyền theo project được phân công:

- Chỉ xem project được giao.
- Tạo báo cáo ngày cho project được giao.
- Sửa báo cáo ngày của project được giao.
- Thêm nội dung theo các đầu mục admin đã tạo.
- Upload tối đa 3 ảnh cho mỗi đầu mục.
- Tạo/sửa/đóng vấn đề xuyên suốt trong project được giao nếu được bật quyền.

## 3. Dữ liệu chính

- User
- Project
- Project user assignment
- Report category / đầu mục báo cáo
- Daily report / báo cáo ngày
- Daily report section / nội dung từng đầu mục
- Attachment / ảnh đính kèm
- Persistent issue / vấn đề xuyên suốt
- Audit log

## 4. Phạm vi MVP

Có trong MVP:

- Login/logout.
- 3 role: Admin tổng, Admin chỉ xem, Reporter.
- PostgreSQL.
- Admin tạo user/project/category.
- Reporter tạo/sửa báo cáo ngày.
- Mỗi report có nhiều đầu mục.
- Mỗi đầu mục có tối đa 3 ảnh.
- Lưu ảnh local server theo project/ngày/report/section.
- Dashboard tổng và dashboard project.
- Lịch sử báo cáo.
- Vấn đề xuyên suốt.
- Chart.js cơ bản.

Chưa làm trong MVP:

- Mobile app.
- React/Vue frontend riêng.
- S3/MinIO.
- Notification Zalo/Telegram/Email.
- Workflow duyệt báo cáo.
- Export PDF phức tạp.
- Comment/mention.
- Real-time update.

## 5. Nguyên tắc thiết kế

- Boring nhưng chắc.
- Backend phải check quyền, không chỉ ẩn nút frontend.
- Một project chỉ có một báo cáo cho một ngày.
- Không xóa cứng dữ liệu quan trọng; dùng soft delete nếu có thể.
- Ảnh không public trực tiếp; phục vụ qua route có kiểm tra quyền.
- `.env` không commit Git.
- Có backup database và folder upload.

## 6. Kết luận

Hệ thống nên được xây như một Flask full-stack app: Jinja + Bootstrap + Chart.js + PostgreSQL. Đây là kiến trúc đơn giản, ít moving parts, phù hợp làm một mình, dễ deploy trên Ubuntu server và có thể nâng cấp dần sau này.
