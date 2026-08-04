# Sổ đăng ký rủi ro được chấp nhận có ý thức (ACCEPTED_RISKS)

## 1. File này là gì

`AUDIT_RUNBOOK.md:392` yêu cầu: mỗi finding mà chủ dự án quyết định **chấp nhận
rủi ro thay vì sửa** phải được ghi lý do vào `.audit/ACCEPTED_RISKS.md`, kèm chữ
ký và ngày. `AUDIT_RUNBOOK.md:436` đưa file này thành **exit criterion** của
Phase 10: "Không còn finding Critical/High chưa xử lý, hoặc đã ghi trong
`ACCEPTED_RISKS.md`".

File đăng ký đó **chưa từng được tạo**. Các rủi ro được chấp nhận hiện nằm rải
rác trong `.audit/VERIFIED.md`, `.audit/VERIFIED-PHASE11-DELTA.md`,
`.audit/findings-15-phase11-storage-company-media.md`,
`.audit/findings-17-phase11-deploy-evidence.md`, `.audit/PHASE10-CLOSURE.md`,
`.audit/PHASE11-DELTA-CLOSURE.md` và `.audit/ROADMAP.md`. Tài liệu này tập hợp
lại toàn bộ, giữ nguyên ID và trạng thái đã đọc được, không tự suy diễn thêm.

Nguyên tắc đọc file này:

* Mỗi mục là **rủi ro đã được nhận diện và cố ý không sửa trong Phase 10/11**,
  không phải rủi ro bị bỏ sót. Hai loại này khác nhau hoàn toàn.
* Một mục chỉ trở thành "được chấp nhận" khi có **người chịu trách nhiệm có tên
  và ngày ký**. Các trường `Chủ sở hữu` / `Ngày chấp nhận` dưới đây **để trống
  có chủ ý** — chủ dự án tự điền. Không ai được điền hộ, và tài liệu này không
  suy đoán tên hay ngày.
* Trước khi phát hành production, mọi mục Critical/High phải có chủ sở hữu và
  ngày; mục nào không có thì coi như **chưa được chấp nhận**.
* Mục §5 **không phải** rủi ro được chấp nhận. Đó là blocker còn mở. File này
  không phải giấy thông hành phát hành.

Không ghi secret, credential, token, presigned URL, object key, bucket name hay
dữ liệu cá nhân vào file này — theo yêu cầu của `CLAUDE.md` và các cảnh báo
trong `findings-15-phase11-storage-company-media.md:55` và
`findings-17-phase11-deploy-evidence.md:37`.

**Tổng số mục đăng ký: 44** (3 sản phẩm/hợp đồng, 4 hạ tầng chờ bằng chứng,
5 biên giới thiết kế, 8 khoảng trống kiểm thử/bằng chứng, 24 nợ vận hành đã
phân loại lại). Ngoài ra §5 liệt kê 9 mục **không** được chấp nhận (8 blocker còn
mở + 1 điều kiện đã đóng, giữ lại để đối chiếu).

Tình trạng kiểm chứng lại: tài liệu này được đối chiếu với source tại HEAD
`ae40172` trên branch `Phase13/Audit-log`. Hai mục đã tự đóng so với văn bản
audit gốc và được đánh dấu **ĐÃ ĐÓNG** ngay tại chỗ: **DEPLOY-004** (§3.e) và
điều kiện thư mục backup bị track (§5.9). Một mâu thuẫn giữa các tài liệu nguồn
đã được phân xử bằng code tại §6.

---

## 2. Bảng tổng hợp

| ID | Severity gốc | Nhóm | Rủi ro một dòng | Điều gì đóng được mục này |
|---|---|---|---|---|
| CONFIG-OP-001 | Low | (a) Sản phẩm/hợp đồng | `.env.example` quảng cáo giới hạn 3 ảnh/section trong khi config cố định 10 | Quyết định sản phẩm REPORTS-007 (§5.1) rồi đồng bộ template/config |
| PD-002 / UNCERTAIN-003 | Medium (Medium nếu archive là thu hồi quyền) | (a) Sản phẩm/hợp đồng | Quyền trên tài liệu con không xét trạng thái archive của thư mục cha | Chủ sản phẩm ra quyết định bằng văn bản: archive có thu hồi quyền hậu duệ hay không |
| AI-002 | Medium | (a) Sản phẩm/hợp đồng | PoC cho rằng project viewer không được download tài liệu; repo cố ý dùng `can_view_documents` cho cả preview và download | Quyết định chính sách sản phẩm nếu muốn tách view khỏi download |
| DEPLOY-OP-001 | n/a (điều kiện triển khai) | (b) Hạ tầng chờ bằng chứng | Quyền sở hữu host bind mount cache và routing Nginx `internal` chưa chứng minh được từ source | Acceptance test trên staging: miss/hit, chặn truy cập trực tiếp, đúng UID 1000 |
| DEPLOY-OP-002 | Low | (b) Hạ tầng chờ bằng chứng | Tài liệu/template hàm ý X-Accel còn Compose mặc định `send_file` | Chốt chế độ delivery production trong runbook và sửa tài liệu khớp |
| STORAGE-OP-002 | n/a (rủi ro dung lượng) | (b) Hạ tầng chờ bằng chứng | Khoản dư 1 MiB cho multipart POST chưa được quan sát với provider thật | Test biên byte trên staging với provider thật + metric quota/bucket |
| ATTACH-001 / UNCERTAIN-004 | Medium (Low nếu có hiệu lực) | (b) Hạ tầng chờ bằng chứng | Preview/thumbnail redirect không đi qua bandwidth limiter của ứng dụng | Load test S3/CDN kiểu production, đo egress/quota accounting |
| CM-OP-001 | n/a (giới hạn vận hành) | (c) Biên giới thiết kế | Huỷ upload Company Media chỉ dọn DB; byte đã lên S3 có thể còn lại | Chính sách lifecycle/reconciliation cho prefix pending + runbook có phê duyệt |
| — (không sync permission lúc startup) | n/a | (c) Biên giới thiết kế | RBAC không tự đồng bộ khi deploy; phải chạy CLI thủ công | Không cần đóng: đây là thiết kế đã tuyên bố; chỉ cần nằm trong runbook deploy |
| — (`send_file` là chế độ mặc định hợp lệ) | n/a | (c) Biên giới thiết kế | Flask tự phát bytes cache thay vì Nginx | Không cần đóng; chỉ cần chốt chế độ (xem DEPLOY-OP-002) |
| CM-003 | Low | (c) Biên giới thiết kế | Cáo buộc bulk media nhận ID không giới hạn/không kiểm kiểu | Đã bác bỏ; đóng khi có test hồi quy cho `parse_file_ids` |
| ISSUE-003 | Low | (c) Biên giới thiết kế | Cáo buộc filter ngày gây lỗi database | Đã bác bỏ; đóng khi có test dựng lỗi thật trên PostgreSQL |
| UPLOAD-001 / UNCERTAIN-001 | High (Medium nếu chứng minh được) | (d) Khoảng trống bằng chứng | Metadata do client khai được tin trước khi Pillow giải mã | Corpus ảnh dị dạng trên Pillow/Celery đúng phiên bản production |
| UPLOAD-003 / UNCERTAIN-002 | Medium (Low nếu tái hiện được) | (d) Khoảng trống bằng chứng | Đếm session/quota V2 theo kiểu read-then-create không khoá | Test hai transaction PostgreSQL thật có barrier |
| ACCOUNT-001 / UNCERTAIN-005 | High (Medium nếu chứng minh được) | (d) Khoảng trống bằng chứng | Decode ảnh đồng bộ không có trần pixel ở tầng ứng dụng | Corpus decompression-bomb trên Pillow đã deploy + metric tài nguyên |
| TEST-001 | Info | (d) Khoảng trống bằng chứng | Decorator tổng hợp trong conftest phủ code không tồn tại thật | Dọn hoặc thay bằng test dùng route thật |
| TEST-002 | Medium | (d) Khoảng trống bằng chứng | PoC bảo mật bị loại khỏi cấu hình pytest → mất bằng chứng hồi quy | Đưa PoC vào CI gate |
| TEST-003 | Medium | (d) Khoảng trống bằng chứng | Fixture SQLite không chứng minh được hành vi PostgreSQL | Suite hồi quy chạy trên PostgreSQL |
| TEST-004 | Medium | (d) Khoảng trống bằng chứng | Thiếu test cho đường xử lý ảnh | Test hồi quy cho display-image/media pipeline |
| JS-001 | Low | (d) Khoảng trống bằng chứng | Coverage JavaScript thấp so với lượng logic frontend | Thêm `tests_js/*.test.js` cho các file JS tương tác |
| AI-001, AI-003, AI-004 | Medium / Low / Info | (e) Nợ vận hành | Lệch runtime Python trong tài liệu, flag media-processing chết, permission code không ai dùng | Dọn tài liệu/config/catalogue |
| CLI-002..CLI-005 | Medium ×3, Low ×1 | (e) Nợ vận hành | `security-audit` tĩnh, restore một phần, backup không nguyên tử, race seeding entrypoint | Runbook vận hành + drill restore |
| ADMIN-003 | Low | (e) Nợ vận hành | Audit log membership không dựng lại được flag | Bổ sung chi tiết audit |
| REPORTS-005, REPORTS-007 (Phase 10) | Medium / Low | (e) Nợ vận hành | Race khi retry tạo report; thiếu audit event khi huỷ upload | Xử lý lỗi thân thiện + audit event |
| PD-004, PD-005 | Low / Info | (e) Nợ vận hành | Tên tài liệu trùng; người tạo custom root có thể tự khoá mình | Ràng buộc/UX |
| CM-004, CM-006 | Low / Low | (e) Nợ vận hành | Audit media chưa đủ; tên album trùng khi ghi đồng thời | Audit + unique constraint |
| PARTNER-004, PARTNER-005 | Low / Low | (e) Nợ vận hành | Form partner dựng tay tạo giá trị không nhất quán; lỗi ảnh sau commit | Validate + xử lý thao tác một phần |
| PARTNER-FIELD-001..003 | Low, Info, Low | (e) Nợ vận hành | Định nghĩa field không hợp lệ/nhãn trùng/UX kích hoạt collection | Ràng buộc và UX lifecycle |
| PARTNER-REL-003 | Low | (e) Nợ vận hành | Đệ quy quan hệ khi dữ liệu bị hỏng | Giới hạn độ sâu traversal |
| ISSUE-004 | Low | (e) Nợ vận hành | Không giới hạn độ dài tiêu đề issue | Validate độ dài |
| DEPLOY-004 | Medium | (e) Nợ vận hành | Compose backup bị track có thể làm yếu rate limiting | **ĐÃ ĐÓNG** bởi commit `ae40172` — thư mục backup đã untrack |
| DEPLOY-005, DEPLOY-007 | Medium, Low | (e) Nợ vận hành | Image Cloudflared không pin digest; thiếu hardening/health ở Docker/Compose | Pin digest đã review; thêm healthcheck và tuỳ chọn hardening |

Nhắc lại: **DEPLOY-001, DEPLOY-002, DEPLOY-003, DEPLOY-006 không có trong bảng
trên** vì `VERIFIED.md:225` nói rõ chúng "still require operational resolution
before a safe release". Chúng nằm ở §5.

---

## 3. Các mục chi tiết

Định dạng mỗi mục: mô tả — vì sao chấp nhận thay vì sửa — rủi ro còn lại theo
nghĩa nghiệp vụ — bằng chứng/quyết định để đóng — nguồn (file:line) — chủ sở hữu
và ngày (để trống).

### (a) Quyết định sản phẩm / hợp đồng

#### a.1 — CONFIG-OP-001 · Low · Open (gắn với REPORTS-007)

* **Mô tả:** `.env.example:11` ghi `MAX_IMAGES_PER_SECTION=3` và
  `.env.example:52` ghi `DAILY_REPORT_MAX_FILES_PER_SECTION=3`, trong khi
  `app/config.py:65` mặc định `MAX_IMAGES_PER_SECTION` là 10 (và chú thích nó là
  legacy) còn `app/config.py:70` cố định `DAILY_REPORT_MAX_FILES_PER_SECTION = 10`
  không đọc environment. Giới hạn thật do
  `app/reports/constants.py:7` (`MAX_ATTACHMENTS_PER_REPORT_SECTION = 10`) quyết định.
* **Vì sao chấp nhận thay vì sửa:** Không phải lỗi bảo mật. Sửa template mà chưa
  có quyết định 3-hay-10 sẽ khoá cứng một hợp đồng sản phẩm chưa được phê duyệt.
  Audit cố ý gộp mục này vào REPORTS-007 thay vì tính thành finding thứ hai.
* **Rủi ro nghiệp vụ còn lại:** Người vận hành đặt 3 và tin là đã có hiệu lực,
  trong khi hệ thống vẫn nhận 10 ảnh/section. Nguy hiểm nhất khi rollback sự cố
  hoặc tính dung lượng: dự toán lưu trữ và tải UI sai theo hệ số hơn 3 lần.
* **Đóng bằng:** Quyết định sản phẩm ở §5.1, sau đó xoá setting chết hoặc làm cho
  setting được ghi trong tài liệu thực sự điều khiển giới hạn.
* **Nguồn:** `.audit/VERIFIED-PHASE11-DELTA.md:18`;
  `.audit/findings-16-phase11-reports-integration.md:43-48`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### a.2 — PD-002 / UNCERTAIN-003 · Medium · UNCERTAIN, cần quyết định sản phẩm

* **Mô tả:** Kiểm tra quyền trên tài liệu/thư mục con **không** xét trạng thái
  archive của tổ tiên. Người từng có quyền xem nhánh con vẫn list/preview/
  download được sau khi thư mục cha bị archive.
* **Vì sao chấp nhận thay vì sửa:** Repository chưa từng tuyên bố rằng archive là
  hành vi **thu hồi quyền**. Nếu archive chỉ mang nghĩa "sắp xếp tổ chức" thì
  hành vi hiện tại đúng. Audit từ chối tự chọn ngữ nghĩa sản phẩm, và từ chối
  siết quyền dựa trên phỏng đoán.
* **Rủi ro nghiệp vụ còn lại:** Nếu ý định thật là archive = ngừng chia sẻ, thì
  tài liệu dự án đã đóng vẫn tiếp cận được bởi thành viên cũ của nhánh con —
  tiết lộ trong phạm vi người đã được cấp quyền, không phải người ngoài.
* **Đóng bằng:** Quyết định lifecycle bằng văn bản của chủ sản phẩm **trước**;
  sau đó test staging có xác thực: list/preview/download hậu duệ sau khi archive
  tổ tiên phải bị từ chối nếu chọn phương án thu hồi.
* **Blocker?** `VERIFIED.md:213` ghi **NO**, nhưng `PHASE10-CLOSURE.md:146` ghi
  "Yes if revocation is policy and denial fails; policy decision is mandatory
  first" — nghĩa là nó chỉ trở thành blocker sau khi có quyết định chọn thu hồi.
* **Nguồn:** `.audit/VERIFIED.md:65,211-213,297-298`;
  `.audit/PHASE10-CLOSURE.md:146`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### a.3 — AI-002 · Medium · FALSE POSITIVE, cố ý không sửa

* **Mô tả:** Một PoC do AI sinh ra khẳng định project viewer không được phép
  download tài liệu dự án. Thực tế Project Documents cố ý dùng
  `can_view_documents` làm predicate cho **cả** preview và download; đoạn RBAC bị
  viện dẫn thuộc bề mặt catalogue không gắn project.
* **Vì sao chấp nhận thay vì sửa:** PoC hợp lệ về mặt cơ học nhưng **sai về
  chính sách**: nó tự phát minh ra một xung đột policy không tồn tại trong repo.
  `VERIFIED.md:229` cảnh báo rõ nó "must not drive a fix without a product policy
  change". `PHASE10-CLOSURE.md:9` loại nó khỏi release gate.
* **Rủi ro nghiệp vụ còn lại:** Bằng 0 với hành vi hiện tại. Rủi ro thật là rủi
  ro ngược: nếu ai đó "sửa" theo PoC, người dùng dự án hợp lệ sẽ mất quyền tải
  tài liệu mà không có quyết định sản phẩm nào.
* **Đóng bằng:** Chỉ cần một quyết định sản phẩm nếu công ty muốn tách quyền view
  khỏi quyền download; khi đó mới thiết kế predicate riêng.
* **Nguồn:** `.audit/VERIFIED.md:23,46,229,252-253`; `.audit/PHASE10-CLOSURE.md:9`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

### (b) Bằng chứng triển khai và hạ tầng còn chờ

#### b.1 — DEPLOY-OP-001 · điều kiện triển khai chưa kiểm chứng · Staging required

* **Mô tả:** Container ghi cache media dưới UID 1000 vào
  `${MEDIA_CACHE_HOST_ROOT:-/opt/starxtech/cache/media}`, còn Nginx đọc cùng thư
  mục host đó. Source không chứng minh được owner/mode thư mục đích thật, chính
  sách SELinux/AppArmor, UID mapping, hay việc site Nginx đang cài đúng là file
  cấu hình được cung cấp.
* **Vì sao chấp nhận thay vì sửa:** Đây **không phải** finding trong source code.
  Cấu hình trong repo đã nhất quán (`deploy/nginx/starx-report.conf:9-15` đánh dấu
  location là `internal`; Compose không publish port/volume cache). Phần còn lại
  là sự thật triển khai, chỉ chứng minh được trên host thật; audit cố ý không
  chạy Compose up hay tạo state triển khai.
* **Rủi ro nghiệp vụ còn lại:** Hai kịch bản. (1) Sai quyền → cache không ghi
  được → thumbnail/preview lỗi hoặc chậm, không rò rỉ dữ liệu. (2) Nếu ai đó cấu
  hình lệch và biến thư mục cache thành static public thì mới thành lộ dữ liệu —
  chính vì vậy acceptance test phải khẳng định truy cập trực tiếp bị chặn.
* **Đóng bằng:** Trên staging: tạo thư mục với quyền tối thiểu cho UID 1000 +
  quyền đọc cho Nginx; gọi một request thumbnail đã xác thực hai lần (miss/hit);
  khẳng định `/_protected_media_cache/...` truy cập trực tiếp/không xác thực là
  không tiếp cận được; kiểm cả `send_file` và (tuỳ chọn) `x_accel`. Không đưa
  object S3 hay signed URL vào log audit.
* **Nguồn:** `.audit/findings-17-phase11-deploy-evidence.md:32-37`;
  `.audit/VERIFIED-PHASE11-DELTA.md:21`;
  `.audit/findings-15-phase11-storage-company-media.md:54`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### b.2 — DEPLOY-OP-002 · Low · Open (mơ hồ tài liệu)

* **Mô tả:** Comment trong `.env.example:88-95` và mô tả README hàm ý Compose ghi
  đè bằng cache X-Accel do Nginx phục vụ, còn `docker-compose.yml:45-50` mặc định
  `MEDIA_CACHE_DELIVERY_MODE` là `send_file`.
* **Vì sao chấp nhận thay vì sửa:** Cả hai chế độ đều được hỗ trợ và đều an toàn
  nếu cấu hình đúng thiết kế, nên đây là mơ hồ tài liệu, không phải lộ dữ liệu.
  Chọn chế độ nào là quyết định vận hành, không phải patch source.
* **Rủi ro nghiệp vụ còn lại:** Người vận hành tin Nginx đang phát bytes trong
  khi thực tế Flask làm việc đó → quan sát sai về dung lượng/hiệu năng, hoặc test
  rollout X-Accel thất bại vào lúc không mong đợi.
* **Đóng bằng:** Ghi rõ chế độ delivery production đã chọn trong environment/
  runbook phát hành và sửa tài liệu cho khớp.
* **Nguồn:** `.audit/findings-17-phase11-deploy-evidence.md:39-45`;
  `.audit/VERIFIED-PHASE11-DELTA.md:22`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### b.3 — STORAGE-OP-002 · rủi ro dung lượng chưa kiểm chứng · Staging required

* **Mô tả:** Khoản dư 1 MiB cho multipart được cố ý cộng vào
  `content-length-range` của presigned POST vì CloudFly đánh giá kích thước
  request multipart, còn bước completion HEAD-check đúng số byte object đã khai.
  Session và quota accounting dùng số byte khai báo.
* **Vì sao chấp nhận thay vì sửa:** Đây là **thoả hiệp tương thích có chủ ý** với
  provider, không phải upload không giới hạn. Không thể kiểm chứng bằng
  `FakeStorageProvider`; suy diễn hành vi provider từ test fake là sai phương pháp.
* **Rủi ro nghiệp vụ còn lại:** POST bị bỏ dở lặp lại có thể tiêu thụ dung lượng
  vật lý nhiều hơn con số accounting quan sát được một chút — đặc biệt khi cộng
  hưởng với CM-OP-001. Không phải bypass quyền; completion vẫn từ chối object có
  kích thước cuối khác số đã khai.
* **Đóng bằng:** Trên staging với provider thật: upload đúng biên byte và từ chối
  body vượt cỡ; quan sát metric quota/bucket; xác nhận lifecycle xoá pending key
  đã hết hạn/bị huỷ.
* **Nguồn:** `.audit/findings-15-phase11-storage-company-media.md:44-50`;
  `.audit/VERIFIED-PHASE11-DELTA.md:20`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### b.4 — ATTACH-001 / UNCERTAIN-004 · Medium (Low nếu có hiệu lực) · UNCERTAIN

* **Mô tả:** Ứng dụng không gọi bandwidth limiter cho các redirect preview/
  thumbnail của attachment; lưu lượng thực đi qua S3/CDN.
* **Vì sao chấp nhận thay vì sửa:** Source chỉ chứng minh được là **không có
  counter ở tầng ứng dụng**. Lưu lượng thật, hành vi cache và phạm vi quota của
  provider chưa đo. Thêm limiter mà chưa đo có thể chặn oan luồng preview hợp lệ.
* **Rủi ro nghiệp vụ còn lại:** Nếu chứng minh được, người nhận URL có thể tạo
  egress/chi phí không được tính vào quota — tức rủi ro **hoá đơn và dung lượng**,
  không phải rò rỉ dữ liệu (URL vẫn cần được cấp cho người đã xác thực).
* **Đóng bằng:** Load test preview/thumbnail kiểu production trên S3/CDN có bật
  cache và quota/rate accounting; trace request và metric của provider.
* **Blocker?** `VERIFIED.md:217` ghi NO; `PHASE10-CLOSURE.md:147` ghi "Yes if
  unbounded/billable bypass is demonstrated".
* **Nguồn:** `.audit/VERIFIED.md:79,215-217,333-334`;
  `.audit/PHASE10-CLOSURE.md:147`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

### (c) Biên giới thiết kế được chấp nhận

#### c.1 — CM-OP-001 · giới hạn vận hành đã ghi nhận · cần bằng chứng từ chủ sở hữu

* **Mô tả:** Huỷ upload session Company Media chỉ dọn metadata trong database.
  `app/company_media/upload_cleanup.py` cố ý **không import provider** và chỉ xoá
  các row disposable. Object đã lên S3 trước khi người dùng huỷ có thể còn lại
  dưới một pending key private sau khi row `StorageObject` bị xoá.
* **Vì sao chấp nhận thay vì sửa:** Gọi S3 hoặc âm thầm xoá key lạ từ một HTTP
  cancel endpoint sẽ vi phạm biên giới "async / S3-only ownership" mà dự án cố ý
  đặt ra. Các tài liệu Phase 5 chọn ranh giới DB-only này và hoãn phần
  reconciliation bucket; test Phase 11 **chủ động khẳng định** cleanup không bao
  giờ gọi provider.
* **Rủi ro nghiệp vụ còn lại:** Một uploader hợp lệ có thể tiêu tốn dung lượng
  bucket private bằng byte bỏ dở, cho tới khi một tiến trình lifecycle/
  reconciliation riêng dọn. **Không** cấp cho kẻ tấn công URL, quyền list bucket,
  object key hay quyền đọc: object vẫn private và mọi route đọc đều dựa trên
  object có trong database cộng kiểm tra ACL.
* **Đóng bằng:** Chủ sở hữu production cung cấp chính sách lifecycle/
  reconciliation cho prefix pending của Company Media, thời gian retention,
  ngưỡng cảnh báo/usage, và runbook đã phê duyệt. Audit không gọi S3, không list
  key, không chạy CLI cleanup dạng mutating.
* **Nguồn:** `.audit/findings-15-phase11-storage-company-media.md:34-42`;
  `.audit/VERIFIED-PHASE11-DELTA.md:19`;
  `.audit/PHASE11-DELTA-CLOSURE.md:56-58`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### c.2 — Không đồng bộ permission lúc startup (không có ID) · thiết kế cố ý

* **Mô tả:** Không có bước synchronize permission nào được thêm vào startup.
  `app/permissions/registry.py` là nguồn sự thật; row DB chỉ được đồng bộ khi
  người vận hành chạy `flask sync-permissions --apply-defaults`.
* **Vì sao chấp nhận thay vì sửa:** Đây là quy tắc dự án đã tuyên bố, nhất quán
  với thiết kế phân quyền ba tầng. Tự đồng bộ lúc deploy sẽ âm thầm đổi
  authorization của production.
* **Rủi ro nghiệp vụ còn lại:** Nếu người vận hành **quên** chạy lệnh sau khi đổi
  registry, quyền trong DB lệch với code → người dùng thiếu quyền mới (fail
  closed) hoặc giữ quyền cũ đã bị bỏ. Đây là rủi ro quy trình vận hành, không
  phải lỗi code.
* **Đóng bằng:** Không cần "đóng"; chỉ cần bước bắt buộc trong runbook deploy và
  một kiểm tra sau deploy rằng registry và DB khớp nhau.
* **Nguồn:** `.audit/PHASE11-DELTA-CLOSURE.md:59-60`; `CLAUDE.md` (quy tắc dự án).
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### c.3 — `send_file` là chế độ mặc định hợp lệ, không phải fallback (không có ID)

* **Mô tả:** Cache media vẫn private và authorization-first; cả object S3 gốc và
  file cache đều không có route public. `send_file` là chế độ được hỗ trợ, không
  phải fallback về filesystem public.
* **Vì sao chấp nhận thay vì sửa:** Audit **cố ý không gọi đây là lỗ hổng**. Ở
  chế độ mặc định, Flask vẫn kiểm quyền trước khi phát byte; ở chế độ `x_accel`,
  location `internal` chỉ nhận đường dẫn cache tương đối đã được cache service
  kiểm tra hợp lệ.
* **Rủi ro nghiệp vụ còn lại:** Chủ yếu là hiệu năng/dung lượng: process web
  phục vụ byte ảnh thay vì Nginx. Rủi ro lộ dữ liệu chỉ phát sinh nếu ai đó tự
  publish thư mục cache ra ngoài — thuộc DEPLOY-OP-001.
* **Đóng bằng:** Chốt chế độ delivery (DEPLOY-OP-002) và giữ nguyên khẳng định
  "không có route public cho cache" trong mọi thay đổi tương lai.
* **Nguồn:** `.audit/PHASE11-DELTA-CLOSURE.md:53-55`;
  `.audit/findings-15-phase11-storage-company-media.md:26`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### c.4 — CM-003 · Low · FALSE POSITIVE, cố ý không sửa

* **Mô tả:** Cáo buộc route bulk của Company Media nhận danh sách file ID không
  giới hạn và không kiểm kiểu. Thực tế `parse_file_ids` được dùng chung, có giới
  hạn số lượng và validate integer.
* **Vì sao chấp nhận thay vì sửa:** Cáo buộc đã cũ (stale) so với source hiện
  tại; sửa thêm sẽ là code trùng lặp không cần thiết.
* **Rủi ro nghiệp vụ còn lại:** Bằng 0 ở hành vi hiện tại. Rủi ro còn lại là
  **hồi quy**: nếu sau này có route bulk mới không dùng parser dùng chung này thì
  giới hạn sẽ mất.
* **Đóng bằng:** Một test hồi quy khẳng định mọi bulk endpoint đều đi qua
  `parse_file_ids` với cap và kiểm kiểu.
* **Nguồn:** `.audit/VERIFIED.md:70,230,306-307`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### c.5 — ISSUE-003 · Low · FALSE POSITIVE, cố ý không sửa

* **Mô tả:** Cáo buộc filter ngày ở module issue gây lỗi database vì không parse
  giá trị. Đúng là không có bước parse, nhưng việc bind một string vào phép so
  sánh date của SQLAlchemy **không tự chứng minh** có exception ở database.
* **Vì sao chấp nhận thay vì sửa:** Đây là kết luận độ tin cậy chỉ dựa trên
  source và đã bị đánh giá là phóng đại; không có bằng chứng runtime.
* **Rủi ro nghiệp vụ còn lại:** Nếu thực tế PostgreSQL báo lỗi với input xấu thì
  hậu quả là **lỗi 500 / trải nghiệm xấu** cho người dùng đã xác thực khi nhập
  ngày sai định dạng, không phải vấn đề phân quyền hay dữ liệu.
* **Đóng bằng:** Một test trên PostgreSQL thật gửi giá trị ngày không hợp lệ; nếu
  dựng được lỗi thì mới bổ sung parse/validate và thông báo tiếng Việt.
* **Nguồn:** `.audit/VERIFIED.md:83,231,339-340`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

### (d) Khoảng trống kiểm thử và bằng chứng

#### d.1 — UPLOAD-001 / UNCERTAIN-001 · High → Medium nếu chứng minh được · UNCERTAIN

* **Mô tả:** Kiểu file do client khai báo được tin trước khi Pillow xử lý. Endpoint
  và tác nhân đều thật, nhưng phiên bản Pillow thực tế, các giới hạn decompression,
  giới hạn worker và tác động khai thác đều chưa được chứng minh.
* **Vì sao chấp nhận thay vì sửa:** Audit không nâng severity chỉ vì có mặt một
  API nguy hiểm khi chưa chứng minh dữ liệu không tin cậy tới được nó với hậu quả
  thật. Cần bằng chứng runtime, không phải phán đoán từ source.
* **Rủi ro nghiệp vụ còn lại:** Nếu tái hiện được: một người **đã có quyền upload**
  có thể làm treo/ngốn tài nguyên worker media → thumbnail/preview toàn hệ thống
  chậm hoặc pending, ảnh hưởng vận hành báo cáo hằng ngày. Không phải leo thang
  quyền.
* **Đóng bằng:** Worker S3/Celery cô lập trên staging xử lý một corpus ảnh dị
  dạng/nhập nhằng định dạng bằng đúng phiên bản Pillow đã deploy, kèm đánh giá
  CVE và metric tài nguyên worker.
* **Blocker?** `VERIFIED.md:205` ghi "NO pending proof";
  `PHASE10-CLOSURE.md:144` ghi "Yes if exploit/DoS is reproduced".
* **Nguồn:** `.audit/VERIFIED.md:61,203-205,291-292`;
  `.audit/PHASE10-CLOSURE.md:144`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.2 — UPLOAD-003 / UNCERTAIN-002 · Medium → Low nếu tái hiện được · UNCERTAIN

* **Mô tả:** `app/reports/direct_uploads.py:116-167` đọc rồi tạo counter session
  mà không khoá (check-then-act). Kết quả test SQLite không thể kết luận về mức
  isolation của PostgreSQL.
* **Vì sao chấp nhận thay vì sửa:** Test hiện tại chạy trên SQLite in-memory nên
  không phải bằng chứng cho production PostgreSQL. Thêm khoá mà chưa đo có thể
  gây thắt cổ chai cho luồng upload trực tiếp.
* **Rủi ro nghiệp vụ còn lại:** Nếu tái hiện được: một reporter upload đồng thời
  có thể vượt nhẹ giới hạn số file/section hoặc tạo item trùng → sai lệch dữ liệu
  báo cáo và quota, không phải vượt quyền dự án.
* **Đóng bằng:** Hai transaction PostgreSQL thật đồng bộ bằng barrier tại thời
  điểm presign V2, khẳng định giới hạn đã khai và tính duy nhất của item, kèm
  bằng chứng row/query đã commit.
* **Nguồn:** `.audit/VERIFIED.md:63,207-209,294-295`;
  `.audit/PHASE10-CLOSURE.md:145`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.3 — ACCOUNT-001 / UNCERTAIN-005 · High → Medium nếu chứng minh được · UNCERTAIN

* **Mô tả:** Decoder đồng bộ ở luồng display-image không có trần pixel ở tầng ứng
  dụng (`app/display_images.py`, route account). Bản Pillow bị cho là có CVE và
  tác động thực tế lên request cần test trên runtime đã cài.
* **Vì sao chấp nhận thay vì sửa:** Cần đúng phiên bản dependency của production
  để kết luận; không dựng kết luận từ requirements file.
* **Rủi ro nghiệp vụ còn lại:** Nếu tái hiện được: một người dùng đã xác thực có
  thể làm cạn CPU/RAM của web process bằng một ảnh dựng riêng → toàn bộ ứng dụng
  chậm hoặc gián đoạn trong giờ làm việc. Đây là rủi ro **khả dụng**, không phải
  bảo mật dữ liệu.
* **Đóng bằng:** Corpus decompression-bomb/nhập nhằng định dạng có kiểm soát chạy
  qua endpoint display-image đồng bộ với đúng Pillow đã deploy; ghi phiên bản
  dependency chính xác, kết quả corpus và metric tài nguyên.
* **Nguồn:** `.audit/VERIFIED.md:89,219-221,357-358`;
  `.audit/PHASE10-CLOSURE.md:148`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.4 — TEST-002 · Medium · NOT A SECURITY FINDING

* **Mô tả:** Các PoC bảo mật bị loại khỏi cấu hình pytest, nên chúng không phải
  một cổng hồi quy tự động.
* **Vì sao chấp nhận thay vì sửa:** Hệ quả là thiếu bằng chứng hồi quy, không
  phải một biên giới bảo mật bị vỡ. Phase 10 đã chạy PoC bằng lệnh tường minh và
  ghi kết quả (`PHASE10-CLOSURE.md:110-119`: 9 passed, exit 0).
* **Rủi ro nghiệp vụ còn lại:** Một trong 34 lỗ hổng đã fix có thể **hồi quy âm
  thầm** trong lần thay đổi sau mà không có test nào đỏ. Đây là rủi ro tích luỹ,
  tăng theo thời gian.
* **Đóng bằng:** Đưa các PoC vào một CI gate chạy được, tách khỏi suite chính nếu
  cần, với kết quả exit 0 được lưu.
* **Nguồn:** `.audit/VERIFIED.md:224-225,366-367`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.5 — TEST-003 · Medium · NOT A SECURITY FINDING

* **Mô tả:** Fixture test dùng SQLite in-memory; các caller phụ thuộc hành vi
  transaction không được chứng minh trên PostgreSQL.
* **Vì sao chấp nhận thay vì sửa:** Đây là giới hạn kiến trúc test đã tuyên bố
  trong `CLAUDE.md`, không phải lỗi. Chuyển toàn bộ suite sang PostgreSQL là thay
  đổi hạ tầng, không thuộc phạm vi một fix bảo mật.
* **Rủi ro nghiệp vụ còn lại:** Suite xanh **không chứng minh** tính đúng đắn ở
  production: constraint, isolation, locking, JSON, index, case-sensitivity, múi
  giờ và ghi đồng thời đều có thể khác. UPLOAD-003 (d.2) là một hệ quả trực tiếp.
* **Đóng bằng:** Ít nhất các suite hot path (auth, phân quyền, upload, migration)
  chạy trên PostgreSQL thật và lưu kết quả.
* **Nguồn:** `.audit/VERIFIED.md:224-225,369-370`; `CLAUDE.md` (mục testing).
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.6 — TEST-004 · Medium · NOT A SECURITY FINDING

* **Mô tả:** Thiếu test hồi quy cho đường xử lý ảnh (suite test / route account).
* **Vì sao chấp nhận thay vì sửa:** Thiếu test là thiếu bằng chứng, không phải lỗ
  hổng; và nó chồng lấn với ACCOUNT-001 (d.3) đang chờ bằng chứng runtime.
* **Rủi ro nghiệp vụ còn lại:** Thay đổi ở pipeline ảnh có thể phá thumbnail/
  avatar/logo mà không test nào phát hiện, ảnh hưởng trực tiếp tới UI báo cáo.
* **Đóng bằng:** Test hồi quy cho display-image và media pipeline, gồm cả nhánh
  từ chối input.
* **Nguồn:** `.audit/VERIFIED.md:224-225,372-373`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.7 — TEST-001 · Info · NOT A SECURITY FINDING

* **Mô tả:** conftest/test route có decorator tổng hợp; phần coverage tương ứng
  là code chết, không phản ánh route thật.
* **Vì sao chấp nhận thay vì sửa:** Chỉ ảnh hưởng tới việc đọc số coverage.
* **Rủi ro nghiệp vụ còn lại:** Số coverage bị lạc quan hoá → người ra quyết định
  tin rằng hot path được phủ nhiều hơn thực tế.
* **Đóng bằng:** Bỏ decorator tổng hợp hoặc chuyển sang test dùng route thật.
* **Nguồn:** `.audit/VERIFIED.md:224-225,363-364`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

#### d.8 — JS-001 · Low · NOT A SECURITY FINDING

* **Mô tả:** Coverage JavaScript thấp so với lượng logic frontend đang chạy trực
  tiếp từ `app/static/js/*.js`.
* **Vì sao chấp nhận thay vì sửa:** Kiểm tra ở frontend không phải lớp bảo mật;
  mọi giá trị từ browser đều được kiểm lại ở server. Thiếu test JS là rủi ro
  chức năng.
* **Rủi ro nghiệp vụ còn lại:** Lỗi hồi quy ở luồng upload trực tiếp/preview chỉ
  bị phát hiện bởi người dùng thật trên công trường, không bởi CI.
* **Đóng bằng:** Mỗi file JS tương tác không tầm thường có một
  `tests_js/*.test.js` tương ứng theo mẫu `report-direct-upload.test.js`.
* **Nguồn:** `.audit/VERIFIED.md:224-225,360-361`.
* **Chủ sở hữu:** _(để trống)_ · **Ngày chấp nhận:** _(để trống)_

### (e) Nợ vận hành phi bảo mật đã phân loại lại

`VERIFIED.md:223-225` gom một khối lớn finding về verdict **NOT A SECURITY
FINDING**: quan sát code phần lớn là đúng, nhưng hệ quả thuộc phạm vi deployment
readiness, thiếu bằng chứng test, độ tin cậy, đầy đủ audit log, hoặc nợ chất
lượng dữ liệu của người dùng đã xác thực — **không có một biên giới
authorization/confidentiality/integrity cụ thể nào bị vượt**.
`ROADMAP.md:44-46` xác nhận nhóm LATER không chứa finding bảo mật nào và để các
mục này lại trong `VERIFIED.md` dưới dạng công việc vận hành phi bảo mật.

Toàn bộ các mục dưới đây có **Blocker: NO** trong record gốc, trừ ghi chú riêng.

| ID | Severity gốc | Mô tả một dòng | Vì sao chấp nhận | Rủi ro nghiệp vụ còn lại | Đóng bằng | Nguồn |
|---|---|---|---|---|---|---|
| AI-001 | Medium | Lệch runtime Python giữa đặc tả và image | Chỉ là readiness giao hàng, không có request sink | Chạy sai phiên bản → khác biệt hành vi/CVE không lường trước | Bằng chứng build/run trên Python 3.12 (đã có: `PHASE10-CLOSURE.md:113`) | `VERIFIED.md:249-250` |
| AI-003 | Low | Flag media-processing không được dùng, job vẫn dispatch | Chỉ là kỳ vọng vận hành | Người vận hành tưởng đã tắt xử lý media nhưng thực tế vẫn chạy | Xoá flag chết hoặc làm nó thực sự có hiệu lực | `VERIFIED.md:255-256` |
| AI-004 | Info | Ba permission code không route nào tiêu thụ | Chỉ là bảo trì catalogue | Người quản trị cấp quyền không có tác dụng → hiểu sai về quyền đã cấp | Dọn registry và chạy `flask sync-permissions` có kiểm soát | `VERIFIED.md:258-259` |
| CLI-002 | Medium | `flask security-audit` là lint cấu hình tĩnh, không chứng minh worker/CORS bên ngoài | Không phải lỗ hổng; là giới hạn của công cụ | Tự tin sai về mức sẵn sàng phát hành | Bổ sung kiểm tra runtime vào runbook, không dựa vào lệnh này làm cổng | `VERIFIED.md:261-262` |
| CLI-003 | Medium | `scripts/restore_db.sh` có thể restore một phần từ dump do người vận hành chọn | Rủi ro quy trình phục hồi, không phải lỗ hổng ứng dụng từ xa | Sự cố thật mà restore ra dữ liệu không đầy đủ → mất bản ghi nghiệp vụ | Drill restore cô lập ít nhất một lần, có biên bản | `VERIFIED.md:264-265` |
| CLI-004 | Medium | Backup không nguyên tử; giá trị retention ảnh hưởng khả năng phục hồi | Rủi ro vận hành dữ liệu | Archive một phần → không phục hồi được tới điểm mong muốn | Kiểm tra tính toàn vẹn archive + chính sách retention đã phê duyệt | `VERIFIED.md:267-268` |
| CLI-005 | Low | Entrypoint có thể reseed/tranh chấp khi nhiều replica | Độ tin cậy triển khai | Deploy nhiều replica gây lỗi khởi động khó chẩn đoán | Chỉ seed từ một job one-shot; tài liệu hoá | `VERIFIED.md:270-271` |
| ADMIN-003 | Low | Audit log membership không dựng lại được các capability flag | Chỉ là đầy đủ pháp chứng | Khi tranh chấp quyền, không truy được ai đã cấp gì | Ghi snapshot flag vào audit record | `VERIFIED.md:273-274` |
| REPORTS-005 | Medium | Retry tạo report có thể lộ lỗi transaction | Không thể tạo ra quyền truy cập | Người dùng gặp lỗi kỹ thuật khó hiểu khi mạng công trường kém | Xử lý unique constraint và trả thông báo tiếng Việt rõ ràng | `VERIFIED.md:285-286` |
| REPORTS-007 (Phase 10) | Low | Thiếu audit event ở luồng cancellation/cleanup | Chỉ là thiếu audit | Không truy được ai huỷ session upload nào | Bổ sung audit event | `VERIFIED.md:288-289` — **lưu ý trùng ID, xem §6** |
| PD-004 | Low | Tên tài liệu có thể trùng khi sửa đồng thời | Toàn vẹn/UX | Người dùng nhầm lẫn giữa hai tài liệu cùng tên | Unique constraint hoặc cảnh báo UI | `VERIFIED.md:300-301` |
| PD-005 | Info | Người tạo custom root có thể tự khoá mình khỏi root đó | Tự khoá, không mở rộng biên giới | Cần admin can thiệp; gián đoạn công việc | UX cảnh báo trước khi lưu ACL | `VERIFIED.md:303-304` |
| CM-004 | Low | Audit record của Company Media chưa đầy đủ | Chỉ là đầy đủ logging | Không truy được lịch sử thao tác media | Bổ sung audit | `VERIFIED.md:309-310` |
| CM-006 | Low | Tên album có thể trùng khi ghi đồng thời | Concurrency/chất lượng dữ liệu | Thư viện media khó điều hướng | Unique constraint | `VERIFIED.md:312-313` |
| PARTNER-004 | Low | Editor có quyền có thể tạo giá trị field không nhất quán qua form dựng tay | Không có tác động vượt phạm vi | Dữ liệu partner nhiễu; báo cáo sai | Validate server-side theo định nghĩa field | `VERIFIED.md:315-316` |
| PARTNER-005 | Low | Lỗi ảnh sau commit gây thao tác một phần | UX/độ tin cậy | Partner có bản ghi nhưng thiếu ảnh, không ai được thông báo | Xử lý thao tác một phần và thông báo | `VERIFIED.md:318-319` |
| PARTNER-FIELD-001 | Low | Định nghĩa field không hợp lệ/không active vẫn submit được, gây lỗi FK | Toàn vẹn định nghĩa | Lỗi 500 khi cấu hình field; mất thời gian quản trị | Validate trước khi ghi | `VERIFIED.md:321-322` |
| PARTNER-FIELD-002 | Info | Nhãn field không unique | Chỉ là mơ hồ đặt tên | Người dùng chọn sai field khi nhập liệu | Ràng buộc nhãn trong một collection | `VERIFIED.md:324-325` |
| PARTNER-FIELD-003 | Low | UX kích hoạt collection chưa rõ | Chỉ là lifecycle UX | Quản trị tưởng đã kích hoạt nhưng chưa | Làm rõ trạng thái trên UI | `VERIFIED.md:327-328` |
| PARTNER-REL-003 | Low | Traversal quan hệ có thể đệ quy khi dữ liệu bị hỏng | Cần dữ liệu hỏng do người vận hành, không do người dùng quyền thấp | Trang quan hệ treo → mất khả dụng cục bộ | Giới hạn độ sâu và phát hiện chu trình khi đọc | `VERIFIED.md:330-331` |
| ISSUE-004 | Low | Không giới hạn độ dài tiêu đề issue | Chỉ là validation UX | Danh sách issue bị vỡ layout, khó đọc trên mobile công trường | Giới hạn độ dài + thông báo tiếng Việt | `VERIFIED.md:342-343` |
| DEPLOY-004 | Medium | Compose backup bị track (`deploy_backup_2026-07-14_142253/docker-compose.yml`) đặt `RATELIMIT_STORAGE_URI: memory://` và thiếu control hiện hành | Lệch cấu hình vận hành, không phải lỗ hổng trong đường request | Người vận hành dùng file backup → rate limiting yếu hơn khoảng 2 lần và thiếu control mới | **ĐÃ ĐÓNG**: commit `ae40172 chore: untrack old deploy config backup` xoá cả 4 file khỏi Git và thêm mục `.gitignore`; kiểm chứng lại `git ls-files \| grep -c deploy_backup` = 0 | `VERIFIED.md:384-385`; `.audit/findings-12-deploy-iac.md:151-158` |
| DEPLOY-005 | Medium | Image Cloudflared không pin digest | Chính sách hardening chuỗi cung ứng | Image upstream đổi âm thầm → hành vi mạng thay đổi | Pin digest đã review | `VERIFIED.md:387-388` |
| DEPLOY-007 | Low | Thiếu một số hardening/health ở Docker/Compose | Phòng thủ theo lớp/độ tin cậy | Sự cố phát hiện chậm hơn | Thêm healthcheck và tuỳ chọn hardening | `VERIFIED.md:393-394` |

---

## 4. Ghi chú về phạm vi

* `ROADMAP.md:44-46` (nhóm **LATER — tracked technical debt**) **không** chứa
  finding bảo mật nào. Nguyên văn nội dung: không có confirmed security finding
  nào phù hợp với LATER; các mục deployment/test/concurrency/image-runtime/
  audit-log/data-quality đã phân loại lại vẫn nằm ở `VERIFIED.md` dưới dạng công
  việc vận hành phi bảo mật. Toàn bộ nhóm (e) ở trên chính là tập hợp đó.
* `VERIFIED.md:239-243` ghi tỉ lệ phản biện: **36/76 finding gốc (47,4%)** bị
  loại, trùng lặp, không chắc chắn hoặc phi bảo mật — vượt xa ngưỡng 10% mà
  `AUDIT_RUNBOOK.md` đặt ra, nên bản audit gốc không được coi là đúng mặc định.
* Không có secret, credential, token, presigned URL, object key, bucket name hay
  dữ liệu cá nhân nào được ghi trong tài liệu này.

---

## 5. KHÔNG phải rủi ro được chấp nhận — blocker còn mở

Phần này tồn tại để không ai đọc file này như một giấy thông hành. Các mục dưới
đây **chưa được chấp nhận** và không được đưa vào §2/§3.

| # | Mục | Trạng thái đã đọc | Nguồn |
|---|---|---|---|
| 5.1 | **REPORTS-007 (Phase 11 delta)** — Medium, giới hạn ảnh/section đổi từ 3 thành 10 mà không có cập nhật hợp đồng sản phẩm được phê duyệt | **Open.** `PHASE11-DELTA-CLOSURE.md:31-35`: "Not ready for production under the currently retained AGENTS/master contract" cho tới khi chủ sản phẩm giải quyết. Cần một trong hai: khôi phục hằng số 3 duy nhất và đồng bộ mọi path/test/config, **hoặc** phê duyệt tường minh đổi hợp đồng sang 10 và cập nhật đồng thời mọi đặc tả và template | `.audit/VERIFIED-PHASE11-DELTA.md:17`; `.audit/findings-16-phase11-reports-integration.md:10-29`; `.audit/PHASE11-DELTA-CLOSURE.md:31-35` |
| 5.2 | **CONFIG-OP-001** — không thể đóng độc lập | Open cùng 5.1 (đã đăng ký ở a.1 nhưng **chỉ** như phần phụ thuộc, không phải rủi ro được chấp nhận riêng) | `.audit/VERIFIED-PHASE11-DELTA.md:18` |
| 5.3 | **DEPLOY-001** (Critical gốc) — Compose/config không đáp ứng startup storage validation | NOT A SECURITY FINDING nhưng **"operations release gate"**; `VERIFIED.md:225` nói rõ DEPLOY-001/002/003/006 vẫn cần xử lý vận hành trước khi phát hành an toàn | `.audit/VERIFIED.md:225,375-376`; `.audit/ROADMAP.md:5` |
| 5.4 | **DEPLOY-002** (High gốc) — giám sát worker; job có thể tích tụ | Như trên, operations release gate | `.audit/VERIFIED.md:225,378-379` |
| 5.5 | **DEPLOY-003** (High gốc) — mức sẵn sàng phục hồi artifact | Như trên, operations release gate | `.audit/VERIFIED.md:225,381-382` |
| 5.6 | **DEPLOY-006** (Medium gốc) — mơ hồ tài liệu triển khai | Như trên, operations release gate | `.audit/VERIFIED.md:225,390-391` |
| 5.7 | **Cổng test Python đầy đủ** — 390 test chưa có kết quả exit 0 dưới Python 3.12 | `PHASE10-CLOSURE.md:97-101`: lệnh đầy đủ bị harness kết thúc sau ~30 giây, **INCOMPLETE, not a pass**; `.venv` là Python 3.10.12. `VERIFIED-PHASE11-DELTA.md:53`: hai lần chạy pytest rộng bị dừng từ bên ngoài, cố ý không tính là passed | `.audit/PHASE10-CLOSURE.md:97-101,156,161`; `.audit/VERIFIED-PHASE11-DELTA.md:53` |
| 5.8 | **Hai dry-run sửa dữ liệu chưa chạy được** — `flask provision-project-document-roots --dry-run` và `flask cleanup-unreferenced-display-images --dry-run` đều exit 1 vì không kết nối được PostgreSQL, nên **chưa biết** có cần sửa dữ liệu staging hay không | **Vẫn mở.** Phải chạy lại cả hai dry-run trên PostgreSQL staging trước khi triển khai | `.audit/PHASE10-CLOSURE.md:121-130,155,161` |
| 5.9 | **Thư mục `deploy_backup_2026-07-14_142253/` bị track trong Git** — điều kiện thứ ba của release verdict Phase 10 | **ĐÃ ĐÓNG.** Kiểm chứng lại trên HEAD hiện tại (`ae40172 chore: untrack old deploy config backup`, branch `Phase13/Audit-log`): `git ls-files \| grep -c deploy_backup` trả về **0**. Điều kiện này không còn là blocker; giữ lại ở đây để đối chiếu với văn bản closure cũ | `.audit/PHASE10-CLOSURE.md:137,157,161` |

Kết luận phát hành đã ghi nhận: `PHASE10-CLOSURE.md:161` —
**CONDITIONAL GO TO PHASE 11 STAGING**, chỉ cho phép công việc staging/hạ tầng,
**không bao giờ là production**. Năm finding UNCERTAIN vẫn mở và có thể trở thành
blocker nếu bằng chứng staging tái hiện được tác động (xem a.2, b.4, d.1, d.2,
d.3).

---

## 6. Mâu thuẫn giữa các tài liệu nguồn — đã kiểm chứng lại với code

Ghi lại để người đọc sau không bị dẫn sai. Cả hai mục dưới đây đã được kiểm
chứng trực tiếp trên source hiện tại, không dựa vào tài liệu.

### 6.1 — Celery Beat: `FOUNDATION-B.md` sai, `PHASE10-CLOSURE.md` đúng

* `.audit/FOUNDATION-B.md:338-339` khẳng định "**no Celery beat schedule exists
  anywhere in this codebase** — no `beat_schedule` config, no periodic-task
  registration of any kind", và bảng ở cùng mục kết luận ba task cleanup
  (`reports.cleanup_expired_upload_sessions`, `media.reconcile_media_jobs`,
  `bulk_download.cleanup_expired`) không có call site `.delay()` nào nên "all
  cleanup/reconciliation is manual-only". `.audit/findings-12-deploy-iac.md:125`
  lặp lại: "There is no beat schedule".
* `.audit/PHASE10-CLOSURE.md:119` khẳng định ngược lại: cả ba task "are present
  in Beat. Required periodic schedules are therefore registered".
* **Kiểm chứng trên code hiện tại:** `PHASE10-CLOSURE.md` **đúng**.
  `app/celery_app.py:69-82` khai báo `beat_schedule` với đúng ba entry:
  `cleanup-expired-report-upload-sessions`, `reconcile-media-jobs`,
  `cleanup-expired-bulk-downloads`, mỗi entry lấy chu kỳ từ config
  (`app/config.py:148-150`: 3600s / 900s / 3600s; cùng giá trị được
  `app.config.setdefault` tại `app/__init__.py:46-47`).
  `docker-compose.yml:127,130` có service `scheduler` chạy
  `celery ... beat --schedule=/app/tmp/celerybeat-schedule`.
* **Vì sao có mâu thuẫn:** `beat_schedule` được thêm ở commit `137c79a`
  ("fix(deploy): enforce production release gate", 2026-07-28) — chính là commit
  fix CLI-001. `FOUNDATION-B.md` được viết ngày 2026-07-27, trước commit đó, nên
  nó **đúng tại thời điểm viết và đã cũ (stale) từ 2026-07-28**.
  `findings-12-deploy-iac.md:125` cũng cũ theo cùng lý do.
* **Hệ quả cho sổ đăng ký này:** Không có mục "cleanup chỉ chạy thủ công" nào
  được đăng ký như rủi ro được chấp nhận, vì tiền đề đã không còn đúng. Tuy vậy
  **vẫn cần bằng chứng vận hành** rằng service `scheduler` thực sự chạy và
  Beat phát task trên môi trường thật — đó là phần "Beat task schedule" trong
  `PHASE10-CLOSURE.md:155` và liên quan tới DEPLOY-002 (§5.4).

### 6.2 — Trùng ID `REPORTS-007` giữa hai đợt audit

* Phase 10: `REPORTS-007` = "upload audit gap", severity Low, verdict
  **NOT A SECURITY FINDING** (`.audit/VERIFIED.md:288-289`).
* Phase 11 delta: `REPORTS-007` = giới hạn ảnh/section 3-versus-10, severity
  **Medium**, trạng thái **Open** và là điều kiện chặn production
  (`.audit/VERIFIED-PHASE11-DELTA.md:17`;
  `.audit/findings-16-phase11-reports-integration.md:10-29`).
* Đây là **hai finding khác nhau dùng cùng một ID**. Trong tài liệu này chúng
  được phân biệt bằng nhãn "(Phase 10)" và "(Phase 11 delta)". Trước khi phát
  hành nên cấp lại ID cho một trong hai để tránh đóng sai finding.
