document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-project-document-preview]"); if (!root) return;
  const csrf = root.dataset.csrfToken;
  const previewFallback = "Không thể tải preview.";
  const downloadFallback = "Không thể tạo liên kết tải xuống.";
  const messageFor = (data, fallback) => {
    const error = data?.error;
    if (typeof data?.message === "string" && data.message) return data.message;
    if (typeof error === "string" && error) return error;
    if (typeof error?.message === "string" && error.message) return error.message;
    return fallback;
  };
  const requestJson = async (url, payload = {}, fallback = previewFallback) => {
    let response;
    try {
      response = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json","X-CSRFToken":csrf}, body:JSON.stringify(payload)});
    } catch (_) { throw new Error(fallback); }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error(fallback); }
    if (!response.ok || data?.ok !== true) throw new Error(messageFor(data, fallback));
    return data;
  };
  if (window.location.pathname.startsWith("/company-media/")) { const versions = JSON.parse(document.querySelector("[data-company-media-thumbnail-versions]")?.dataset.companyMediaThumbnailVersions || "{}"); document.querySelectorAll(".document-card-preview[data-preview-file-id]").forEach((card) => { const image = document.createElement("img"); const version = versions[card.dataset.previewFileId]; image.className = "document-thumbnail-image"; image.alt = card.dataset.previewName || "Thumbnail media"; image.loading = "lazy"; image.decoding = "async"; image.width = image.height = 480; image.src = `/company-media/files/${encodeURIComponent(card.dataset.previewFileId)}/thumbnail${version ? `?v=${encodeURIComponent(version)}` : ""}`; card.replaceChildren(image); }); }
  document.addEventListener("click", async (event) => { const trigger = event.target.closest("[data-preview-file-id]"); if (!trigger) return; event.preventDefault(); try { const variant = trigger.dataset.previewVariant === "thumbnail" ? "preview" : trigger.dataset.previewVariant; const data = await requestJson(trigger.dataset.previewUrl, {variant}, previewFallback); window.openMediaPreview?.({url:data.url, name:trigger.dataset.previewName, type:data.kind === "video" ? "video" : "image", imageTools:data.kind === "image", downloadUrl: trigger.dataset.downloadUrl || null}); } catch (error) { window.alert(error.message); } });
  document.querySelectorAll("[data-signed-download]").forEach((button) => button.addEventListener("click", async () => {
    if (button.dataset.signedDownloadBusy === "true") return;
    button.dataset.signedDownloadBusy = "true";
    const wasDisabled = button.disabled;
    button.disabled = true;
    try {
      const result = await requestJson(button.dataset.downloadUrl, {}, downloadFallback);
      if (typeof result.url !== "string" || !result.url.trim()) throw new Error(downloadFallback);
      window.location.assign(result.url);
    } catch (error) { window.alert(error.message || downloadFallback); }
    finally {
      button.disabled = wasDisabled;
      delete button.dataset.signedDownloadBusy;
    }
  }));
});
