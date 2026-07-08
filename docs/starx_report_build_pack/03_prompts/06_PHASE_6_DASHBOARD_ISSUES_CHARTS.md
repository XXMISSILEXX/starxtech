# PROMPT 06 — Dashboard, Persistent Issues, Charts

---

Hãy xây dashboard và module persistent issues.

## A. Persistent Issues

Routes:

```text
GET  /projects/<project_id>/issues
GET  /projects/<project_id>/issues/create
POST /projects/<project_id>/issues/create
GET  /issues/<id>/edit
POST /issues/<id>/edit
POST /issues/<id>/close
POST /issues/<id>/reopen
```

Fields:

- title
- description
- severity: LOW, MEDIUM, HIGH, CRITICAL
- status: OPEN, PROCESSING, RESOLVED, CLOSED
- opened_date
- due_date
- owner_user_id optional

Permission:

- SUPER_ADMIN: all.
- VIEWER_ADMIN: read only.
- REPORTER: read/write assigned project.

## B. Dashboard tổng `/dashboard`

Filter:

- project_id optional
- from_date
- to_date
- overall_status optional
- reporter optional

Cards:

- total_reports
- good_reports
- processing_reports
- attention_reports
- critical_reports
- open_issues

Charts:

- Pie chart: report count by overall_status.
- Bar chart: report count by date or month.

Tables:

- latest reports.
- open issues.

Permission:

- SUPER_ADMIN và VIEWER_ADMIN xem all.
- REPORTER chỉ thấy dữ liệu project được gán.

## C. Project dashboard `/projects/<project_id>/dashboard`

Hiển thị:

- Project header.
- Danh sách ngày báo cáo bên trái hoặc table đơn giản.
- Cards thống kê.
- Bảng lịch sử báo cáo.
- Issue xuyên suốt đang mở.
- Nút thêm báo cáo mới nếu user có quyền write.

## D. API chart endpoints

Có thể render chart bằng data inline trong template hoặc API JSON. Nếu dùng API:

```text
GET /api/dashboard/status-chart
GET /api/dashboard/report-count-chart
```

Phải filter theo quyền user.

## E. UI

- Bootstrap cards.
- Badge status.
- Chart.js.
- Không cần giao diện quá đẹp.

## F. Tests

- Dashboard của reporter không lộ dữ liệu project chưa gán.
- Viewer admin xem được all nhưng không thấy nút write.
- Counts đúng với dữ liệu seed.

Sau khi làm xong, cung cấp command chạy test và hướng dẫn tạo dữ liệu mẫu để xem chart.
