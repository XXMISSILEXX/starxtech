# StarX Project Daily Report System — Build Pack

Gói tài liệu này dùng để xây dựng hệ thống báo cáo tiến độ dự án độc lập, đơn giản, không liên quan ERP/FSM/Starlink app hoặc bất kỳ hệ thống khác.

## Mục tiêu

Xây hệ thống web nội bộ để:

- Admin tổng tạo user, tạo dự án, tạo đầu mục báo cáo cho từng dự án.
- Admin chỉ xem xem toàn bộ hệ thống nhưng không chỉnh sửa.
- Người báo cáo/quản lý dự án tạo và sửa báo cáo ngày cho dự án được phân quyền.
- Báo cáo ngày có nhiều đầu mục; mỗi đầu mục có nội dung, trạng thái và tối đa 3 ảnh đính kèm.
- Có dashboard tổng, dashboard theo dự án, lịch sử báo cáo, vấn đề xuyên suốt và biểu đồ.

## Công nghệ khuyến nghị

- Python 3.12
- Flask full-stack: Jinja + Bootstrap 5 + Chart.js
- PostgreSQL
- SQLAlchemy + Flask-Migrate/Alembic
- Flask-Login
- Pillow cho xử lý ảnh
- Gunicorn + Nginx khi deploy production

## Cách dùng gói này

1. Đọc `01_analysis/01_project_analysis.md` để nắm mục tiêu và phạm vi.
2. Đọc `02_spec/01_functional_spec.md` và `02_spec/02_database_schema.md` để nắm thiết kế.
3. Dùng các prompt trong `03_prompts/` để copy & paste vào Codex/AI coding agent theo từng phase.
4. Dùng `04_setup/01_local_setup_ubuntu.md` để chạy local.
5. Dùng `05_deployment/01_production_deploy_ubuntu.md` để deploy production.
6. Dùng `06_testing/01_test_plan.md` để test hệ thống trước khi dùng thật.

## Cách triển khai an toàn

Làm theo thứ tự:

1. Backend/app foundation.
2. Auth + role.
3. User/project/category.
4. Daily report.
5. Upload ảnh.
6. Dashboard + issue.
7. Audit + backup + deploy.

Không nên làm React/mobile/S3/notification ngay ở MVP. Hệ thống nên bắt đầu boring, chắc, dễ backup.
