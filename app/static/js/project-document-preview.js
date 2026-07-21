document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-project-document-preview]");
  if (!root) return;

  const csrfToken = root.dataset.csrfToken;
  const modalElement = document.getElementById("projectDocumentPreviewModal");
  const modalBody = modalElement.querySelector("[data-preview-modal-body]");
  const modalTitle = document.getElementById("projectDocumentPreviewTitle");
  const modalDownload = modalElement.querySelector("[data-preview-download]");
  const modal = new bootstrap.Modal(modalElement);

  modalElement.addEventListener("hidden.bs.modal", () => {
    modalBody.querySelectorAll("video").forEach((video) => {
      video.pause();
      video.removeAttribute("src");
      video.load();
    });
    modalBody.querySelectorAll("img").forEach((image) => image.removeAttribute("src"));
    modalBody.replaceChildren();
    modalDownload.onclick = null;
  });

  const requestJson = async (url, payload = {}) => {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Không thể tải preview.");
    return result;
  };

  const setPlaceholder = (element, message) => {
    element.replaceChildren();
    const text = document.createElement("span");
    text.className = "preview-placeholder-text";
    text.textContent = message;
    element.append(text);
  };

  const loadThumbnail = async (element) => {
    try {
      const result = await requestJson(element.dataset.previewUrl, { variant: element.dataset.previewVariant });
      if (!result.ok) {
        setPlaceholder(element, result.message || "Chưa có preview");
        return;
      }
      const image = document.createElement("img");
      image.className = "document-thumbnail-image";
      image.alt = `Preview ${element.dataset.previewName}`;
      image.src = result.url;
      element.replaceChildren(image);
    } catch (_) {
      setPlaceholder(element, "Không tải được preview");
    }
  };

  document.querySelectorAll(".document-card-preview").forEach(loadThumbnail);

  document.querySelectorAll("[data-preview-file-id]").forEach((trigger) => {
    trigger.addEventListener("click", async () => {
      modalTitle.textContent = trigger.dataset.previewName;
      modalBody.replaceChildren();
      modalBody.textContent = "Đang tải preview…";
      modalDownload.disabled = true;
      modal.show();
      try {
        const modalVariant = trigger.dataset.previewVariant === "thumbnail" ? "preview" : trigger.dataset.previewVariant;
        const result = await requestJson(trigger.dataset.previewUrl, { variant: modalVariant });
        if (!result.ok) {
          modalBody.textContent = result.message || "Chưa có preview.";
          return;
        }
        let preview;
        if (result.kind === "video") {
          preview = document.createElement("video");
          preview.className = "w-100 rounded document-preview-video";
          preview.controls = true;
          preview.preload = "metadata";
          preview.src = result.url;
        } else if (result.kind === "pdf") {
          preview = document.createElement("iframe");
          preview.className = "w-100 border rounded document-preview-pdf";
          preview.title = trigger.dataset.previewName;
          preview.src = result.url;
        } else {
          preview = document.createElement("img");
          preview.className = "img-fluid rounded document-preview-image";
          preview.alt = trigger.dataset.previewName;
          preview.src = result.url;
        }
        modalBody.replaceChildren(preview);
        modalDownload.disabled = false;
        modalDownload.onclick = () => {
          const download = document.querySelector(`[data-signed-download="${trigger.dataset.previewFileId}"]`);
          if (download) download.click();
        };
      } catch (error) {
        modalBody.textContent = error.message || "Không thể tải preview.";
      }
    });
  });

  document.querySelectorAll("[data-signed-download]").forEach((button) => {
    button.addEventListener("click", async () => {
      const originalText = button.textContent;
      button.disabled = true;
      try {
        const result = await requestJson(button.dataset.downloadUrl);
        if (result.url) window.location.assign(result.url);
      } catch (error) {
        window.alert(error.message || "Không thể tạo liên kết tải xuống.");
      } finally {
        button.disabled = false;
        button.textContent = originalText;
      }
    });
  });
});
