# Hướng dẫn sử dụng Quản lý đối tác

## 1. Mục đích phân hệ

Phân hệ Quản lý đối tác dùng để lưu hồ sơ đối tác, công ty, các trường dữ liệu mở rộng và quan hệ giữa những người trong cùng công ty.

Mục tiêu là giúp đội dự án tra cứu nhanh ai đang phụ trách việc gì, thuộc công ty nào, nên liên hệ qua kênh nào và cần lưu ý gì khi làm việc.

## 2. Luồng sử dụng khuyến nghị

Step 1: Tạo công ty.

Step 2: Tạo trường dữ liệu mẫu như sở thích, phong cách làm việc, mức độ thân thiết.

Step 3: Tạo đối tác và gán vào công ty.

Step 4: Thêm thông tin mở rộng cho từng đối tác.

Step 5: Xem công ty và sơ đồ quan hệ để nắm cấp trên, cấp dưới, phòng ban phụ trách.

## 3. Công ty

Các thông tin chính của công ty:

- Tên công ty: tên pháp nhân hoặc tên đơn vị.
- Lĩnh vực: ngành hoạt động như xây dựng, MEP, vật liệu, tư vấn thiết kế.
- Địa chỉ: địa điểm chính hoặc văn phòng liên hệ.
- Website: trang web công ty nếu có.
- SĐT: số điện thoại tổng đài hoặc đầu mối chung.
- Email: email liên hệ chung.
- Ghi chú: thông tin ngắn cần nhớ về công ty.

## 4. Đối tác

Các thông tin chính của đối tác:

- Họ tên: tên người liên hệ.
- Công ty: công ty hoặc đơn vị người đó thuộc về.
- Phòng ban: bộ phận như kỹ thuật, mua hàng, hiện trường.
- Vị trí: chức danh hoặc vai trò trong dự án.
- SĐT: số điện thoại liên hệ.
- Email: email làm việc.
- Ngày sinh: dùng khi cần ghi nhớ ngày sinh.
- Địa chỉ: địa chỉ liên hệ nếu cần.
- Ghi chú: thông tin ngắn khi làm việc với người này.

## 5. Trường dữ liệu đối tác

Trường dữ liệu mẫu là các trường mở rộng có thể gắn cho nhiều đối tác mà không cần sửa cấu trúc database.

Dùng `text` cho thông tin ngắn một dòng như sở thích hoặc người giới thiệu.

Dùng `textarea` cho ghi chú dài hơn, ví dụ lưu ý khi làm việc.

Dùng `number` cho điểm số hoặc mức độ, ví dụ mức độ thân thiết từ 1 đến 5.

Dùng `date` cho ngày tháng như ngày sinh nhật hoặc ngày gặp gần nhất.

Dùng `select` khi chỉ chọn một giá trị trong danh sách, ví dụ phong cách làm việc.

Dùng `multi_select` khi có thể chọn nhiều giá trị, ví dụ lĩnh vực quan tâm gồm tiến độ, chất lượng, chi phí.

Khi chỉnh field mẫu, dữ liệu cũ vẫn giữ snapshot tên trường, kiểu dữ liệu và giá trị tại thời điểm nhập. Vì vậy đổi label field mẫu không làm mất cách hiển thị dữ liệu đã lưu trước đó.

## 6. Ví dụ trường nên tạo

- Sở thích
- Phong cách làm việc
- Mức độ thân thiết
- Lĩnh vực quan tâm
- Kênh liên hệ ưu tiên
- Ghi chú khi làm việc
- Người giới thiệu
- Ngày sinh nhật

## 7. Sơ đồ quan hệ

Sơ đồ quan hệ dùng để xem người nào thuộc công ty nào, ai là cấp trên hoặc cấp dưới, và ai phụ trách phòng ban nào.

Trong dữ liệu mẫu, mỗi công ty có một giám đốc hoặc tổng giám đốc ở trên, các trưởng bộ phận hoặc nhân sự phụ trách nằm bên dưới.

## 8. Quyền người dùng

Admin tổng có toàn quyền xem, tạo, sửa dữ liệu đối tác, công ty và trường dữ liệu.

Admin có quyền quản trị dữ liệu đối tác theo cấu hình hiện tại của hệ thống.

Quản lý dự án có thể truy cập phân hệ đối tác và tạo dữ liệu đối tác khi được phân quyền.

Reporter có thể xem dữ liệu đối tác nhưng không được tạo, sửa hoặc xóa.

## 9. Cách chạy dữ liệu mẫu

Chạy lệnh:

```bash
flask seed-partner-demo
```

Sau đó mở:

```text
/modules
```

Chọn “Quản lý đối tác”.

## 10. Best practices

- Không tạo quá nhiều field trùng nhau.
- Nên gom field theo nhóm để dễ đọc.
- Không xóa field nếu đã dùng, nên vô hiệu hóa.
- Dữ liệu nhạy cảm nên nhập có kiểm soát.
- Ghi chú nên ngắn gọn, có ngày nếu cần.
