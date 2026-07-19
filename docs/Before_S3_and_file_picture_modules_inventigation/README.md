# Investigation before S3 and file/picture modules

## Mục tiêu

Đánh giá read-only codebase StarX trước khi mở rộng Mini RBAC, hồ sơ tài liệu dự án, ảnh sự kiện và S3/Object Storage. Báo cáo này không thay đổi runtime, migration, database, Docker, secret hay dữ liệu.

## Phạm vi đã đọc

- Flask blueprints, routes, services, models, migrations, templates và tests.
- Cấu hình upload/security, Docker Compose, Cloudflared và hướng dẫn production.
- Không chạy `flask db`, seed/reset, Docker hay test vì các lệnh đó có thể ghi database/test database.

## Báo cáo con

- `RBAC_EXPANSION_PLAN.md`: Mini RBAC và lộ trình chuyển đổi.
- `CURRENT_ROUTES_AND_PERMISSIONS.md`: route inventory và quyền/rủi ro.
- `S3_FILE_STORAGE_READINESS.md`: storage, tài liệu và ảnh sự kiện.
- `FUTURE_MODULE_PERMISSION_MATRIX.md`: mapping role mặc định.
- `SECURITY_RISK_REVIEW.md`: rủi ro ưu tiên.
- `IMPLEMENTATION_PHASES.md`: rollout, test, deploy và rollback.
- `OPEN_QUESTIONS.md`: quyết định nghiệp vụ cần chốt.

## Kết luận ngắn

Nền tảng hiện có đã có kiểm tra backend theo project cho báo cáo/attachment và CSRF global, nhưng role là chuỗi đơn lẻ (`users.role`) và permission phần lớn hard-code trong `app/auth/permissions.py`, routes/templates. Nên thêm RBAC additive, giữ `users.role` ở phase đầu, rồi áp dụng module-by-module. File mới phải private và đi qua authorization backend; không đưa URL public vào database.
