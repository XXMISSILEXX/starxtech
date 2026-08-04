# Phase 12.1 — Mốc xanh trước triển khai

Ngày chạy: 2026-08-02

## Lệnh đã chạy

```text
$ pytest -q --durations=10
500 passed, 3 skipped in 328.70s (0:05:28)
```

Ba kiểm thử PostgreSQL đã bị skip do chưa đặt các biến môi trường
`PHASE4_POSTGRES_URL` / `PHASE5_POSTGRES_URL`; đây là các skip đã có từ trước.

```text
$ npm test
32 passed, 0 failed in 475.624147ms
```

`tests_js/construction-progress.test.js` hiện có trong baseline và còn xanh;
file này được đặc tả Phase 12.1 yêu cầu xoá ở Bước 6, không phải ở Bước 0.
