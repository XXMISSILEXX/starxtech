document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-project-document-upload]");
  if (!root) return;
  const input = root.querySelector("#project-document-file-input");
  const dropzone = root.querySelector("#project-document-dropzone");
  const message = root.querySelector(".dropzone-message");
  const choose = root.querySelector("#project-document-choose-files");
  const start = root.querySelector("#project-document-start-upload");
  const list = root.querySelector("#project-document-upload-queue");
  const selectedFiles = [];
  const keyFor = (file) => `${file.name}:${file.size}:${file.lastModified}`;
  const formatSize = (size) => size < 1024 ? `${size} B` : `${(size / 1024 / 1024).toFixed(1)} MB`;
  const render = () => {
    list.replaceChildren();
    selectedFiles.forEach((entry, index) => {
      const item = document.createElement("li"); item.className = "list-group-item d-flex justify-content-between gap-2";
      const detail = document.createElement("span"); detail.textContent = `${entry.file.name} (${formatSize(entry.file.size)}) — ${entry.status}`; item.append(detail);
      if (entry.status === "Chờ tải lên") { const remove = document.createElement("button"); remove.type = "button"; remove.className = "btn btn-sm btn-outline-danger"; remove.textContent = "Xóa"; remove.addEventListener("click", () => { selectedFiles.splice(index, 1); render(); }); item.append(remove); }
      list.append(item);
    });
    start.disabled = !selectedFiles.some((entry) => entry.status === "Chờ tải lên");
  };
  const addFiles = (files) => { [...files].forEach((file) => { if (!selectedFiles.some((entry) => keyFor(entry.file) === keyFor(file))) selectedFiles.push({ file, id: `file-${Date.now()}-${selectedFiles.length}`, status: "Chờ tải lên" }); }); render(); };
  const openPicker = () => input.click();
  choose.addEventListener("click", openPicker); dropzone.addEventListener("click", openPicker);
  dropzone.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openPicker(); } });
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); event.stopPropagation(); dropzone.classList.add("dragover"); message.textContent = "Thả tệp để tải lên"; }));
  ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); event.stopPropagation(); dropzone.classList.remove("dragover"); message.textContent = "Kéo thả tệp vào đây hoặc bấm để chọn tệp"; }));
  dropzone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
  start.addEventListener("click", async () => {
    const pending = selectedFiles.filter((entry) => entry.status === "Chờ tải lên"); if (!pending.length) return;
    start.disabled = true; input.disabled = true; pending.forEach((entry) => entry.status = "Đang chuẩn bị"); render();
    try {
      const response = await fetch(root.dataset.presignUrl, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": root.dataset.csrfToken }, body: JSON.stringify({ files: pending.map((entry) => ({ client_file_id: entry.id, filename: entry.file.name, mime_type: entry.file.type, size: entry.file.size })) }) });
      const result = await response.json(); if (!response.ok) throw new Error(result.error || "Không thể chuẩn bị tải lên.");
      for (const item of result.items) { const entry = selectedFiles.find((candidate) => candidate.id === item.client_file_id); if (!entry) continue; if (!item.accepted) { entry.status = `Bị từ chối: ${item.error}`; render(); continue; } if (!Number.isInteger(item.upload_batch_item_id)) { entry.status = "Lỗi: Server không trả upload_batch_item_id cho tệp này."; render(); continue; }
        entry.status = "Đang tải lên"; render(); const form = new FormData(); Object.entries(item.fields || {}).forEach(([key, value]) => form.append(key, value)); form.append("file", entry.file);
        const upload = await fetch(item.url, { method: item.method || "POST", body: form }); if (!upload.ok) { entry.status = "Lỗi tải lên S3"; render(); continue; }
        entry.status = "Đang hoàn tất"; render(); const complete = await fetch(root.dataset.completeUrl, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": root.dataset.csrfToken }, body: JSON.stringify({ upload_batch_item_id: item.upload_batch_item_id }) }); const completed = await complete.json(); entry.status = complete.ok ? "Hoàn tất" : `Lỗi: ${completed.error || "không thể hoàn tất"}`; render();
      }
    } catch (error) { pending.forEach((entry) => { if (entry.status === "Đang chuẩn bị") entry.status = `Lỗi: ${error.message}`; }); render(); }
    finally { input.disabled = false; render(); if (selectedFiles.some((entry) => entry.status === "Hoàn tất")) window.setTimeout(() => window.location.reload(), 700); }
  });
});
