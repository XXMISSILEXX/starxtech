/* Company Media direct-to-S3 POST uploader. Files never pass through Flask. */
(() => {
  const FALLBACK_LIMITS = {max_files_per_batch: 50, upload_concurrency: 3};
  const REQUIRED_LIMIT_KEYS = [
    "max_selection_files", "max_selection_bytes", "max_files_per_batch", "max_batch_bytes",
    "max_file_bytes", "max_image_bytes", "max_video_bytes", "upload_concurrency", "session_ttl_seconds",
  ];
  const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp", "gif", "heic", "heif"]);
  const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "mov", "m4v"]);
  const terminal = new Set(["succeeded", "failed", "blocked", "cancelled"]);
  const retryableStatus = new Set([0, 408, 429, 500, 502, 503, 504]);
  const nonRetryableS3Codes = new Set(["EntityTooSmall", "EntityTooLarge", "SignatureDoesNotMatch", "AccessDenied", "InvalidPolicyDocument", "RequestExpired", "ExpiredToken"]);

  const positiveInteger = (value) => Number.isInteger(value) && value > 0;
  const formatBytes = (value) => {
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
    const units = ["B", "KiB", "MiB", "GiB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const amount = bytes / (1024 ** index);
    return `${Number(amount.toFixed(2))} ${units[index]}`;
  };
  const readUploadLimits = (raw, warn = () => {}) => {
    let parsed;
    try { parsed = typeof raw === "string" ? JSON.parse(raw) : raw; } catch (_) { parsed = null; }
    const safeFallback = {...FALLBACK_LIMITS};
    if (!parsed || typeof parsed !== "object" || REQUIRED_LIMIT_KEYS.some((key) => !positiveInteger(parsed[key]))) {
      warn("Company Media upload limits payload is missing or invalid; upload is disabled until valid server limits are available.");
      return {...safeFallback, valid: false};
    }
    return {...parsed, valid: true};
  };
  const fileExtension = (file) => String(file?.name || "").split(".").pop().toLowerCase();
  const fileCategory = (file) => {
    const extension = fileExtension(file);
    if (IMAGE_EXTENSIONS.has(extension)) return "image";
    if (VIDEO_EXTENSIONS.has(extension)) return "video";
    return "unknown";
  };
  const clientFileError = (file, limits) => {
    const category = fileCategory(file);
    if (category === "unknown") return {code: "unsupported_type", message: `Tệp ${file.name} không phải là ảnh hoặc video được hỗ trợ.`, retryable: false};
    const categoryCap = category === "image" ? limits.max_image_bytes : limits.max_video_bytes;
    if (file.size > categoryCap) {
      const label = category === "image" ? "Ảnh" : "Video";
      return {code: `${category}_size_exceeded`, message: `${label} ${file.name} có dung lượng ${formatBytes(file.size)}, tối đa ${formatBytes(categoryCap)}.`, details: {actual_bytes: file.size, max_bytes: categoryCap}, retryable: false};
    }
    if (file.size > limits.max_file_bytes) return {code: "file_size_exceeded", message: `Tệp ${file.name} có dung lượng ${formatBytes(file.size)}, tối đa ${formatBytes(limits.max_file_bytes)}.`, details: {actual_bytes: file.size, max_bytes: limits.max_file_bytes}, retryable: false};
    if (file.size > limits.max_batch_bytes) return {code: "presign_batch_bytes_exceeded", message: `Tệp ${file.name} có dung lượng ${formatBytes(file.size)}, vượt giới hạn batch ${formatBytes(limits.max_batch_bytes)}.`, details: {actual_bytes: file.size, max_bytes: limits.max_batch_bytes}, retryable: false};
    return null;
  };
  const buildBatches = (items, limits) => {
    const batches = [], oversized = [];
    let batch = [], bytes = 0, byteLimited = false;
    for (const item of items) {
      const size = Number(item.file?.size ?? item.size ?? 0);
      if (!Number.isFinite(size) || size < 0 || size > limits.max_batch_bytes) { oversized.push(item); continue; }
      if (batch.length && (batch.length >= limits.max_files_per_batch || bytes + size > limits.max_batch_bytes)) {
        byteLimited ||= bytes + size > limits.max_batch_bytes;
        batches.push(batch); batch = []; bytes = 0;
      }
      batch.push(item); bytes += size;
    }
    if (batch.length) batches.push(batch);
    return {batches, oversized, byteLimited};
  };
  const evaluateSelection = (items, limits) => {
    const files = items.filter((entry) => entry.status !== "removed");
    const blocked = files.filter((entry) => entry.clientError || entry.status === "blocked");
    const valid = files.filter((entry) => !entry.clientError && entry.status !== "blocked");
    const totalBytes = files.reduce((sum, entry) => sum + entry.file.size, 0);
    const errors = [];
    if (!limits.valid) errors.push("Không thể xác minh giới hạn tải lên từ máy chủ. Vui lòng tải lại trang.");
    else {
      if (!files.length) errors.push("Hãy chọn ít nhất một tệp để tải lên.");
      if (files.length > limits.max_selection_files) errors.push(`Bạn đã chọn ${files.length} tệp, tối đa ${limits.max_selection_files} tệp.`);
      if (totalBytes > limits.max_selection_bytes) errors.push(`Tổng dung lượng ${formatBytes(totalBytes)} vượt giới hạn ${formatBytes(limits.max_selection_bytes)}.`);
    }
    return {files, valid, blocked, totalBytes, errors, batches: limits.valid ? buildBatches(valid, limits) : {batches: [], oversized: [], byteLimited: false}};
  };
  const safeText = (value, fallback) => {
    if (typeof value !== "string" || !value.trim() || /<[^>]+>|https?:\/\/|<\/?(?:Error|Code|RequestId)>/i.test(value)) return fallback;
    return value.trim();
  };
  const normalizeError = (value) => {
    const error = value && typeof value === "object" && value.error ? value.error : value;
    if (typeof error === "string") return {message: safeText(error, "Không thể xử lý yêu cầu tải lên."), details: {}, retryable: false};
    if (error && typeof error === "object") return {
      code: typeof error.code === "string" ? error.code : "",
      message: safeText(error.message || error.error_message, "Không thể xử lý yêu cầu tải lên."),
      details: error.details && typeof error.details === "object" ? error.details : {},
      retryable: error.retryable === true,
    };
    return {message: "Không thể xử lý yêu cầu tải lên.", details: {}, retryable: false};
  };
  const formatUploadError = (value, fallback) => {
    const error = normalizeError(value);
    const details = error.details || {};
    const actualFiles = details.actual_files ?? details.resulting_files;
    const maxFiles = details.max_files ?? details.declared_files;
    const actualBytes = details.actual_bytes ?? details.resulting_bytes;
    const maxBytes = details.max_bytes ?? details.declared_bytes;
    const actualMax = (actual, max, unit = "") => Number.isFinite(actual) && Number.isFinite(max) ? `${actual}${unit} / ${max}${unit}` : "";
    const byteActualMax = Number.isFinite(actualBytes) && Number.isFinite(maxBytes) ? `${formatBytes(actualBytes)} / ${formatBytes(maxBytes)}` : "";
    const messages = {
      selection_file_count_exceeded: `Bạn đã chọn ${actualMax(actualFiles, maxFiles, " tệp") || "quá nhiều tệp"}, tối đa ${maxFiles || ""} tệp.`,
      selection_total_bytes_exceeded: `Tổng dung lượng ${byteActualMax || "đã chọn"} vượt giới hạn ${formatBytes(maxBytes)}.`,
      presign_batch_file_count_exceeded: `Batch có ${actualMax(actualFiles, maxFiles, " tệp") || "quá nhiều tệp"}, tối đa ${maxFiles || ""} tệp.`,
      presign_batch_bytes_exceeded: `Dung lượng batch ${byteActualMax || "đã chọn"} vượt giới hạn ${formatBytes(maxBytes)}.`,
      file_size_exceeded: `Tệp có dung lượng ${byteActualMax || "vượt giới hạn"}.`,
      image_size_exceeded: `Ảnh có dung lượng ${byteActualMax || "vượt giới hạn"}.`,
      video_size_exceeded: `Video có dung lượng ${byteActualMax || "vượt giới hạn"}.`,
      selection_declared_file_quota_exceeded: `Số tệp khai báo ${actualMax(actualFiles, maxFiles, " tệp") || "vượt giới hạn phiên tải"}.`,
      selection_declared_byte_quota_exceeded: `Dung lượng khai báo ${byteActualMax || "vượt giới hạn phiên tải"}.`,
      selection_session_expired: "Phiên tải đã hết hạn hoặc đã hoàn tất. Hãy chọn tải lại.",
      selection_session_target_mismatch: "Phiên tải không hợp lệ cho album này.",
      idempotency_conflict: "Mã tệp đã được sử dụng cho một tệp khác.",
      upload_item_not_retryable: "Tệp này không thể thử lại. Vui lòng chọn lại tệp.",
      selection_session_expired: "Phiên tải đã hết hạn. Vui lòng chọn lại tệp để bắt đầu lại.",
      upload_session_cancelled: "Phiên tải đã được hủy.",
      upload_item_not_available: "Tệp tải lên không còn khả dụng.",
      head_verification_failed: "Không thể xác minh tệp đã tải lên. Bạn có thể tải lại tệp.",
      s3_upload_failed: "Tải lên kho lưu trữ thất bại. Vui lòng thử lại.",
    };
    return messages[error.code] || safeText(error.message, fallback || "Không thể xử lý yêu cầu tải lên.");
  };

  const exported = {FALLBACK_LIMITS, readUploadLimits, formatBytes, fileCategory, clientFileError, buildBatches, evaluateSelection, normalizeError, formatUploadError};
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  if (typeof window === "undefined" || typeof document === "undefined") return;
  window.CompanyMediaUploadUtils = exported;

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-company-media-upload]");
    if (!root) return;
    const input = root.querySelector("[data-company-media-file-input]");
    const dropzone = root.querySelector("[data-company-media-dropzone]");
    const dropzoneMessage = root.querySelector("[data-company-media-dropzone-message]");
    const choose = root.querySelector("[data-company-media-choose-files]");
    const clear = root.querySelector("[data-company-media-clear-files]");
    const start = root.querySelector("[data-company-media-start-upload]");
    const queue = root.querySelector("[data-company-media-upload-queue]");
    const validationMessage = root.querySelector("[data-upload-validation-message]");
    const summary = root.querySelector("[data-company-media-upload-summary]");
    const overlay = document.querySelector("[data-company-media-upload-overlay]");
    const entries = [];
    let uploading = false;
    let activeSessionId = null;
    let cancelRequested = false;
    let focusBeforeModal = null;
    const uploadLimits = readUploadLimits(root.dataset.companyMediaUploadLimits, (message) => console.warn(message));
    const concurrency = uploadLimits.upload_concurrency;
    const maxAttempts = 3;
    const modal = window.bootstrap?.Modal ? new window.bootstrap.Modal(overlay, {backdrop: "static", keyboard: false}) : null;
    const newId = () => globalThis.crypto?.randomUUID?.() || `company-media-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const csrfHeaders = {"Content-Type": "application/json", "X-CSRFToken": root.dataset.csrfToken};
    const selected = () => entries.filter((entry) => entry.status !== "removed");
    const pending = () => selected().filter((entry) => entry.status === "pending");
    const setText = (scope, selector, value) => { const node = scope?.querySelector(selector); if (node) node.textContent = String(value); };
    const setDisabled = (node, disabled) => { if (!node) return; node.disabled = disabled; node.setAttribute("aria-disabled", String(disabled)); };
    const selectionState = () => {
      const state = evaluateSelection(entries, uploadLimits);
      return {...state, clientBlocked: state.blocked};
    };
    const renderSummary = () => {
      const state = selectionState();
      setText(root, "[data-selected-count]", state.files.length);
      setText(root, "[data-selected-max]", uploadLimits.valid ? uploadLimits.max_selection_files : "—");
      setText(root, "[data-selected-bytes]", formatBytes(state.totalBytes));
      setText(root, "[data-selected-bytes-max]", uploadLimits.valid ? formatBytes(uploadLimits.max_selection_bytes) : "—");
      setText(root, "[data-valid-count]", state.valid.length);
      setText(root, "[data-blocked-count]", state.clientBlocked.length);
      if (uploadLimits.valid) {
        setText(root, "[data-limit-image]", formatBytes(uploadLimits.max_image_bytes));
        setText(root, "[data-limit-video]", formatBytes(uploadLimits.max_video_bytes));
        setText(root, "[data-limit-batch-files]", uploadLimits.max_files_per_batch);
        setText(root, "[data-limit-batch-bytes]", formatBytes(uploadLimits.max_batch_bytes));
        setText(root, "[data-limit-concurrency]", uploadLimits.upload_concurrency);
      }
      const estimate = root.querySelector("[data-batch-estimate]");
      if (estimate) {
        const count = state.batches.batches.length;
        estimate.hidden = count < 2;
        estimate.textContent = count >= 2 ? ` · ${state.valid.length} tệp sẽ được chia thành ${count} batch${state.batches.byteLimited ? " theo giới hạn dung lượng" : ""}.` : "";
      }
      const ratio = uploadLimits.valid ? Math.max(state.files.length / uploadLimits.max_selection_files, state.totalBytes / uploadLimits.max_selection_bytes) : 0;
      summary?.classList.toggle("is-near-limit", ratio >= .8 && !state.errors.slice(1).length);
      summary?.classList.toggle("is-exceeded", state.errors.some((message) => !message.startsWith("Hãy chọn")));
      root.dataset.companyMediaUploadState = uploading ? "uploading" : state.errors.length ? "invalid" : state.clientBlocked.length ? "partial" : ratio >= .8 ? "near-limit" : "normal";
      if (validationMessage) { validationMessage.hidden = !state.errors.length; validationMessage.textContent = state.errors[0] || ""; }
      const status = root.querySelector("[data-upload-selection-status]");
      if (status) status.textContent = uploading ? "Đang tải lên; không thể thay đổi lựa chọn." : state.errors.length ? "Lựa chọn không hợp lệ; chưa thể tải lên." : state.clientBlocked.length ? "Một số tệp bị chặn; chỉ các tệp hợp lệ sẽ được tải lên." : ratio >= .8 ? "Gần giới hạn số lượng hoặc dung lượng." : state.files.length ? "Lựa chọn trong giới hạn." : "Chưa chọn tệp.";
      const canUpload = !uploading && !state.errors.length && pending().length > 0;
      setDisabled(start, !canUpload);
      setDisabled(clear, uploading || !state.files.length);
      return state;
    };
    const renderQueue = () => {
      queue.replaceChildren();
      selected().forEach((entry) => {
        const item = document.createElement("li");
        item.className = "list-group-item d-flex justify-content-between gap-2";
        const content = document.createElement("div"); content.className = "company-media-upload-name";
        const status = {pending: "Chờ tải", ready: "Chờ tải", uploading: "Đang tải", completing: "Đang xác minh", succeeded: "Hoàn tất", failed: "Thất bại", blocked: "Bị chặn", cancelled: "Đã hủy"}[entry.status] || entry.status;
        const category = fileCategory(entry.file) === "image" ? "Ảnh" : fileCategory(entry.file) === "video" ? "Video" : "Không hỗ trợ";
        const name = document.createElement("div"); name.className = "fw-semibold"; name.textContent = entry.file.name;
        const meta = document.createElement("div"); meta.className = "small text-muted"; meta.textContent = `${formatBytes(entry.file.size)} · ${category} · ${status}${["uploading", "completing"].includes(entry.status) ? ` ${Math.round((entry.loaded || 0) * 100 / entry.file.size)}%` : ""}`;
        content.append(name, meta);
        if (entry.error || entry.clientError) {
          const error = document.createElement("div"); error.className = "small text-danger mt-1"; error.id = `company-media-upload-error-${entry.clientFileId}`; error.textContent = entry.error || entry.clientError.message; content.append(error); item.setAttribute("aria-describedby", error.id);
        }
        item.append(content);
        if (!uploading && ["pending", "blocked"].includes(entry.status)) {
          const remove = document.createElement("button"); remove.type = "button"; remove.className = "btn btn-sm btn-outline-danger"; remove.textContent = "Xóa"; remove.setAttribute("aria-label", `Xóa ${entry.file.name}`);
          remove.addEventListener("click", () => { entry.status = "removed"; renderQueue(); }); item.append(remove);
        }
        queue.append(item);
      });
      renderSummary();
    };
    const safeReason = (code, fallback = "Không thể tải tệp. Vui lòng thử lại.") => ({
      EntityTooSmall: "Tệp không phù hợp với giới hạn upload của kho lưu trữ.", EntityTooLarge: "Tệp vượt giới hạn upload của kho lưu trữ.",
      SignatureDoesNotMatch: "Phiên tải đã không còn hợp lệ. Vui lòng thử lại.", AccessDenied: "Không được phép tải tệp này.",
      InvalidPolicyDocument: "Phiên tải không hợp lệ. Vui lòng thử lại.", RequestExpired: "Phiên tải đã hết hạn. Vui lòng thử lại.", ExpiredToken: "Phiên tải đã hết hạn. Vui lòng thử lại.",
    }[code] || fallback);
    const parseS3Error = (body) => {
      try { const xml = new DOMParser().parseFromString(body || "", "application/xml"); return {code: xml.querySelector("Code")?.textContent?.trim() || ""}; } catch (_) { return {code: ""}; }
    };
    const overlayResults = () => overlay?.querySelector("[data-upload-overlay-results]");
    const renderOverlay = (phase = "uploading", message = "") => {
      if (!overlay) return;
      const files = selected(); const count = (state) => files.filter((entry) => entry.status === state).length;
      const uploadedBytes = files.reduce((sum, entry) => sum + Math.min(entry.loaded || 0, entry.file.size), 0);
      const totalBytes = files.reduce((sum, entry) => sum + entry.file.size, 0); const percent = totalBytes ? Math.round(uploadedBytes * 100 / totalBytes) : 0;
      setText(overlay, "[data-upload-total]", files.length); setText(overlay, "[data-upload-ready]", files.filter((entry) => !["pending", "blocked"].includes(entry.status)).length);
      setText(overlay, "[data-upload-blocked]", count("blocked")); setText(overlay, "[data-upload-pending]", count("pending") + count("ready"));
      setText(overlay, "[data-upload-uploading]", count("uploading") + count("completing")); setText(overlay, "[data-upload-succeeded]", count("succeeded")); setText(overlay, "[data-upload-failed]", count("failed"));
      setText(overlay, "[data-upload-overlay-message]", message);
      const progress = overlay.querySelector("[data-upload-overall-progress]"); if (progress) { progress.style.width = `${percent}%`; progress.textContent = totalBytes ? `${percent}%` : ""; progress.setAttribute("aria-valuenow", String(percent)); }
      const current = files.find((entry) => ["uploading", "completing"].includes(entry.status)); setText(overlay, "[data-upload-current-file]", current ? `Đang xử lý: ${current.file.name} (${Math.round((current.loaded || 0) * 100 / current.file.size)}%)` : "");
      const title = overlay.querySelector("[data-upload-overlay-title]"); if (title) title.textContent = phase === "done" ? "Kết quả tải lên" : phase === "preparing" ? "Chuẩn bị tải lên" : "Đang tải lên";
      const results = overlayResults();
      if (results) { results.replaceChildren(); files.filter((entry) => ["blocked", "failed"].includes(entry.status)).forEach((entry) => { const row = document.createElement("li"); row.className = `list-group-item ${entry.status === "blocked" ? "list-group-item-warning" : "list-group-item-danger"}`; row.textContent = `${entry.file.name} — ${entry.status === "blocked" ? "Bị chặn" : "Lỗi"}: ${entry.error || entry.clientError?.message || "Không thể tải tệp."}`; results.append(row); }); }
      const retry = overlay.querySelector("[data-upload-retry-failed]"); const close = overlay.querySelector("[data-upload-close]"); const cancel = overlay.querySelector("[data-upload-cancel]");
      if (retry) retry.hidden = phase !== "done" || !files.some((entry) => entry.status === "failed"); if (close) close.hidden = phase !== "done";
      if (cancel) { cancel.hidden = phase === "done" || !Number.isInteger(activeSessionId); setDisabled(cancel, cancelRequested); }
    };
    const api = async (url, body) => {
      const response = await fetch(url, {method: "POST", credentials: "same-origin", headers: csrfHeaders, body: JSON.stringify(body)});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) { const error = normalizeError(payload.error || payload.error_message); throw Object.assign(new Error(formatUploadError(error)), error); }
      return payload;
    };
    const sessionUrl = () => root.dataset.presignUrl.replace("/presign-batch", "/upload-selection-sessions");
    const finalizeUrl = (sessionId) => `${sessionUrl()}/${sessionId}/finalize`;
    const cancelUrl = (sessionId) => root.dataset.presignUrl.replace("/files/presign-batch", `/upload-sessions/${sessionId}/cancel`);
    const delay = (attempt) => new Promise((resolve) => window.setTimeout(resolve, Math.round((250 * 2 ** attempt) + Math.random() * 250)));
    const directPost = (entry) => new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); const form = new FormData(); Object.entries(entry.presign.fields || {}).forEach(([key, value]) => form.append(key, value)); form.append("file", entry.file);
      xhr.open(entry.presign.method || "POST", entry.presign.url, true);
      xhr.upload.onprogress = (event) => { if (!event.lengthComputable) return; entry.loaded = event.loaded; renderOverlay("uploading", "Đang tải tệp lên kho lưu trữ."); };
      xhr.onload = () => { if (xhr.status >= 200 && xhr.status < 300) { entry.loaded = entry.file.size; resolve(); return; } const error = parseS3Error(xhr.responseText); reject(Object.assign(new Error(safeReason(error.code, "Kho lưu trữ từ chối tệp.")), {status: xhr.status, code: "s3_upload_failed", providerCode: error.code})); };
      xhr.onerror = () => reject(Object.assign(new Error("Mất kết nối khi tải tệp."), {status: 0, code: "s3_upload_failed", providerCode: "NetworkError"})); xhr.onabort = () => reject(Object.assign(new Error("Tải tệp đã bị hủy."), {status: 0, code: "s3_upload_failed", providerCode: "AbortError"})); xhr.send(form);
    });
    const uploadOne = async (entry) => {
      entry.status = "uploading"; entry.loaded = 0; renderQueue(); renderOverlay("uploading", "Đang tải tệp lên kho lưu trữ."); let lastError;
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) { try { await directPost(entry); lastError = null; break; } catch (error) { lastError = error; if (nonRetryableS3Codes.has(error.providerCode) || !retryableStatus.has(error.status) || attempt === maxAttempts - 1) break; await delay(attempt); } }
      if (lastError) throw lastError; entry.status = "completing"; renderQueue(); renderOverlay("uploading", "Đang xác minh tệp đã tải."); await api(root.dataset.completeUrl, {upload_batch_item_id: entry.itemId}); entry.status = "succeeded"; entry.error = ""; entry.loaded = entry.file.size;
    };
    const runWithConcurrency = async (items) => { let cursor = 0; const worker = async () => { while (cursor < items.length) { const entry = items[cursor++]; try { await uploadOne(entry); } catch (error) { entry.status = "failed"; entry.error = formatUploadError(error, safeReason(error.code, error.message)); } renderQueue(); renderOverlay("uploading", "Đang tải tệp lên kho lưu trữ."); } }; await Promise.all(Array.from({length: Math.min(concurrency, items.length)}, worker)); };
    const prepare = async (items) => {
      const retainedSessionIds = new Set(items.map((entry) => entry.sessionId).filter(Number.isInteger));
      let sessionId;
      if (retainedSessionIds.size === 1) sessionId = [...retainedSessionIds][0];
      else {
        const session = await api(sessionUrl(), {file_count: items.length, total_size_bytes: items.reduce((sum, entry) => sum + entry.file.size, 0)});
        sessionId = session.selection_session_id;
      }
      items.forEach((entry) => { entry.sessionId = sessionId; entry.status = "pending"; });
      const {batches, oversized} = buildBatches(items, uploadLimits);
      oversized.forEach((entry) => { entry.status = "blocked"; entry.error = `Tệp vượt giới hạn batch ${formatBytes(uploadLimits.max_batch_bytes)}.`; });
      for (const group of batches) {
        const result = await api(root.dataset.presignUrl, {selection_session_id: sessionId, files: group.map((entry) => ({client_file_id: entry.clientFileId, filename: entry.file.name, mime_type: entry.file.type, size: entry.file.size}))});
        const byClientId = new Map(result.items.map((item) => [item.client_file_id, item]));
        group.forEach((entry) => { const item = byClientId.get(entry.clientFileId); if (!item) { entry.status = "failed"; entry.error = "Server không trả thông tin cho tệp này."; return; } if (!item.accepted) { entry.status = "blocked"; entry.error = formatUploadError(item.error || item.error_message, "Tệp không được chấp nhận."); return; } entry.itemId = item.upload_batch_item_id; entry.presign = item; if (item.status === "completed") { entry.status = "succeeded"; entry.loaded = entry.file.size; entry.error = ""; return; } entry.status = "ready"; });
        renderQueue(); renderOverlay("preparing", "Đang kiểm tra tệp đã chọn.");
      }
      return sessionId;
    };
    const finalize = async (sessionId, sessionEntries) => api(finalizeUrl(sessionId), {failed_upload_batch_item_ids: sessionEntries.filter((entry) => entry.status === "failed" && Number.isInteger(entry.itemId)).map((entry) => entry.itemId)});
    const upload = async (items) => {
      if (uploading || !items.length || selectionState().errors.length) return;
      cancelRequested = false; uploading = true; focusBeforeModal = document.activeElement; setDisabled(choose, true); setDisabled(clear, true); dropzone.classList.add("disabled"); dropzone.setAttribute("aria-disabled", "true"); modal?.show(); renderQueue(); renderOverlay("preparing", "Đang kiểm tra tệp đã chọn."); let sessionId;
      try { sessionId = await prepare(items); activeSessionId = sessionId; renderOverlay("preparing", "Đang kiểm tra tệp đã chọn."); await runWithConcurrency(items.filter((entry) => entry.status === "ready")); if (!cancelRequested) await finalize(sessionId, items); }
      catch (error) { const message = formatUploadError(error, "Không thể chuẩn bị tải tệp."); items.filter((entry) => !terminal.has(entry.status)).forEach((entry) => { entry.status = "failed"; entry.error = message; }); if (sessionId && !cancelRequested && error.code !== "selection_session_expired") { try { await finalize(sessionId, items); } catch (_) { /* The result remains visible. */ } } }
      uploading = false; activeSessionId = null; setDisabled(choose, false); dropzone.classList.remove("disabled"); dropzone.setAttribute("aria-disabled", "false"); renderQueue(); renderOverlay("done", cancelRequested ? "Đã hủy phần tải lên còn lại. Các tệp đã tải thành công vẫn được giữ." : "Đã hoàn tất tải lên. Kiểm tra kết quả trước khi đóng.");
    };
    const addFiles = (files) => { if (uploading) return; [...files].forEach((file) => { const clientError = uploadLimits.valid ? clientFileError(file, uploadLimits) : null; entries.push({clientFileId: newId(), file, status: clientError ? "blocked" : "pending", clientError, loaded: 0, error: clientError?.message || ""}); }); renderQueue(); };
    const openPicker = () => { if (!uploading) input.click(); };
    choose.addEventListener("click", openPicker); clear.addEventListener("click", () => { if (!uploading) { entries.splice(0, entries.length); renderQueue(); } }); dropzone.addEventListener("click", openPicker);
    dropzone.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openPicker(); } }); input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
    ["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (event) => { if (uploading) return; event.preventDefault(); dropzone.classList.add("dragover"); dropzoneMessage.textContent = "Thả tệp để tải lên"; }));
    ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.remove("dragover"); dropzoneMessage.textContent = "Kéo thả ảnh/video hoặc bấm để chọn"; }));
    dropzone.addEventListener("drop", (event) => { if (!uploading) addFiles(event.dataTransfer.files); }); start.addEventListener("click", () => upload(pending()));
    overlay?.querySelector("[data-upload-retry-failed]")?.addEventListener("click", () => { const failed = selected().filter((entry) => entry.status === "failed"); failed.forEach((entry) => { entry.presign = null; entry.status = "pending"; entry.loaded = 0; entry.error = ""; }); upload(failed); });
    overlay?.querySelector("[data-upload-cancel]")?.addEventListener("click", async () => {
      if (!Number.isInteger(activeSessionId) || cancelRequested) return;
      if (!window.confirm("Hủy phần tải lên còn lại. Các tệp đã tải thành công vẫn được giữ.")) return;
      cancelRequested = true; renderOverlay("uploading", "Đang hủy phần tải lên còn lại.");
      try {
        const result = await api(cancelUrl(activeSessionId), {});
        selected().filter((entry) => !terminal.has(entry.status)).forEach((entry) => { entry.status = "cancelled"; entry.error = ""; });
        renderQueue(); renderOverlay("done", result.idempotent_replay ? "Phiên tải đã được hủy trước đó." : "Đã hủy phần tải lên còn lại. Các tệp đã tải thành công vẫn được giữ.");
      } catch (error) {
        cancelRequested = false; renderOverlay("uploading", formatUploadError(error, "Không thể hủy phiên tải. Vui lòng thử lại."));
      }
    });
    overlay?.querySelector("[data-upload-close]")?.addEventListener("click", () => { modal?.hide(); if (selected().some((entry) => entry.status === "succeeded")) window.location.reload(); });
    overlay?.addEventListener("hidden.bs.modal", () => focusBeforeModal?.focus());
    renderQueue();
  });
})();
