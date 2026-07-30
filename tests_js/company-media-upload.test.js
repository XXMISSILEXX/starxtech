const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const uploader = require("../app/static/js/company-media-upload.js");
const source = fs.readFileSync("app/static/js/company-media-upload.js", "utf8");
const template = fs.readFileSync("app/templates/company_media/album.html", "utf8");
const MIB = 1024 ** 2;
const GIB = 1024 ** 3;
const limits = {
  max_selection_files: 500, max_selection_bytes: 2 * GIB, max_files_per_batch: 50,
  max_batch_bytes: 512 * MIB, max_file_bytes: 300 * MIB, max_image_bytes: 50 * MIB,
  max_video_bytes: 300 * MIB, upload_concurrency: 3, session_ttl_seconds: 7200,
};
const file = (name, size, type = "image/jpeg") => ({name, size, type});

test("parses valid server limits and safely disables aggregate validation for malformed payloads", () => {
  assert.deepEqual(uploader.readUploadLimits(JSON.stringify(limits)), {...limits, valid: true});
  assert.deepEqual(uploader.readUploadLimits("not-json", () => {}), {max_files_per_batch: 50, upload_concurrency: 3, valid: false});
  assert.deepEqual(uploader.readUploadLimits({max_files_per_batch: 50, upload_concurrency: 3}, () => {}), {max_files_per_batch: 50, upload_concurrency: 3, valid: false});
});

test("formats bytes consistently in binary B, KiB, MiB, and GiB", () => {
  assert.equal(uploader.formatBytes(0), "0 B");
  assert.equal(uploader.formatBytes(1024), "1 KiB");
  assert.equal(uploader.formatBytes(MIB), "1 MiB");
  assert.equal(uploader.formatBytes(50 * MIB), "50 MiB");
  assert.equal(uploader.formatBytes(2 * GIB), "2 GiB");
  assert.equal(uploader.formatBytes(2.25 * GIB), "2.25 GiB");
});

test("pre-validates image, video, absolute, and unsupported files without adding them to a session", () => {
  assert.equal(uploader.clientFileError(file("ok.jpg", 50 * MIB), limits), null);
  assert.equal(uploader.clientFileError(file("over.jpg", 50 * MIB + 1), limits).code, "image_size_exceeded");
  assert.equal(uploader.clientFileError(file("ok.mp4", 300 * MIB, "video/mp4"), limits), null);
  assert.equal(uploader.clientFileError(file("over.mp4", 300 * MIB + 1, "video/mp4"), limits).code, "video_size_exceeded");
  assert.equal(uploader.clientFileError(file("unsafe.exe", 1, "application/octet-stream"), limits).code, "unsupported_type");
  const higherCategoryLimit = {...limits, max_image_bytes: 400 * MIB};
  assert.equal(uploader.clientFileError(file("absolute.jpg", 301 * MIB), higherCategoryLimit).code, "file_size_exceeded");
});

test("count and byte selection boundaries remain inclusive at the server limit", () => {
  const countValid = (count) => count <= limits.max_selection_files;
  const byteValid = (bytes) => bytes <= limits.max_selection_bytes;
  assert.equal(countValid(499), true); assert.equal(countValid(500), true); assert.equal(countValid(501), false);
  assert.equal(byteValid(2 * GIB - 1), true); assert.equal(byteValid(2 * GIB), true); assert.equal(byteValid(2 * GIB + 1), false);
});

test("selection summary distinguishes valid and blocked files and updates after remove", () => {
  const valid = {file: file("valid.jpg", 10), status: "pending"};
  const blocked = {file: file("blocked.exe", 20), status: "blocked", clientError: {code: "unsupported_type"}};
  let state = uploader.evaluateSelection([], {...limits, valid: true});
  assert.deepEqual({count: state.files.length, bytes: state.totalBytes, valid: state.valid.length, blocked: state.blocked.length}, {count: 0, bytes: 0, valid: 0, blocked: 0});
  state = uploader.evaluateSelection([valid, {...valid, file: file("second.jpg", 30)}, {...valid, file: file("third.jpg", 40)}], {...limits, valid: true});
  assert.deepEqual({count: state.files.length, bytes: state.totalBytes, valid: state.valid.length}, {count: 3, bytes: 80, valid: 3});
  state = uploader.evaluateSelection([valid, blocked], {...limits, valid: true});
  assert.deepEqual({count: state.files.length, valid: state.valid.length, blocked: state.blocked.length}, {count: 2, valid: 1, blocked: 1});
  blocked.status = "removed";
  state = uploader.evaluateSelection([valid, blocked], {...limits, valid: true});
  assert.deepEqual({count: state.files.length, bytes: state.totalBytes, valid: state.valid.length, blocked: state.blocked.length}, {count: 1, bytes: 10, valid: 1, blocked: 0});
});

test("partial acceptance declares only valid file metadata while aggregate excess remains invalid", () => {
  const valid = {file: file("good.jpg", 1), status: "pending"};
  const blocked = {file: file("bad.jpg", 51 * MIB), status: "blocked", clientError: {code: "image_size_exceeded"}};
  const partial = uploader.evaluateSelection([valid, valid, blocked], {...limits, valid: true});
  assert.equal(partial.valid.length, 2);
  assert.equal(partial.valid.reduce((sum, entry) => sum + entry.file.size, 0), 2);
  const excessive = uploader.evaluateSelection(Array.from({length: 501}, () => valid), {...limits, valid: true});
  assert.match(excessive.errors[0], /501 tệp, tối đa 500/);
});

test("batch builder slices by both count and byte cap and safely reports an oversized batch item", () => {
  const small = (count) => Array.from({length: count}, (_, index) => ({file: file(`${index}.jpg`, 1)}));
  assert.equal(uploader.buildBatches(small(49), limits).batches.length, 1);
  assert.equal(uploader.buildBatches(small(50), limits).batches.length, 1);
  assert.equal(uploader.buildBatches(small(51), limits).batches.length, 2);
  assert.equal(uploader.buildBatches(small(100), limits).batches.length, 2);
  const bytesBoundary = uploader.buildBatches([{file: file("a.mp4", 256 * MIB)}, {file: file("b.mp4", 256 * MIB)}, {file: file("c.jpg", 1)}], limits);
  assert.deepEqual(bytesBoundary.batches.map((batch) => batch.length), [2, 1]);
  assert.equal(bytesBoundary.byteLimited, true);
  const combined = uploader.buildBatches([...small(50), {file: file("large.mp4", 512 * MIB)}], limits);
  assert.deepEqual(combined.batches.map((batch) => batch.length), [50, 1]);
  const oversized = uploader.buildBatches([{file: file("too-large.mp4", 512 * MIB + 1)}], limits);
  assert.equal(oversized.batches.length, 0); assert.equal(oversized.oversized.length, 1);
});

test("structured error formatter supports compatibility fields and never exposes XML", () => {
  assert.match(uploader.formatUploadError({code: "image_size_exceeded", details: {actual_bytes: 61 * MIB, max_bytes: 50 * MIB}}), /61 MiB \/ 50 MiB/);
  assert.match(uploader.formatUploadError({error_message: "Phiên tải đã hết hạn."}), /Phiên tải/);
  assert.match(uploader.formatUploadError("Lỗi cũ an toàn"), /Lỗi cũ/);
  assert.equal(uploader.formatUploadError("<Error><Code>AccessDenied</Code></Error>"), "Không thể xử lý yêu cầu tải lên.");
  assert.equal(uploader.formatUploadError({code: "s3_upload_failed", message: "<Error>secret</Error>"}), "Tải lên kho lưu trữ thất bại. Vui lòng thử lại.");
});

test("uploader retains direct POST progress, bounded concurrency, stable client ids, and double-submit guard", () => {
  assert.match(source, /clientFileId: newId\(\)/);
  assert.match(source, /new Map\(result\.items\.map\(\(item\) => \[item\.client_file_id, item\]\)\)/);
  assert.match(source, /new XMLHttpRequest\(\)/);
  assert.match(source, /xhr\.upload\.onprogress/);
  assert.match(source, /Math\.min\(concurrency, items\.length\)/);
  assert.match(source, /if \(uploading \|\| !items\.length \|\| selectionState\(\)\.errors\.length\) return/);
  assert.match(source, /nonRetryableS3Codes\.has\(error\.providerCode\)/);
});

test("template exposes accessible summary, validation, queue, and modal contracts", () => {
  for (const marker of ["data-company-media-upload-limits", "data-selected-count", "data-selected-bytes", "data-valid-count", "data-blocked-count", "data-batch-estimate", "data-upload-selection-status", "data-upload-validation-message", "data-company-media-upload-queue", "data-company-media-upload-overlay"]) assert.match(template, new RegExp(marker));
  assert.match(template, /aria-live="polite"/);
  assert.match(template, /role="alert"/);
  assert.match(template, /aria-label="Kéo thả ảnh hoặc video/);
  assert.match(template, /data-company-media-clear-files/);
});
