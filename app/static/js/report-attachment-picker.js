(() => {
  const allowed = new Set(["jpg", "jpeg", "png", "webp", "heic", "heif"]);
  const ext = (f) => (f.name.split(".").pop() || "").toLowerCase();
  const previewHeif = async (file, token) => { const data = new FormData(); data.append("image", file); data.append("csrf_token", token); const res = await fetch("/media-display-preview", {method:"POST",body:data,credentials:"same-origin"}); if (!res.ok) throw new Error(); return URL.createObjectURL(await res.blob()); };
  const render = async (input) => {
    const root = input.closest("[data-report-attachment-picker]"); const out = root?.querySelector("[data-attachment-preview]"); if (!out) return; out.replaceChildren();
    const token = input.closest("form")?.querySelector('[name="csrf_token"]')?.value || "";
    [...input.files].forEach(async (file, index) => { const card=document.createElement("div"); card.className="upload-preview-item"; const media=document.createElement("div"); media.className="upload-preview-media"; const label=document.createElement("div"); label.className="upload-preview-name"; label.textContent=file.name; const remove=document.createElement("button"); remove.type="button"; remove.className="btn btn-sm btn-outline-danger"; remove.textContent="×"; remove.onclick=()=>{const dt=new DataTransfer();[...input.files].forEach((f,i)=>i!==index&&dt.items.add(f));input.files=dt.files;render(input);}; card.append(media,label,remove); out.append(card);
      if (!allowed.has(ext(file))) { media.textContent="Tệp không hợp lệ"; return; } const img=new Image(); img.alt=file.name; try { const url=["heic","heif"].includes(ext(file)) ? await previewHeif(file,token) : URL.createObjectURL(file); img.src=url; img.onload=()=>URL.revokeObjectURL(url); media.replaceChildren(img); } catch (_) { media.textContent="Không thể tạo xem trước"; }
    });
  };
  document.addEventListener("change", (event) => { const input=event.target.closest("[data-report-attachment-input]"); if (input) render(input); });
  document.addEventListener("click", (event) => { const zone = event.target.closest("[data-report-attachment-picker] .upload-dropzone"); if (!zone || event.target.matches("input")) return; event.preventDefault(); zone.querySelector("[data-report-attachment-input]")?.click(); });
  document.addEventListener("keydown", (event) => { const zone = event.target.closest("[data-report-attachment-picker] .upload-dropzone"); if (zone && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); zone.querySelector("[data-report-attachment-input]")?.click(); } });
  document.addEventListener("drop", (event) => { const zone=event.target.closest("[data-report-attachment-picker]"); if (!zone) return; event.preventDefault(); const input=zone.querySelector("[data-report-attachment-input]"); input.files=event.dataTransfer.files; render(input); });
  document.addEventListener("dragover", (event)=>{if(event.target.closest("[data-report-attachment-picker]"))event.preventDefault();});
})();
