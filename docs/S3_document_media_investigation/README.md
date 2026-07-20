# S3 Document & Media Investigation

## Mục tiêu và phạm vi

Đây là thiết kế cho hai module tiếp theo: **Quản lý hồ sơ tài liệu dự án** và **Thư viện ảnh/video công ty**. Báo cáo đánh giá cách bổ sung object storage S3-compatible private, metadata database, RBAC canonical và ACL theo folder/album mà không thay đổi runtime hiện tại.

Phạm vi là MVP Flask/Jinja; browser upload trực tiếp lên object storage bằng signed URL. Flask chỉ xác thực, tạo metadata, phát signed URL và kiểm tra hoàn tất upload. Báo cáo không implement code, migration, S3, hay thay đổi RBAC hiện hữu.

## Kết luận ngắn

- Dùng một bảng `storage_objects` chung là phù hợp: nó tránh lặp metadata/storage policy giữa hai module và giữ `object_key` độc lập với folder/album.
- Dùng adjacency list (`parent_id`) cho Project Document Folder. Cây nhiều cấp, rename/move rẻ vì không phải move object; chặn cycle ở service layer trong transaction.
- Dùng ACL allow-only trên folder/album (principal `user` hoặc `role`), kết hợp với module permission và scope dự án. Không đưa explicit deny vào MVP.
- Bucket phải private; signed URL không lưu DB; upload/download chỉ sau authorization. Khuyến nghị Presigned POST cho upload browser có policy size/content-type, với fallback Presigned PUT khi provider không hỗ trợ POST đầy đủ.
- Media processing theo worker-first: Redis + Celery là queue chính, còn PostgreSQL là source of truth cho metadata và job state.
- Drag/drop và batch upload mixed file type là yêu cầu MVP; ReportAttachment hiện có vẫn local upload và không bị ảnh hưởng.
- Phase đầu nên làm **storage foundation + batch presign/complete contract**, có provider fake cho test, trước khi dựng UI module.

## Tài liệu

1. [CURRENT_STATE.md](CURRENT_STATE.md)
2. [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)
3. [S3_STORAGE_ARCHITECTURE.md](S3_STORAGE_ARCHITECTURE.md)
4. [DATA_MODEL_PROPOSAL.md](DATA_MODEL_PROPOSAL.md)
5. [RBAC_AND_ACL_PROPOSAL.md](RBAC_AND_ACL_PROPOSAL.md)
6. [ROUTE_API_PLAN.md](ROUTE_API_PLAN.md)
7. [UI_UX_PLAN.md](UI_UX_PLAN.md)
8. [SECURITY_RISK_REVIEW.md](SECURITY_RISK_REVIEW.md)
9. [TEST_PLAN.md](TEST_PLAN.md)
10. [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md)
11. [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)
12. [MEDIA_PROCESSING_WORKER_PLAN.md](MEDIA_PROCESSING_WORKER_PLAN.md)
13. [BATCH_UPLOAD_PLAN.md](BATCH_UPLOAD_PLAN.md)
