# Phase 7.2 — Dashboard dung lượng & băng thông

`GET /admin/storage` cho phép người có `storage.dashboard.view` xem estimate metadata. `GET /admin/storage/export.csv` cần thêm `storage.dashboard.export` và chịu giới hạn `RATELIMIT_EXPORT_LIMIT`.

Storage hiện tại là tổng object active chưa soft-delete, derivative chưa soft-delete và ZIP bulk-download thành công còn hạn. Băng thông là tổng `DownloadEvent` trong kỳ (storage/client egress; event legacy dùng `estimated_bytes`). Dashboard không quét S3/Object Storage, không phải số liệu billing và không có cleanup/quota edit.

Deploy:

```bash
flask db upgrade
flask sync-permissions --apply-defaults
```

Smoke test: đăng nhập SUPER_ADMIN/ADMIN/VIEWER_ADMIN, kiểm tra dashboard; chỉ SUPER_ADMIN hoặc role custom được grant export mới thấy/tải CSV. Kiểm tra bộ lọc ngày, module, source type và không có thao tác cleanup.
