document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-project-document-files]");
  if (!root) return;

  const csrfToken = root.dataset.csrfToken;
  const bulkBar = root.querySelector("[data-bulk-bar]");
  const count = root.querySelector("[data-selected-count]");
  const archiveButton = root.querySelector("[data-bulk-archive]");
  const restoreButton = root.querySelector("[data-bulk-restore]");
  const downloadButton = root.querySelector("[data-bulk-download]");
  const selectAll = root.querySelector("[data-select-all]");
  const checkboxes = () => [...root.querySelectorAll("[data-file-select]")];
  const selected = () => checkboxes().filter((checkbox) => checkbox.checked);

  const updateSelectedCards = () => {
    checkboxes().forEach((checkbox) => {
      checkbox.closest("[data-file-card]").classList.toggle("is-selected", checkbox.checked);
    });
  };

  const updateSelectAll = () => {
    if (!selectAll) return;
    const items = checkboxes();
    const selectedCount = selected().length;
    selectAll.disabled = items.length === 0;
    selectAll.checked = items.length > 0 && selectedCount === items.length;
    selectAll.indeterminate = selectedCount > 0 && selectedCount < items.length;
  };

  const updateBulkBar = () => {
    const items = selected();
    const states = items.map((checkbox) => checkbox.closest("[data-file-card]").dataset.fileState);
    count.textContent = items.length;
    bulkBar.classList.toggle("d-none", items.length === 0);
    if (archiveButton) archiveButton.disabled = !states.includes("active");
    if (restoreButton) restoreButton.disabled = !states.includes("archived");
    if (downloadButton) downloadButton.disabled = !states.includes("active");
    updateSelectedCards();
    updateSelectAll();
  };

  checkboxes().forEach((checkbox) => checkbox.addEventListener("change", updateBulkBar));
  selectAll?.addEventListener("change", () => {
    checkboxes().forEach((checkbox) => { checkbox.checked = selectAll.checked; });
    updateBulkBar();
  });
  root.querySelector("[data-clear-selection]")?.addEventListener("click", () => {
    checkboxes().forEach((checkbox) => { checkbox.checked = false; });
    updateBulkBar();
  });

  updateBulkBar();

  const postBulk = async (url) => {
    const fileIds = selected().map((checkbox) => Number(checkbox.value));
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ file_ids: fileIds }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Bạn không có quyền thao tác các tệp đã chọn.");
    return result;
  };

  const showSummary = (result, action) => {
    const countChanged = result[action] || 0;
    const notes = [];
    if (result.skipped) notes.push(`${result.skipped} tệp bị bỏ qua`);
    if (result.forbidden) notes.push(`${result.forbidden} tệp không đủ quyền`);
    window.alert(`${countChanged} tệp đã được xử lý.${notes.length ? ` ${notes.join(", ")}.` : ""}`);
  };

  archiveButton?.addEventListener("click", async () => {
    if (!window.confirm("Lưu trữ các tài liệu đã chọn?")) return;
    try {
      showSummary(await postBulk(root.dataset.bulkArchiveUrl), "archived");
      window.location.reload();
    } catch (error) { window.alert(error.message); }
  });
  restoreButton?.addEventListener("click", async () => {
    try {
      showSummary(await postBulk(root.dataset.bulkRestoreUrl), "restored");
      window.location.reload();
    } catch (error) { window.alert(error.message); }
  });
  downloadButton?.addEventListener("click", async () => {
    try {
      downloadButton.disabled = true;
      downloadButton.textContent = "Đang chuẩn bị tải xuống...";
      const fileIds = selected().map((checkbox) => Number(checkbox.value));
      if (fileIds.length === 1) {
        const response = await fetch(root.dataset.bulkDownloadUrl, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken }, body: JSON.stringify({ file_ids: fileIds }) });
        const result = await response.json();
        if (!response.ok || result.kind !== "direct" || !result.download?.url) {
          throw new Error(result.error || "Không thể tải xuống tệp đã chọn.");
        }
        window.location.assign(result.download.url);
        return;
      }

      const validateUrl = root.dataset.bulkDownloadValidateUrl || document.querySelector("[data-bulk-download-validate-url]")?.dataset.bulkDownloadValidateUrl;
      const response = await fetch(validateUrl, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken }, body: JSON.stringify({ file_ids: fileIds }) });
      const result = await response.json();
      if (!response.ok || result.kind !== "zip") {
        throw new Error(result.error || "Không thể tải xuống các tệp đã chọn.");
      }

      const form = document.createElement("form");
      form.method = "POST";
      form.action = root.dataset.bulkDownloadUrl;
      form.hidden = true;
      for (const [name, value] of [["csrf_token", csrfToken], ["file_ids_json", JSON.stringify(fileIds)]]) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.append(input);
      }
      document.body.append(form);
      form.submit();
      window.setTimeout(() => form.remove(), 0);
    } catch (error) { window.alert(error.message || "Tải file ZIP thất bại. Vui lòng thử lại hoặc chọn ít tệp hơn."); }
    finally { downloadButton.disabled = false; downloadButton.textContent = "Tải xuống"; }
  });

  const renameModalElement = document.getElementById("projectDocumentRenameModal");
  if (!renameModalElement) return;
  const renameForm = renameModalElement.querySelector("[data-rename-form]");
  const renameInput = document.getElementById("projectDocumentRenameInput");
  const renameModal = new bootstrap.Modal(renameModalElement);
  document.querySelectorAll("[data-rename-file]").forEach((button) => button.addEventListener("click", () => {
    renameForm.action = button.dataset.renameUrl;
    renameInput.value = button.dataset.fileName;
    renameModal.show();
    window.setTimeout(() => renameInput.select(), 150);
  }));
});
