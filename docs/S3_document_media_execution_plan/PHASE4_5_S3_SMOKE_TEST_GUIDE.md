# Phase 4.5 — MinIO / S3-compatible smoke test

`fake` chỉ là in-memory provider cho unit test; browser không thể POST object tới nó. Browser smoke test cần signed URL của một endpoint S3-compatible thật.

## MinIO local

```bash
docker run --rm -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Mở console `http://127.0.0.1:9001`, tạo bucket `starx-local`, rồi đặt CORS qua MinIO Console hoặc `mc` cho origin `http://127.0.0.1:5666`, methods `GET, PUT, POST, HEAD`, headers `Content-Type, x-amz-*, authorization`, và expose `ETag` nếu cần.

Flask CSP cũng phải allow **storage endpoint origin** trong `connect-src`; với endpoint trên, header gồm `connect-src 'self' http://127.0.0.1:9000`. CSP và CORS là hai lớp riêng. Lưu ý `http://localhost:5666` và `http://127.0.0.1:5666` là hai browser origins khác nhau; cấu hình CORS đúng origin đang mở ứng dụng.

## Env local

```dotenv
STORAGE_PROVIDER=s3
STORAGE_BUCKET=starx-local
STORAGE_ENDPOINT_URL=http://127.0.0.1:9000
STORAGE_REGION=us-east-1
STORAGE_ACCESS_KEY_ID=minioadmin
STORAGE_SECRET_ACCESS_KEY=minioadmin
STORAGE_PREFIX=dev
STORAGE_UPLOAD_URL_TTL_SECONDS=300
STORAGE_DOWNLOAD_URL_TTL_SECONDS=300
```

Không commit credentials; các giá trị trên chỉ dành cho MinIO local. Nếu Flask chạy trên host, browser cũng phải gọi `127.0.0.1:9000`, không phải hostname nội bộ Docker.

## Checklist

1. Start MinIO, tạo bucket và CORS.
2. Chạy Flask với env trên; đăng nhập admin và mở Project Documents.
3. Upload PDF và image; `.exe`/`.html` phải bị từ chối.
4. Xác nhận complete tạo `ProjectDocumentFile`, signed download hoạt động và URL không nằm trong DB.
5. Image preview xuất hiện sau worker/eager processing; archive/restore file vẫn chỉ đổi metadata.

For image/video derivatives, run Redis and:

```bash
celery -A app.celery_worker:celery_app worker -Q media_image,media_video,storage_cleanup --loglevel=INFO
```

The worker task list must include `media.process_image_derivatives`; do not use the legacy entrypoint that causes `Working outside of application context`.

## Troubleshooting

- CORS/403: kiểm tra origin, POST fields và bucket policy private.
- `SignatureDoesNotMatch`: endpoint/region/clock phải khớp chữ ký.
- Complete size mismatch: không thay đổi file sau presign và kiểm tra `Content-Type`.
- Browser không thể tới hostname Docker nội bộ: dùng host-reachable endpoint.
- `fake` không thể dùng cho browser upload; nó chỉ dành cho tests không-network.
