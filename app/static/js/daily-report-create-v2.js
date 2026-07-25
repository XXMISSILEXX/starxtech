/* JSON-only controller for the create page.  Edit deliberately uses its own legacy file. */
(() => {
  const form = document.querySelector("[data-daily-report-create-v2]");
  if (!form) return;
  const limits = JSON.parse(form.dataset.uploadLimits || "{}");
  const csrf = form.dataset.csrfToken;
  const endpoint = (tail) => `${form.dataset.apiBase}${tail}`;
  const uuid = () => crypto.randomUUID();
  const entries = new Map();
  let state = "idle", sessionId = null, submitting = false;
  const overlay = document.querySelector("[data-report-save-overlay]");
  const sectionRows = () => [...form.querySelectorAll("[data-section-row]")];
  const active = () => [...entries.values()].filter(x => !x.removed);
  const locked = () => ["creating_session", "presigning", "uploading", "verifying", "finalizing"].includes(state);
  const setState = (next, message = "") => {
    state = next;
    if (overlay) {
      overlay.hidden = !["validating", "creating_session", "presigning", "uploading", "verifying", "finalizing", "failed"].includes(next);
      overlay.querySelector("[data-save-message]").textContent = message;
      overlay.querySelector("[data-save-retry]").hidden = next !== "failed";
      overlay.querySelector("[data-save-cancel]").hidden = !["creating_session", "presigning", "uploading", "verifying", "failed"].includes(next);
    }
    form.querySelectorAll("[data-report-submit], [data-add-section], [data-remove-section], [data-report-attachment-input]").forEach(el => el.disabled = locked());
    window.onbeforeunload = locked() ? event => { event.preventDefault(); event.returnValue = ""; } : null;
    progress();
  };
  const api = async (url, body) => {
    const response = await fetch(url, {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRFToken": csrf}, body: JSON.stringify(body)});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "Không thể xử lý yêu cầu.");
    return payload.data;
  };
  const sectionId = row => {
    const input = row.querySelector("[data-client-section-id]");
    if (!input.value) input.value = uuid();
    return input.value;
  };
  const normalizeSections = () => sectionRows().forEach(sectionId);
  const progress = () => {
    const list = active(), done = list.filter(x => x.status === "completed");
    const total = list.reduce((n, x) => n + x.file.size, 0), bytes = done.reduce((n, x) => n + x.file.size, 0);
    if (overlay) {
      overlay.querySelector("[data-save-count]").textContent = `${done.length}/${list.length} ảnh`;
      overlay.querySelector("[data-save-bytes]").textContent = total ? `${Math.round(bytes / 1048576)} / ${Math.round(total / 1048576)} MiB` : "";
      overlay.querySelector("[data-save-progress]").style.width = `${total ? Math.round(bytes * 100 / total) : 0}%`;
    }
  };
  const render = entry => {
    const row = sectionRows().find(x => sectionId(x) === entry.clientSectionId), host = row?.querySelector("[data-attachment-preview]");
    if (!host) return;
    let card = host.querySelector(`[data-v2-file="${entry.id}"]`);
    if (!card) { card = document.createElement("div"); card.className = "upload-preview-item"; card.dataset.v2File = entry.id; host.append(card); }
    card.replaceChildren();
    if (entry.preview) { const image = new Image(); image.src = entry.preview; image.className = "report-thumb"; image.alt = entry.file.name; card.append(image); }
    const label = document.createElement("span"); label.textContent = `${entry.file.name}: ${entry.status === "failed" ? "Lỗi – thử lại" : entry.status === "completed" ? "Đã tải" : "Chờ lưu"}`; card.append(label);
    if (!locked()) { const remove = document.createElement("button"); remove.type = "button"; remove.className = "btn btn-sm btn-outline-danger"; remove.textContent = "×"; remove.onclick = () => { entry.removed = true; URL.revokeObjectURL(entry.preview); card.remove(); progress(); }; card.append(remove); }
  };
  const addFiles = (row, files) => {
    normalizeSections(); const current = active(); let total = current.reduce((n, x) => n + x.file.size, 0);
    for (const file of files) {
      const perSection = current.filter(x => x.clientSectionId === sectionId(row)).length;
      if (!/\.(jpe?g|png|webp)$/i.test(file.name) || file.size > limits.max_file_bytes || current.length >= limits.max_files || perSection >= limits.max_files_per_section || total + file.size > limits.max_total_bytes) { setState("failed", `Không thể thêm ${file.name}: vượt giới hạn ảnh.`); continue; }
      const entry = {id: uuid(), clientSectionId: sectionId(row), file, status: "queued", preview: URL.createObjectURL(file)};
      entries.set(entry.id, entry); current.push(entry); total += file.size; render(entry);
    }
    progress();
  };
  const addSection = () => {
    const source = sectionRows()[0];
    if (!source) return;
    const row = source.cloneNode(true);
    // Bootstrap's legacy custom-select wrapper belongs to the source select;
    // V2 owns only the native controls it serializes.
    row.querySelectorAll(".custom-select").forEach(wrapper => wrapper.remove());
    row.querySelector("[data-client-section-id]").value = uuid();
    row.querySelector("[name$='-category_id']").value = "";
    row.querySelector("[name$='-status']").value = "INFO";
    row.querySelector("textarea[name$='-content']").value = "";
    const input = row.querySelector("[data-report-attachment-input]");
    input.value = ""; input.id = `v2-images-${uuid()}`; input.closest("label.upload-dropzone").htmlFor = input.id;
    row.querySelector("[data-attachment-preview]").replaceChildren();
    form.querySelector("[data-sections]").append(row);
  };
  const payload = list => ({client_request_id: form.dataset.clientRequestId || (form.dataset.clientRequestId = uuid()), report_date: form.report_date.value.split("/").reverse().join("-"), overall_status: form.overall_status.value, highlight: form.highlight.value.trim(), summary_note: form.summary_note.value.trim(), upload_session_id: list.length ? sessionId : null,
    sections: sectionRows().map((row, sort_order) => ({client_section_id: sectionId(row), report_category_id: Number(row.querySelector("[name$='-category_id']").value), status: row.querySelector("[name$='-status']").value, content: row.querySelector("textarea[name$='-content']").value.trim(), sort_order})),
    attachments: list.map((entry, sort_order) => ({upload_item_id: entry.itemId, client_section_id: entry.clientSectionId, sort_order}))});
  const validate = () => { normalizeSections(); if (!form.checkValidity()) { form.reportValidity(); throw new Error("Vui lòng kiểm tra các trường bắt buộc."); } return active(); };
  const uploadOne = async entry => {
    entry.status = "uploading"; render(entry);
    const response = await fetch(entry.signed.url, {method: "PUT", headers: entry.signed.headers || {"Content-Type": entry.file.type}, body: entry.file});
    if (!response.ok) throw new Error("S3 từ chối tải ảnh.");
    entry.status = "verifying"; setState("verifying", "Đang xác minh ảnh...");
    await api(endpoint(`/upload-sessions/${sessionId}/items/${entry.itemId}/complete`), {});
    entry.status = "completed"; render(entry); progress();
  };
  const parallel = async list => { let index = 0, failure; await Promise.all(Array.from({length: Math.min(3, Number(limits.concurrency) || 3, list.length)}, async () => { while (index < list.length && !failure) { const item = list[index++]; try { await uploadOne(item); } catch (error) { item.status = "failed"; item.error = error.message; render(item); failure = error; } } })); if (failure) throw failure; };
  const save = async () => {
    if (submitting || locked()) return; submitting = true;
    try {
      setState("validating", "Đang kiểm tra dữ liệu..."); const list = validate();
      if (list.length) {
        setState("creating_session", "Đang tạo phiên tải ảnh...");
        if (!sessionId) sessionId = (await api(endpoint("/upload-sessions"), {file_count: list.length, total_size_bytes: list.reduce((n, x) => n + x.file.size, 0)})).upload_session_id;
        setState("presigning", "Đang chuẩn bị tải ảnh...");
        const signed = await api(endpoint(`/upload-sessions/${sessionId}/presign`), {files: list.filter(x => x.status !== "completed").map(x => ({client_file_id: x.id, client_section_id: x.clientSectionId, filename: x.file.name, mime_type: x.file.type, size: x.file.size}))});
        const byFile = new Map(signed.items.map(x => [x.client_file_id, x])); list.forEach(x => { const item = byFile.get(x.id); if (item) { x.itemId = item.upload_batch_item_id; x.signed = item; } });
        setState("uploading", "Đang tải ảnh..."); await parallel(list.filter(x => x.status !== "completed"));
      }
      setState("finalizing", "Đang hoàn tất báo cáo..."); const result = await api(endpoint("/finalize"), payload(list)); setState("succeeded"); window.location.assign(result.redirect_url);
    } catch (error) { setState("failed", error.message || "Không thể lưu báo cáo."); submitting = false; }
  };
  const retry = () => { active().filter(x => x.status === "failed").forEach(x => { x.status = "queued"; }); submitting = false; save(); };
  form.addEventListener("submit", event => { event.preventDefault(); save(); });
  form.addEventListener("change", event => { const input = event.target.closest("[data-report-attachment-input]"); if (input && !locked()) { addFiles(input.closest("[data-section-row]"), [...input.files]); input.value = ""; } });
  form.querySelector("[data-add-section]")?.addEventListener("click", addSection);
  form.addEventListener("click", event => { if (event.target.closest("[data-remove-section]")) { const row = event.target.closest("[data-section-row]"); active().filter(x => x.clientSectionId === sectionId(row)).forEach(x => { x.removed = true; }); row.remove(); progress(); } });
  overlay?.querySelector("[data-save-retry]")?.addEventListener("click", retry);
  overlay?.querySelector("[data-save-cancel]")?.addEventListener("click", async () => { if (sessionId && state !== "finalizing") { try { await api(endpoint(`/upload-sessions/${sessionId}/cancel`), {}); } catch (_) {} } sessionId = null; active().forEach(x => { x.status = "queued"; x.itemId = null; }); setState("cancelled"); submitting = false; });
  normalizeSections(); progress();
})();
