/* Company Media direct-to-S3 POST uploader. Files never pass through Flask. */
document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-company-media-upload]");
  if (!root) return;

  const input = root.querySelector("[data-company-media-file-input]");
  const dropzone = root.querySelector("[data-company-media-dropzone]");
  const dropzoneMessage = root.querySelector("[data-company-media-dropzone-message]");
  const choose = root.querySelector("[data-company-media-choose-files]");
  const start = root.querySelector("[data-company-media-start-upload]");
  const queue = root.querySelector("[data-company-media-upload-queue]");
  const overlay = document.querySelector("[data-company-media-upload-overlay]");
  const entries = [];
  const concurrency = 3;
  const maxAttempts = 3;
  const modal = window.bootstrap?.Modal ? new window.bootstrap.Modal(overlay, {backdrop: "static", keyboard: false}) : null;

  const newId = () => globalThis.crypto?.randomUUID?.() || `company-media-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const formatSize = (size) => size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`;
  const csrfHeaders = {"Content-Type": "application/json", "X-CSRFToken": root.dataset.csrfToken};
  const terminal = new Set(["succeeded", "failed", "blocked"]);
  const retryableStatus = new Set([0, 408, 429, 500, 502, 503, 504]);
  const nonRetryableS3Codes = new Set(["EntityTooSmall", "EntityTooLarge", "SignatureDoesNotMatch", "AccessDenied", "InvalidPolicyDocument", "RequestExpired", "ExpiredToken"]);

  const selected = () => entries.filter((entry) => entry.status !== "removed");
  const accepted = () => selected().filter((entry) => entry.itemId);
  const waiting = () => selected().filter((entry) => ["pending", "ready"].includes(entry.status));
  const setText = (selector, value) => { const node = overlay?.querySelector(selector); if (node) node.textContent = String(value); };

  const safeReason = (code, fallback = "Không thể tải tệp. Vui lòng thử lại.") => ({
    EntityTooSmall: "Tệp không phù hợp với giới hạn upload của kho lưu trữ.",
    EntityTooLarge: "Tệp vượt giới hạn upload của kho lưu trữ.",
    SignatureDoesNotMatch: "Phiên tải đã không còn hợp lệ. Vui lòng thử lại.",
    AccessDenied: "Không được phép tải tệp này.",
    InvalidPolicyDocument: "Phiên tải không hợp lệ. Vui lòng thử lại.",
    RequestExpired: "Phiên tải đã hết hạn. Vui lòng thử lại.",
    ExpiredToken: "Phiên tải đã hết hạn. Vui lòng thử lại.",
  }[code] || fallback);

  const parseS3Error = (body) => {
    try {
      const xml = new DOMParser().parseFromString(body || "", "application/xml");
      return {
        code: xml.querySelector("Code")?.textContent?.trim() || "",
        requestId: xml.querySelector("RequestId")?.textContent?.trim() || "",
      };
    } catch (_) { return {code: "", requestId: ""}; }
  };

  const overlayResults = () => overlay?.querySelector("[data-upload-overlay-results]");
  const renderOverlay = (phase = "uploading", message = "") => {
    if (!overlay) return;
    const files = selected();
    const count = (state) => files.filter((entry) => entry.status === state).length;
    const acceptedFiles = files.filter((entry) => !["pending", "blocked", "removed"].includes(entry.status)).length;
    const uploadedBytes = files.reduce((sum, entry) => sum + Math.min(entry.loaded || 0, entry.file.size), 0);
    const totalBytes = files.reduce((sum, entry) => sum + entry.file.size, 0);
    const percent = totalBytes ? Math.round(uploadedBytes * 100 / totalBytes) : 0;
    setText("[data-upload-total]", files.length);
    setText("[data-upload-ready]", acceptedFiles);
    setText("[data-upload-blocked]", count("blocked"));
    setText("[data-upload-pending]", count("pending") + count("ready"));
    setText("[data-upload-uploading]", count("uploading") + count("completing"));
    setText("[data-upload-succeeded]", count("succeeded"));
    setText("[data-upload-failed]", count("failed"));
    setText("[data-upload-overlay-message]", message);
    const progress = overlay.querySelector("[data-upload-overall-progress]");
    if (progress) { progress.style.width = `${percent}%`; progress.textContent = totalBytes ? `${percent}%` : ""; }
    const current = files.find((entry) => ["uploading", "completing"].includes(entry.status));
    setText("[data-upload-current-file]", current ? `Đang xử lý: ${current.file.name} (${Math.round((current.loaded || 0) * 100 / current.file.size)}%)` : "");
    const title = overlay.querySelector("[data-upload-overlay-title]");
    if (title) title.textContent = phase === "done" ? "Kết quả tải lên" : phase === "preparing" ? "Chuẩn bị tải lên" : "Đang tải lên";
    const results = overlayResults();
    if (results) {
      results.replaceChildren();
      files.filter((entry) => ["blocked", "failed"].includes(entry.status)).forEach((entry) => {
        const item = document.createElement("li");
        item.className = `list-group-item ${entry.status === "blocked" ? "list-group-item-warning" : "list-group-item-danger"}`;
        item.textContent = `${entry.file.name} — ${entry.status === "blocked" ? "Bị chặn" : "Lỗi"}: ${entry.error || "Không thể tải tệp."}`;
        results.append(item);
      });
    }
    const retry = overlay.querySelector("[data-upload-retry-failed]");
    const close = overlay.querySelector("[data-upload-close]");
    if (retry) retry.hidden = phase !== "done" || !files.some((entry) => entry.status === "failed");
    if (close) close.hidden = phase !== "done";
  };

  const renderQueue = () => {
    queue.replaceChildren();
    selected().forEach((entry) => {
      const item = document.createElement("li");
      item.className = "list-group-item d-flex justify-content-between gap-2 align-items-center";
      const label = document.createElement("span");
      const status = {pending: "Chờ tải lên", ready: "Sẵn sàng", uploading: "Đang tải", completing: "Đang xác minh", succeeded: "Hoàn tất", failed: "Lỗi", blocked: "Bị chặn"}[entry.status] || entry.status;
      const progress = ["uploading", "completing"].includes(entry.status) ? ` ${Math.round((entry.loaded || 0) * 100 / entry.file.size)}%` : "";
      label.textContent = `${entry.file.name} (${formatSize(entry.file.size)}) — ${status}${progress}${entry.error ? `: ${entry.error}` : ""}`;
      item.append(label);
      if (entry.status === "pending") {
        const remove = document.createElement("button");
        remove.type = "button"; remove.className = "btn btn-sm btn-outline-danger"; remove.textContent = "Xóa";
        remove.addEventListener("click", () => { entry.status = "removed"; renderQueue(); });
        item.append(remove);
      }
      queue.append(item);
    });
    start.disabled = !selected().some((entry) => entry.status === "pending");
  };

  const api = async (url, body) => {
    const response = await fetch(url, {method: "POST", credentials: "same-origin", headers: csrfHeaders, body: JSON.stringify(body)});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || "Không thể xử lý yêu cầu tải lên.");
    return payload;
  };

  const sessionUrl = () => root.dataset.presignUrl.replace("/presign-batch", "/upload-selection-sessions");
  const finalizeUrl = (sessionId) => `${sessionUrl()}/${sessionId}/finalize`;
  const chunks = (items, size) => Array.from({length: Math.ceil(items.length / size)}, (_, index) => items.slice(index * size, (index + 1) * size));
  const delay = (attempt) => new Promise((resolve) => window.setTimeout(resolve, Math.round((250 * 2 ** attempt) + Math.random() * 250)));

  const directPost = (entry) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    Object.entries(entry.presign.fields || {}).forEach(([key, value]) => form.append(key, value));
    form.append("file", entry.file);
    xhr.open(entry.presign.method || "POST", entry.presign.url, true);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      entry.loaded = event.loaded;
      renderOverlay("uploading", "Đang tải tệp lên kho lưu trữ.");
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { entry.loaded = entry.file.size; resolve(); return; }
      const error = parseS3Error(xhr.responseText);
      reject(Object.assign(new Error(safeReason(error.code, "Kho lưu trữ từ chối tệp.")), {status: xhr.status, code: error.code, requestId: error.requestId}));
    };
    xhr.onerror = () => reject(Object.assign(new Error("Mất kết nối khi tải tệp."), {status: 0, code: "NetworkError"}));
    xhr.onabort = () => reject(Object.assign(new Error("Tải tệp đã bị hủy."), {status: 0, code: "AbortError"}));
    xhr.send(form);
  });

  const uploadOne = async (entry) => {
    entry.status = "uploading"; entry.loaded = 0; renderQueue(); renderOverlay("uploading", "Đang tải tệp lên kho lưu trữ.");
    let lastError;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try { await directPost(entry); lastError = null; break; }
      catch (error) {
        lastError = error;
        if (nonRetryableS3Codes.has(error.code) || !retryableStatus.has(error.status) || attempt === maxAttempts - 1) break;
        await delay(attempt);
      }
    }
    if (lastError) throw lastError;
    entry.status = "completing"; renderQueue(); renderOverlay("uploading", "Đang xác minh tệp đã tải.");
    await api(root.dataset.completeUrl, {upload_batch_item_id: entry.itemId});
    entry.status = "succeeded"; entry.error = ""; entry.loaded = entry.file.size;
  };

  const runWithConcurrency = async (items) => {
    let cursor = 0;
    const worker = async () => {
      while (cursor < items.length) {
        const entry = items[cursor++];
        try { await uploadOne(entry); }
        catch (error) { entry.status = "failed"; entry.error = safeReason(error.code, error.message); }
        renderQueue(); renderOverlay("uploading", "Đang tải tệp lên kho lưu trữ.");
      }
    };
    await Promise.all(Array.from({length: Math.min(concurrency, items.length)}, worker));
  };

  const prepare = async (items) => {
    const session = await api(sessionUrl(), {file_count: items.length, total_size_bytes: items.reduce((sum, entry) => sum + entry.file.size, 0)});
    const sessionId = session.selection_session_id;
    items.forEach((entry) => { entry.sessionId = sessionId; entry.status = "pending"; });
    for (const group of chunks(items, 50)) {
      const result = await api(root.dataset.presignUrl, {selection_session_id: sessionId, files: group.map((entry) => ({client_file_id: entry.clientFileId, filename: entry.file.name, mime_type: entry.file.type, size: entry.file.size}))});
      const byClientId = new Map(result.items.map((item) => [item.client_file_id, item]));
      group.forEach((entry) => {
        const item = byClientId.get(entry.clientFileId);
        if (!item) { entry.status = "failed"; entry.error = "Server không trả thông tin cho tệp này."; return; }
        if (!item.accepted) { entry.status = "blocked"; entry.error = item.error || "Tệp không được chấp nhận."; return; }
        entry.itemId = item.upload_batch_item_id; entry.presign = item; entry.status = "ready";
      });
      renderQueue(); renderOverlay("preparing", "Đang kiểm tra tệp đã chọn.");
    }
    return sessionId;
  };

  const finalize = async (sessionId, sessionEntries) => {
    const failedIds = sessionEntries.filter((entry) => entry.status === "failed" && Number.isInteger(entry.itemId)).map((entry) => entry.itemId);
    await api(finalizeUrl(sessionId), {failed_upload_batch_item_ids: failedIds});
  };

  const upload = async (items) => {
    if (!items.length) return;
    modal?.show(); renderOverlay("preparing", "Đang kiểm tra tệp đã chọn.");
    let sessionId;
    try {
      sessionId = await prepare(items);
      await runWithConcurrency(items.filter((entry) => entry.status === "ready"));
      await finalize(sessionId, items);
    } catch (error) {
      items.filter((entry) => !terminal.has(entry.status)).forEach((entry) => { entry.status = "failed"; entry.error = error.message || "Không thể chuẩn bị tải tệp."; });
      if (sessionId) {
        try { await finalize(sessionId, items); } catch (_) { /* The result remains visible; pending objects expire safely. */ }
      }
    }
    renderQueue(); renderOverlay("done", "Đã hoàn tất tải lên. Kiểm tra kết quả trước khi đóng.");
  };

  const addFiles = (files) => {
    [...files].forEach((file) => entries.push({clientFileId: newId(), file, status: "pending", loaded: 0, error: ""}));
    renderQueue();
  };
  const openPicker = () => input.click();

  choose.addEventListener("click", openPicker);
  dropzone.addEventListener("click", openPicker);
  dropzone.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openPicker(); } });
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzoneMessage.textContent = "Thả tệp để tải lên"; }));
  ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzoneMessage.textContent = "Kéo thả ảnh/video hoặc bấm để chọn"; }));
  dropzone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
  start.addEventListener("click", () => upload(selected().filter((entry) => entry.status === "pending")));
  overlay.querySelector("[data-upload-retry-failed]").addEventListener("click", () => {
    const failed = selected().filter((entry) => entry.status === "failed");
    failed.forEach((entry) => {
      entry.itemId = null; entry.presign = null; entry.sessionId = null;
      entry.status = "pending"; entry.loaded = 0; entry.error = "";
    });
    upload(failed);
  });
  overlay.querySelector("[data-upload-close]").addEventListener("click", () => {
    modal?.hide();
    if (selected().some((entry) => entry.status === "succeeded")) window.location.reload();
  });
});
