(() => {
  const allowed = new Set(["jpg", "jpeg", "png", "webp", "heic", "heif"]);
  const maxBytes = 10 * 1024 * 1024;
  let active = null;
  let sourceUrl = null;

  const extension = (file) => (file.name.split(".").pop() || "").toLowerCase();
  const csrf = () => document.querySelector('input[name="csrf_token"]')?.value || "";
  const isHeif = (file) => ["heic", "heif"].includes(extension(file));
  const setStatus = (picker, text, tone = "muted") => {
    const status = picker.querySelector("[data-picker-status]");
    if (status) { status.textContent = text; status.className = `small text-${tone}`; }
  };
  const replaceInputFile = (input, file) => { const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; };
  const temporaryPreview = async (file) => {
    const data = new FormData(); data.append("image", file); data.append("csrf_token", csrf());
    const response = await fetch("/media-display-preview", {method: "POST", body: data, credentials: "same-origin"});
    if (!response.ok) throw new Error("Không thể tạo bản xem trước");
    return URL.createObjectURL(await response.blob());
  };
  const loadImage = (url) => new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = url; });
  const canvasToWebp = (state) => new Promise((resolve) => state.canvas.toBlob((blob) => resolve(blob), "image/webp", .88));

  const draw = () => {
    if (!active?.image) return;
    const {canvas, ctx, image, zoom, rotation, offsetX, offsetY} = active;
    const size = canvas.width; ctx.clearRect(0, 0, size, size);
    ctx.save(); ctx.translate(size / 2 + offsetX, size / 2 + offsetY); ctx.rotate(rotation * Math.PI / 180);
    const scale = Math.max(size / image.width, size / image.height) * zoom;
    ctx.drawImage(image, -image.width * scale / 2, -image.height * scale / 2, image.width * scale, image.height * scale); ctx.restore();
  };
  const openCropper = async (picker, file) => {
    const modalEl = document.getElementById("displayImageCropModal"); if (!modalEl || !window.bootstrap) return;
    setStatus(picker, "Đang tạo bản xem trước…");
    let url;
    try { url = isHeif(file) ? await temporaryPreview(file) : URL.createObjectURL(file); } catch (_) { setStatus(picker, "Không thể tạo bản xem trước", "danger"); return; }
    let image; try { image = await loadImage(url); } catch (_) { setStatus(picker, "Không thể tạo bản xem trước", "danger"); return; }
    if (sourceUrl) URL.revokeObjectURL(sourceUrl); sourceUrl = url;
    const canvas = modalEl.querySelector("canvas"); const slider = modalEl.querySelector("[data-crop-zoom]");
    active = {picker, file, image, url, canvas, ctx: canvas.getContext("2d"), zoom: 1, rotation: 0, offsetX: 0, offsetY: 0};
    slider.value = "1"; draw(); setStatus(picker, "");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl); modal.show();
  };
  const bindPicker = (picker) => {
    if (picker.dataset.pickerReady) return; picker.dataset.pickerReady = "1";
    const input = picker.querySelector("[data-file-input]"); const zone = picker.querySelector("[data-dropzone]");
    const viewport = picker.querySelector("[data-display-image-preview]");
    const originalPreview = viewport?.innerHTML || "";
    const choose = (file) => { if (!file || !allowed.has(extension(file)) || file.size > maxBytes) { setStatus(picker, "Chỉ nhận JPG, PNG, WebP, HEIC/HEIF tối đa 10 MB.", "danger"); return; } replaceInputFile(input, file); openCropper(picker, file); };
    input?.addEventListener("change", () => choose(input.files[0]));
    ["dragenter", "dragover"].forEach((name) => zone?.addEventListener(name, (event) => { event.preventDefault(); zone.classList.add("dragover"); }));
    ["dragleave", "drop"].forEach((name) => zone?.addEventListener(name, (event) => { event.preventDefault(); zone.classList.remove("dragover"); if (name === "drop") choose(event.dataTransfer.files[0]); }));
    picker.querySelector("[data-remove-selection]")?.addEventListener("click", () => { input.value = ""; if (viewport) viewport.innerHTML = originalPreview; setStatus(picker, ""); });
  };
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-display-image-picker]").forEach(bindPicker);
    const modal = document.getElementById("displayImageCropModal"); if (!modal) return;
    modal.querySelector("[data-crop-zoom]")?.addEventListener("input", (e) => { if (active) { active.zoom = Number(e.target.value); draw(); } });
    modal.querySelector("[data-crop-rotate-left]")?.addEventListener("click", () => { if (active) { active.rotation -= 90; draw(); } });
    modal.querySelector("[data-crop-rotate-right]")?.addEventListener("click", () => { if (active) { active.rotation += 90; draw(); } });
    modal.querySelector("[data-crop-reset]")?.addEventListener("click", () => { if (active) { active.zoom = 1; active.rotation = active.offsetX = active.offsetY = 0; draw(); } });
    modal.querySelector("[data-crop-confirm]")?.addEventListener("click", async () => { if (!active) return; const blob = await canvasToWebp(active); const file = new File([blob], "display-image.webp", {type: "image/webp"}); replaceInputFile(active.picker.querySelector("[data-file-input]"), file); const viewport = active.picker.querySelector("[data-display-image-preview]"); const url = URL.createObjectURL(blob); if (viewport) { const preview = new Image(); preview.alt = "Xem trước ảnh đã cắt"; preview.onload = () => { if (sourceUrl) URL.revokeObjectURL(sourceUrl); }; preview.src = url; viewport.replaceChildren(preview); } setStatus(active.picker, "Sẵn sàng tải lên.", "success"); bootstrap.Modal.getInstance(modal)?.hide(); });
    let dragging; modal.querySelector("canvas")?.addEventListener("pointerdown", (e) => { dragging = {x:e.clientX, y:e.clientY}; e.currentTarget.setPointerCapture(e.pointerId); });
    modal.querySelector("canvas")?.addEventListener("pointermove", (e) => { if (dragging && active) { active.offsetX += e.clientX - dragging.x; active.offsetY += e.clientY - dragging.y; dragging = {x:e.clientX,y:e.clientY}; draw(); } });
    modal.querySelector("canvas")?.addEventListener("pointerup", () => { dragging = null; });
  });
})();
