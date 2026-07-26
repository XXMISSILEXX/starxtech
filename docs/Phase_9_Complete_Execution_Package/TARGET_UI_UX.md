# UI/UX mục tiêu

## Reports sidebar

```text
Hôm nay
Quản lý dự án & nhà thầu
Dashboard quản trị
Cấu hình
```

## Hôm nay

Nhóm theo Customer, nhưng query phải là project user được phép xem.

```text
Geleximco
  ✓ An Bình Homeland — Đã nộp 17:30
  ! XY Land — Chưa nộp

Khách hàng chưa phân loại
  ! Dự án cũ — Chưa nộp
```

Click:

- chưa report hôm nay → create;
- đã report → detail;
- edit action nếu có quyền.

User không có project thấy empty state, không 403 ở trang danh sách.

## Quản lý dự án & nhà thầu

Accordion Customer, mặc định mở tối đa một Customer.

Project row:

```text
An Bình Homeland
Đang chạy · Đã nộp hôm nay · 2 thi công · 3 giải pháp
[Báo cáo ngày] [Đối tác thi công] [Đối tác giải pháp] [⋮]
```

- Tên Customer → Customer Dashboard.
- Tên Project → Project Workspace/Dashboard.
- Ba action cùng visual priority.
- Search Customer/Project tự mở accordion.
- Mobile không ép ba button một hàng.

## Contractor role page

```text
Đối tác giải pháp — An Bình Homeland
[VTS] Active · cập nhật gần nhất 26/07
[ZTSS] Paused · cập nhật gần nhất 22/07
```

Actions permission-aware:

```text
Xem cập nhật
Thêm cập nhật
Sửa assignment
Kết thúc
```

## Project Workspace

Tabs:

```text
Tổng quan
Báo cáo ngày
Báo cáo xuyên suốt
Vấn đề tồn đọng
Đối tác thi công
Đối tác giải pháp
```

## Báo cáo xuyên suốt

Timeline `ProjectUpdate`:

```text
26/07 — VTS · Giải pháp · Bàn giao
Đã bàn giao hoàn thành 2 hạng mục.

25/07 — Cập nhật chung
Chủ đầu tư xác nhận lịch nghiệm thu.
```

Filters:

- update type;
- contractor;
- role;
- date range.

Form cập nhật contractor khóa project/contractor/role theo assignment URL, tránh chọn nhầm.

## Cấu hình

Hub tái sử dụng trang hiện tại:

- Projects.
- Project assignments.
- Report categories theo project.
- Roles/permissions.
- Customer/contractor catalog khi có quyền.

Không xây lại toàn bộ admin UI.
