(() => {
  let state = {scale: 1, rotation: 0, x: 0, y: 0, tools: false};
  let media = null;
  const reset = () => { state = {scale: 1, rotation: 0, x: 0, y: 0, tools: false}; if (media) media.style.transform = ""; };
  const transform = () => { if (media) media.style.transform = `translate(${state.x}px, ${state.y}px) rotate(${state.rotation}deg) scale(${state.scale})`; };
  document.addEventListener("DOMContentLoaded", () => {
    const el = document.getElementById("mediaPreviewModal"); if (!el || !window.bootstrap) return;
    const modal = bootstrap.Modal.getOrCreateInstance(el); const body = el.querySelector("[data-media-preview-body]"); const title = el.querySelector("[data-media-preview-title]"); const download = el.querySelector("[data-media-preview-download]"); const tools = el.querySelector("[data-media-image-tools]");
    const open = ({url, name, downloadUrl, type = "image", imageTools = false}) => {
      reset(); body.replaceChildren(); title.textContent = name || "Xem trước"; state.tools = imageTools && type === "image"; tools.classList.toggle("d-none", !state.tools);
      media = document.createElement(type === "video" ? "video" : "img"); media.className = "media-viewer-media"; media.src = url;
      if (type === "video") { media.controls = true; media.preload = "metadata"; } else { media.alt = title.textContent; }
      body.append(media); if (downloadUrl) { download.href = downloadUrl; download.classList.remove("d-none"); } else download.classList.add("d-none"); modal.show();
    };
    window.openMediaPreview = open;
    document.addEventListener("click", (event) => { const trigger = event.target.closest("[data-media-preview-url]"); if (!trigger) return; event.preventDefault(); open({url: trigger.dataset.mediaPreviewUrl, name: trigger.dataset.mediaPreviewName, downloadUrl: trigger.dataset.mediaPreviewDownload, type: trigger.dataset.mediaPreviewType || "image", imageTools: trigger.dataset.mediaPreviewTools === "1"}); });
    [["[data-viewer-zoom-in]", () => state.scale = Math.min(6, state.scale + .2)], ["[data-viewer-zoom-out]", () => state.scale = Math.max(.3, state.scale - .2)], ["[data-viewer-rotate-left]", () => state.rotation -= 90], ["[data-viewer-rotate-right]", () => state.rotation += 90], ["[data-viewer-reset]", reset]].forEach(([selector, action]) => el.querySelector(selector)?.addEventListener("click", () => { action(); transform(); }));
    body.addEventListener("wheel", (event) => { if (!state.tools) return; event.preventDefault(); state.scale = Math.max(.3, Math.min(6, state.scale + (event.deltaY < 0 ? .15 : -.15))); transform(); }, {passive:false});
    let drag; body.addEventListener("pointerdown", (event) => { if (state.tools && state.scale > 1 && media?.tagName === "IMG") { drag = {x:event.clientX,y:event.clientY}; body.setPointerCapture(event.pointerId); }}); body.addEventListener("pointermove", (event) => { if (drag) { state.x += event.clientX-drag.x; state.y += event.clientY-drag.y; drag={x:event.clientX,y:event.clientY}; transform(); }}); body.addEventListener("pointerup", () => drag = null);
    el.addEventListener("hidden.bs.modal", () => { if (media?.tagName === "VIDEO") { media.pause(); media.removeAttribute("src"); media.load(); } body.replaceChildren(); media = null; reset(); });
  });
})();
