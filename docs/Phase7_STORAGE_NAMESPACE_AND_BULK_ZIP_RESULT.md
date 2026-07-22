# Phase 7 — S3 namespace và tải ZIP hàng loạt

StarX vẫn dùng một bucket theo môi trường. Object mới được phân vùng bằng
`<STORAGE_PREFIX>/document-library/...` hoặc
`<STORAGE_PREFIX>/company-media/...`, với các nhánh `originals`,
`derivatives` và `bulk-downloads`. Key cũ trong database là source of truth:
chúng không được di chuyển, sửa lại hoặc xóa trong phase này.

Một tệp tiếp tục nhận signed URL tải trực tiếp. Từ hai tệp trở lên, backend
kiểm tra tất cả tệp và ACL trước khi tạo `BulkDownloadJob`, Celery queue
`bulk_download` nén tệp vào ZIP tạm trên S3, rồi UI poll trạng thái và tải một
ZIP. Job chỉ lưu `zip_object_key`, không lưu signed URL.

Mặc định tối đa 100 tệp/2 GB, ZIP hết hạn sau 24 giờ. Task cleanup chỉ xóa
ZIP tạm đã hết hạn, không bao giờ hard-delete object nguồn. Worker:

```bash
celery -A app.celery_worker:celery_app worker -Q media_image,media_video,storage_cleanup,bulk_download --loglevel=INFO
```

Authorization được kiểm tra lại trong worker: Hồ sơ tài liệu dùng Project
Membership hoặc global custom-root permission cùng folder ACL; Company Media
dùng RBAC/album ACL `can_download`. Restricted folder/album luôn được giữ.

Không chuyển `ReportAttachment` sang S3, không file-level ACL, không di
chuyển object legacy, không ZIP permanent archive, và không thay đổi Partner
hay Daily Reports.
