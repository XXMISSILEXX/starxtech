# Kế hoạch xây dựng 2 module S3 + Redis/Celery

## Mục tiêu

Xây dựng 2 module mới, độc lập với các module hiện có:

1. **Quản lý tài liệu/hồ sơ dự án**
   - Folder cây nhiều cấp.
   - Tạo/đổi tên/di chuyển/lưu trữ/khôi phục folder.
   - Upload nhiều loại file: tài liệu, ảnh, video, âm thanh.
   - Drag/drop và bulk upload nhiều file cùng lúc.
   - Phân quyền theo folder/role/user.
   - Xem ảnh/video qua thumbnail, preview, lightbox và signed URL.

2. **Thư viện ảnh/video công ty**
   - Album cấp ngoài duy nhất.
   - Trong album chứa ảnh/video trực tiếp.
   - Không có folder con.
   - Drag/drop và bulk upload nhiều ảnh/video.
   - Phân quyền theo album/role/user.
   - Gallery/lightbox, cover, thumbnail/poster.

## Nguyên tắc không ảnh hưởng module cũ

- **Không chuyển ReportAttachment/Báo cáo hàng ngày sang S3.**
- **Không thay đổi upload ảnh báo cáo hiện tại.**
- **Không thay đổi module Quản lý đối tác/Quan hệ đối tác.**
- 2 module mới dùng S3/Object Storage riêng qua `StorageObject`.
- Existing reports vẫn local filesystem cho tới khi có phase migration riêng được phê duyệt.

## Kết luận kiến trúc

- Browser upload trực tiếp lên S3 bằng signed URL.
- Flask chỉ quản lý xác thực, RBAC/ACL, metadata, presign, complete upload và signed download.
- Redis + Celery xử lý background jobs.
- PostgreSQL là source of truth cho metadata, batch, job và derivative.
- Celery worker tạo thumbnail/preview/poster, không xử lý file trong web process.
- Object key dùng UUID, không chứa tên folder/project/album/filename.
- Bucket private, không public object.
- Không lưu signed URL trong DB/log/audit.

## Danh sách tài liệu trong zip

1. `01_EXECUTIVE_SUMMARY.md`
2. `02_TARGET_ARCHITECTURE.md`
3. `03_KEY_DECISIONS.md`
4. `04_DATA_MODEL_DETAILED.md`
5. `05_RBAC_ACL_DESIGN.md`
6. `06_BATCH_UPLOAD_FLOW.md`
7. `07_MEDIA_WORKER_CELERY_REDIS.md`
8. `08_API_ROUTE_PLAN.md`
9. `09_UI_UX_PLAN.md`
10. `10_SECURITY_AND_RISK_PLAN.md`
11. `11_TEST_STRATEGY.md`
12. `12_IMPLEMENTATION_PHASES.md`
13. `13_DEPLOYMENT_AND_OPERATIONS.md`
14. `14_PHASE_PROMPTS.md`
15. `15_ACCEPTANCE_CHECKLIST.md`
