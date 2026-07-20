# Investigation: Relation Management

## Mục tiêu

Đánh giá hiện trạng và đề xuất chính sách vòng đời dữ liệu cho phân hệ Quản lý
đối tác: đối tác, công ty, phòng ban, quan hệ và metadata trường động. Đây là
tài liệu cho phase implement sau, không phải thay đổi runtime.

## Phạm vi

- Model, route, template, service, RBAC/audit và test của Partner Management.
- Chính sách active → archived/inactive → restore, truy vấn và UI.
- Không bao gồm S3, hồ sơ tài liệu, ảnh sự kiện hoặc thay đổi Reports.

## Các báo cáo

- `CURRENT_STATE.md`: phát hiện từ source hiện tại.
- `BUSINESS_POLICY_RECOMMENDATION.md`: chính sách nghiệp vụ khuyến nghị.
- `RBAC_PERMISSION_RECOMMENDATION.md`: quyền và default grants.
- `ROUTE_AND_UI_PLAN.md`: API/UI phase sau.
- `DATA_MODEL_IMPACT.md`: migration, query và backfill dự kiến.
- `TEST_PLAN.md`: automated/manual/regression checks.
- `IMPLEMENTATION_PHASES.md`: kế hoạch triển khai an toàn.
- `OPEN_QUESTIONS.md`: các quyết định cần business owner xác nhận.

## Kết luận ngắn

Source đã có soft-delete/deactivate cho Partner, Company và Relationship, và
`is_active` cho Department. Tuy nhiên list/detail lookup phần lớn chỉ truy
vấn `deleted_at IS NULL`, không có archived/all view hay restore. Khuyến nghị
là chuẩn hóa từ ngữ thành “Lưu trữ”, dùng status filter, thêm restore permission
riêng và không cascade archive Company sang Partner.
