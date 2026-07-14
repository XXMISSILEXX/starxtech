# Checklist bảo mật StarX

Chạy sau mỗi lần triển khai hoặc thay đổi cấu hình:

```bash
flask security-audit
```

Lệnh in `PASS`, `WARN`, `FAIL`; mã thoát khác 0 nghĩa là có mục `FAIL` cần xử lý. `WARN` không chặn vận hành, nhưng phải được xem xét trước khi đưa production.

- Dùng `APP_ENV=production`, `FLASK_DEBUG=false`, và `SECRET_KEY` ngẫu nhiên tối thiểu 32 ký tự, không dùng giá trị mẫu.
- Bật `SESSION_COOKIE_SECURE=true`, giữ `SESSION_COOKIE_HTTPONLY=true` và `SESSION_COOKIE_SAMESITE=Lax` (hoặc `Strict`) trên HTTPS.
- Kiểm tra migration đã ở head, có ít nhất một `SUPER_ADMIN` đang hoạt động, không có dữ liệu demo Partner trên production.
- Đăng nhập bị giới hạn theo `RATELIMIT_LOGIN_LIMIT`. `memory://` phù hợp local hoặc một process nội bộ; khi chạy nhiều worker production, cấu hình kho dùng chung (ví dụ Redis) để giới hạn có hiệu lực giữa các worker. Redis là tuỳ chọn, không phải dependency MVP.
- Ảnh chỉ được phục vụ qua route có kiểm tra quyền; không public thư mục upload. Kiểm tra `UPLOAD_ROOT` chỉ trỏ đến thư mục dành riêng cho ứng dụng.
- Sao lưu database và uploads, sau đó thử restore trong môi trường tách biệt.

## Reset an toàn

`flask reset-database` xóa toàn bộ bảng ứng dụng và chạy migration lại. Luôn yêu cầu:

```bash
flask reset-database --confirm "RESET DATABASE"
```

Uploads được giữ mặc định. Chỉ thêm `--delete-uploads` khi đã xác nhận đường dẫn upload. Production bị từ chối trừ khi truyền `--allow-production`; override này chỉ dùng sau khi có backup và được người vận hành phê duyệt.

## Chuẩn bị Docker và Cloudflared

MVP không bao gồm Docker hoặc Cloudflared. Nếu chuẩn bị chúng về sau, giữ secrets trong secret store hoặc biến môi trường runtime (không bake vào image), mount uploads ngoài image, đặt reverse proxy HTTPS trước ứng dụng, và chạy `flask security-audit` trong container trước khi mở tunnel Cloudflared. Không expose PostgreSQL hay upload directory qua tunnel.
