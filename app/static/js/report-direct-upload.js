/* Daily Report save orchestrator.  Browser files are never submitted to Flask. */
(() => {
  const form = document.querySelector("form[data-report-direct-upload]");
  if (!form || !JSON.parse(form.dataset.uploadLimits || "{}").enabled) return;
  const limits = JSON.parse(form.dataset.uploadLimits || "{}");
  const csrf = form.dataset.csrfToken;
  const storageKey = `starx:report-upload:${form.dataset.projectId}`;
  const entries = new Map();
  const states = new Set(["idle", "validating", "creating_session", "uploading", "verifying", "submitting_report", "succeeded", "failed"]);
  let state = "idle", sessionId = null, finalSubmitting = false, beforeUnload = null;
  const overlay = form.querySelector("[data-report-save-overlay]");
  const uuid = () => globalThis.crypto?.randomUUID?.() || `section-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const endpoint = (base, id) => base.replace(/0(?=\D*$)/, String(id));
  const debug = (...args) => { if (window.STARX_DEBUG_UPLOADS) console.debug("[report-upload]", ...args); };
  const active = () => [...entries.values()].filter((entry) => entry.status !== "removed");
  const isLocked = () => ["creating_session", "uploading", "verifying", "submitting_report"].includes(state);
  const setState = (next, message) => {
    if (!states.has(next)) throw new Error("Upload state không hợp lệ.");
    state = next;
    if (overlay) {
      overlay.hidden = !["validating", "creating_session", "uploading", "verifying", "submitting_report", "failed"].includes(next);
      overlay.querySelector("[data-save-message]").textContent = message || "";
      overlay.querySelector("[data-save-retry]").hidden = next !== "failed";
      overlay.querySelector("[data-save-cancel]").hidden = !["creating_session", "uploading", "verifying", "failed"].includes(next);
    }
    form.classList.toggle("report-save-locked", isLocked());
    form.querySelectorAll("[data-report-submit], [data-add-section], [data-remove-section], [data-report-attachment-input]").forEach((el) => { el.disabled = isLocked(); });
    beforeUnload = isLocked() ? (event) => { event.preventDefault(); event.returnValue = ""; } : null;
    window.onbeforeunload = beforeUnload;
    renderProgress();
  };
  const sectionId = (row) => {
    let input = row.querySelector("[data-client-section-id]");
    if (!input) { input = document.createElement("input"); input.type = "hidden"; input.dataset.clientSectionId = "1"; row.prepend(input); }
    const index = (row.querySelector("[name*='-category_id']")?.name.match(/sections-(\d+)-/) || [])[1];
    input.name = `sections-${index || uuid()}-client-section-id`;
    if (!input.value) input.value = uuid();
    return input.value;
  };
  const normalizeSections = () => form.querySelectorAll("[data-section-row]").forEach(sectionId);
  const json = async (url, body) => {
    const response = await fetch(url, { method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRFToken": csrf}, body: JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || data.error || "Không thể tải ảnh.");
    return data;
  };
  const render = (entry) => {
    const row = [...form.querySelectorAll("[data-section-row]")].find((element) => sectionId(element) === entry.clientSectionId);
    const host = row?.querySelector("[data-attachment-preview]"); if (!host) return;
    let card = host.querySelector(`[data-direct-card="${entry.id}"]`);
    if (!card) { card = document.createElement("div"); card.className = "upload-preview-item"; card.dataset.directCard = entry.id; host.append(card); }
    card.replaceChildren();
    if (entry.preview) { const image = document.createElement("img"); image.src = entry.preview; image.className = "report-thumb"; image.alt = entry.file?.name || entry.name; card.append(image); }
    const label = document.createElement("span");
    label.textContent = `${entry.file?.name || entry.name}: ${entry.status === "completed" ? "Đã tải" : entry.status === "failed" ? `Lỗi – ${entry.error || "bấm thử lại"}` : "Chờ lưu"}`;
    card.append(label);
    if (!isLocked()) { const remove = document.createElement("button"); remove.type = "button"; remove.className = "btn btn-sm btn-outline-danger"; remove.textContent = entry.status === "failed" ? "Thử lại" : "×"; remove.onclick = () => entry.status === "failed" ? retryFailed() : removeEntry(entry); card.append(remove); }
  };
  const renderProgress = () => {
    const list = active(), completed = list.filter((entry) => entry.status === "completed").length;
    const bytes = list.reduce((sum, entry) => sum + (entry.file?.size || entry.size || 0), 0);
    const doneBytes = list.filter((entry) => entry.status === "completed").reduce((sum, entry) => sum + (entry.file?.size || entry.size || 0), 0);
    if (overlay) {
      overlay.querySelector("[data-save-count]").textContent = `${completed}/${list.length} ảnh`;
      overlay.querySelector("[data-save-bytes]").textContent = bytes ? `${Math.round(doneBytes / 1024 / 1024)} / ${Math.round(bytes / 1024 / 1024)} MiB` : "";
      overlay.querySelector("[data-save-progress]").style.width = `${bytes ? Math.round(doneBytes * 100 / bytes) : 0}%`;
    }
  };
  const persist = () => sessionStorage.setItem(storageKey, JSON.stringify({sessionId, items: active().map(({id, clientSectionId, itemId, status, name, size, file}) => ({id, clientSectionId, itemId, status, name: file?.name || name, size: file?.size || size}))}));
  const removeEntry = (entry) => { entry.status = "removed"; if (entry.preview) URL.revokeObjectURL(entry.preview); form.querySelector(`[data-direct-card="${entry.id}"]`)?.remove(); persist(); renderProgress(); };
  const add = (row, files) => {
    const current = active(), clientSectionId = sectionId(row); let total = current.reduce((sum, entry) => sum + entry.file.size, 0);
    for (const file of files) {
      const sectionCount = current.filter((entry) => entry.clientSectionId === clientSectionId).length;
      if (!/\.(jpe?g|png|webp|heic|heif)$/i.test(file.name) || file.size > Number(limits.max_file_bytes) || current.length >= Number(limits.max_files) || sectionCount >= Number(limits.max_files_per_section) || total + file.size > Number(limits.max_total_bytes)) {
        setState("failed", `Không thể thêm ${file.name}: vượt giới hạn ảnh.`); continue;
      }
      const entry = {id: uuid(), clientSectionId, file, name: file.name, size: file.size, status: "queued", preview: /^image\/(jpeg|png|webp)$/.test(file.type) ? URL.createObjectURL(file) : null};
      entries.set(entry.id, entry); current.push(entry); total += file.size; render(entry);
    }
    persist(); renderProgress();
  };
  const validate = () => {
    normalizeSections();
    if (!form.reportValidity()) { form.reportValidity(); throw new Error("Đang kiểm tra dữ liệu biểu mẫu."); }
    const list = active();
    if (list.length > Number(limits.max_files)) throw new Error("Báo cáo chỉ được có tối đa 30 ảnh.");
    return list;
  };
  const createAndPresign = async (list) => {
    if (!sessionId) {
      setState("creating_session", "Đang tạo phiên tải ảnh...");
      const data = await json(form.dataset.sessionUrl, {file_count: list.length, total_size_bytes: list.reduce((sum, entry) => sum + entry.file.size, 0)});
      sessionId = data.upload_session_id; debug("session created", sessionId);
    }
    const pending = list.filter((entry) => !entry.itemId);
    if (!pending.length) return;
    const data = await json(endpoint(form.dataset.presignUrl, sessionId), {files: pending.map((entry) => ({client_file_id: entry.id, client_section_id: entry.clientSectionId, filename: entry.file.name, mime_type: entry.file.type || "application/octet-stream", size: entry.file.size}))});
    const signed = new Map(data.items.map((item) => [item.client_file_id, item]));
    pending.forEach((entry) => { const item = signed.get(entry.id); if (!item) throw new Error("Không thể ký tải ảnh."); entry.itemId = item.upload_batch_item_id; entry.signed = item; entry.status = "presigned"; debug("item presigned", entry.itemId); });
    persist();
  };
  const uploadOne = async (entry) => {
    entry.status = "uploading"; render(entry); renderProgress();
    const response = await fetch(entry.signed.url, {method: "PUT", headers: entry.signed.headers || {"Content-Type": entry.file.type}, body: entry.file});
    if (!response.ok) throw new Error("S3 từ chối tải ảnh.");
    entry.status = "verifying"; setState("verifying", "Đang xác minh ảnh đã tải..."); render(entry);
    await json(endpoint(form.dataset.completeUrl, sessionId), {upload_batch_item_id: entry.itemId});
    entry.status = "completed"; entry.error = null; debug("item verified", entry.itemId); render(entry); persist(); renderProgress();
  };
  const uploadAll = async (list) => {
    setState("uploading", `Đang tải 0/${list.length} ảnh...`);
    let cursor = 0, failed = null;
    await Promise.all(Array.from({length: Math.min(3, Number(limits.concurrency) || 3, list.length)}, async () => {
      while (cursor < list.length && !failed) { const entry = list[cursor++]; try { await uploadOne(entry); setState("uploading", `Đang tải ${active().filter((x) => x.status === "completed").length}/${list.length} ảnh...`); } catch (error) { entry.status = "failed"; entry.error = error.message; render(entry); failed = error; } }
    }));
    if (failed || list.some((entry) => entry.status !== "completed")) throw failed || new Error("Có ảnh chưa tải lên hoàn tất.");
  };
  const manifest = (list) => ({upload_session_id: list.length ? sessionId : null, attachments: list.map((entry, sort_order) => ({upload_item_id: entry.itemId, client_section_id: entry.clientSectionId, sort_order}))});
  const submitReport = async (list) => {
    setState("submitting_report", "Đang hoàn tất báo cáo...");
    if (!list.length) sessionId = null;
    form.querySelector("[data-upload-session-id]").value = list.length ? (sessionId || "") : "";
    form.querySelector("[data-attachment-manifest]").value = JSON.stringify(manifest(list));
    form.querySelector("[data-direct-upload-expected]").value = list.length ? "1" : "0";
    const selectedCount = form.querySelector("[data-direct-upload-selected-count]");
    if (selectedCount) selectedCount.value = String(list.length);
    const data = new FormData(form); form.querySelectorAll("[data-report-attachment-input]").forEach((input) => { if (input.name) data.delete(input.name); });
    const response = await fetch(form.action || window.location.href, {method: "POST", credentials: "same-origin", headers: {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}, body: new URLSearchParams(data)});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) throw new Error(payload.message || "Không thể lưu báo cáo.");
    debug("report success", payload.report_id); setState("succeeded"); sessionStorage.removeItem(storageKey); window.location.assign(payload.redirect_url);
  };
  const save = async () => {
    if (finalSubmitting || isLocked()) return; finalSubmitting = true;
    try { setState("validating", "Đang kiểm tra dữ liệu..."); const list = validate(); if (list.length) { await createAndPresign(list); await uploadAll(list.filter((entry) => entry.status !== "completed")); } await submitReport(list); }
    catch (error) { debug("report failed", error.message); setState("failed", error.message || "Không thể lưu báo cáo."); finalSubmitting = false; persist(); }
  };
  const retryFailed = async () => { if (isLocked()) return; const failed = active().filter((entry) => entry.status === "failed"); if (!failed.length) return; failed.forEach((entry) => { entry.status = "presigned"; entry.error = null; }); await save(); };
  form.addEventListener("submit", (event) => { event.preventDefault(); save(); });
  form.addEventListener("change", (event) => { const input = event.target.closest("[data-report-attachment-input]"); if (!input) return; add(input.closest("[data-section-row]"), [...input.files]); input.value = ""; });
  form.addEventListener("drop", (event) => { const row = event.target.closest("[data-section-row]"); if (!row || isLocked()) return; event.preventDefault(); add(row, [...event.dataTransfer.files]); });
  form.addEventListener("dragover", (event) => { if (event.target.closest("[data-section-row]")) event.preventDefault(); });
  overlay?.querySelector("[data-save-retry]")?.addEventListener("click", retryFailed);
  overlay?.querySelector("[data-save-cancel]")?.addEventListener("click", async () => {
    if (sessionId) { try { await json(endpoint(form.dataset.cancelUrl, sessionId), {}); } catch (_) { /* Cleanup also expires cancelled sessions server-side. */ } }
    sessionId = null;
    active().forEach((entry) => { if (entry.file) { entry.itemId = null; entry.signed = null; entry.status = "queued"; } else { removeEntry(entry); } });
    setState("idle"); persist();
  });
  document.addEventListener("starx:report-section-added", normalizeSections);
  document.addEventListener("starx:report-section-removed", (event) => active().filter((entry) => entry.clientSectionId === event.detail).forEach(removeEntry));
  normalizeSections();
  form.querySelectorAll("[data-report-attachment-input]").forEach((input) => { input.dataset.originalName = input.name || ""; input.removeAttribute("name"); });
  try { const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null"); if (saved?.sessionId) { sessionId = saved.sessionId; fetch(endpoint(form.dataset.sessionStateUrl, sessionId), {credentials: "same-origin"}).then((response) => response.ok ? response.json() : null).then((data) => { (saved.items || []).forEach((old) => { const server = (data?.items || []).find((item) => item.id === old.itemId); if (server?.status === "completed") { const entry = {...old, status: "completed"}; entries.set(entry.id, entry); render(entry); } }); persist(); renderProgress(); }); } } catch (_) { /* Session recovery is best-effort. */ }
})();
