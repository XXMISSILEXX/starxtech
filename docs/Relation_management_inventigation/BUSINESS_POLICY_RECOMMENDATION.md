# Business policy recommendation

## Nguyên tắc

Không hard delete dữ liệu nghiệp vụ. “Xóa” trong UI phải đổi thành “Lưu trữ”
(Partner, Company, Relationship) hoặc “Vô hiệu hóa” (metadata nếu không có
full lifecycle). Active list là mặc định; archived data vẫn view được với
quyền view; archive/restore luôn POST + CSRF.

Mỗi list nghiệp vụ nên hỗ trợ `status=active|archived|all`, mặc định `active`.
Filter/search/pagination phải giữ `status`. Badge “Đã lưu trữ” xuất hiện ở
all/archived view và detail historical view.

## Partner

Giữ cặp hiện tại `is_active=False` + `deleted_at=now` khi archive; restore đặt
`is_active=True`, `deleted_at=None`. Không thêm hard delete UI. Detail archived
phải được load trong status-aware query để người có `partners.view` kiểm tra
lịch sử. Relationship tree/list mặc định ẩn Partner inactive; all/audit view
có thể hiển thị badge thay vì dựng đường quan hệ active sai lệch.

## Company

Company đã có đủ `is_active` và `deleted_at`; không cần migration chỉ để thêm
hai field này. Archive Company không cascade archive Partner: giữ lịch sử link
và tránh mất dữ liệu hàng loạt. Partner của Company archived vẫn view được,
và Partner detail hiển thị badge “Công ty đã lưu trữ”.

Không cho tạo Partner mới với Company inactive. Khi edit Partner lịch sử, form
phải render active Companies cộng với Company inactive đang gắn hiện tại; chỉ
cho giữ nguyên link đó hoặc đổi sang Company active. Company archived nên chặn
tạo/sửa Department và quản lý Relationship, hiển thị cảnh báo “Khôi phục công
ty trước khi chỉnh sửa”; read-only historical detail/tree vẫn có thể xem.

## Department và Relationship

Department hiện chỉ inactive, không soft-delete. Khuyến nghị phase đầu giữ
`is_active` lifecycle (archive=inactive, restore=active) thay vì thêm
`deleted_at` ngay, nhưng chặn create/edit nếu Company inactive. Partner giữ
`department_id` lịch sử; create/edit Partner không chọn Department inactive;
detail all view gắn badge.

Relationship đã có `is_active` + `deleted_at`. Mặc định tree/list chỉ active
và chỉ Partner active. Chưa cần UI archived Relationship riêng ở MVP; vẫn nên
thiết kế restore capability cho admin/audit và để hidden status query nội bộ.
Nếu user cần quản trị quan hệ lịch sử, bổ sung status filter sau Partner/Company
lifecycle, không làm đồng thời phase đầu.

## Open business decisions

Xác nhận retention/compliance period, ai được restore, có cho restore Partner
vào Company vẫn archived không (khuyến nghị có, nhưng không cho edit link), và
có cần lịch sử archive timestamp riêng thay vì dùng `deleted_at`.
