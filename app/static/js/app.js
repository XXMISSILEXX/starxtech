document.addEventListener("DOMContentLoaded", () => {
  if (!document.querySelector("[data-daily-report-create-v2]")) initReportSections();
  initCustomSelects();
  initStatusBadges();
  initUploadPreviews();
  initIconChoices();
  initReportFormValidation();
  initConfirmActions();
  initAutoOpenModals();
  initPartnerDynamicFields();
  initRequiredFormValidation();
  initProjectUpdateDateValidation();
  initPartnerDepartmentSelect();
  initPartnerHeadToggle();
  initRelationshipPartnerProfileDisplay();
  initPartnerOrgChartModal();
  initDashboardSelectors();
});

function initDashboardSelectors() {
  document.querySelectorAll("[data-dashboard-selector]").forEach((select) => select.addEventListener("change", () => {
    if (select.value) window.location.assign(select.value);
  }));
  document.querySelectorAll("[data-dashboard-filter]").forEach((input) => {
    const select = document.querySelector(input.dataset.dashboardFilter);
    if (!select) return;
    input.addEventListener("input", () => {
      const term = input.value.trim().toLowerCase();
      Array.from(select.options).forEach((option) => { option.hidden = Boolean(term) && !option.dataset.search.includes(term); });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-permission-group]").forEach((group) => {
    const boxes = () => [...group.querySelectorAll("[data-group-permission]:not(:disabled)")];
    const counter = group.querySelector("[data-group-counter]");
    const sync = () => { const enabled = boxes(); counter.textContent = `Đã chọn ${enabled.filter((box) => box.checked).length}/${enabled.length} quyền`; };
    group.querySelectorAll("[data-group-permission]").forEach((box) => box.addEventListener("change", sync));
    group.querySelector("[data-group-select-all]")?.addEventListener("click", () => {
      if (group.querySelector(".text-bg-warning") && !window.confirm("Nhóm này có quyền nguy hiểm như xóa/lưu trữ/chia sẻ/quản trị. Bạn có chắc muốn chọn tất cả?")) return;
      boxes().forEach((box) => { box.checked = true; }); sync();
    });
    group.querySelector("[data-group-clear]")?.addEventListener("click", () => { boxes().forEach((box) => { box.checked = false; }); sync(); });
    sync();
  });
});

function initReportSections() {
  const container = document.querySelector("[data-sections]");
  if (!container || container.dataset.canWrite !== "1") {
    return;
  }

  const addButton = document.querySelector("[data-add-section]");
  const categories = JSON.parse(container.dataset.categories || "[]");
  const statuses = JSON.parse(container.dataset.statuses || "[]");

  const nextIndex = () => {
    const indexes = Array.from(container.querySelectorAll("[name^='sections-']"))
      .map((element) => {
        const match = element.name.match(/^sections-(\d+)-/);
        return match ? Number(match[1]) : -1;
      })
      .filter((index) => index >= 0);
    return indexes.length ? Math.max(...indexes) + 1 : 0;
  };

  const optionHtml = (items, selectedValue = "") =>
    items
      .map((item) => {
        const value = typeof item === "object" ? String(item.id) : String(item);
        const label = typeof item === "object" ? item.name : item;
        const icon = typeof item === "object" ? item.icon || "" : "";
        const iconKey = typeof item === "object" ? item.icon_key || "" : "";
        const tone = typeof item === "object" ? item.tone || "" : "";
        const selected = value === String(selectedValue) ? " selected" : "";
        return `<option value="${escapeHtml(value)}" data-icon="${escapeHtml(icon)}" data-icon-key="${escapeHtml(iconKey)}" data-tone="${escapeHtml(tone)}"${selected}>${escapeHtml(label)}</option>`;
      })
      .join("");

  const addSection = () => {
    const index = nextIndex();
    const section = document.createElement("div");
    section.className = "report-section p-3 mb-3";
    section.dataset.sectionRow = "";
    section.innerHTML = `
      <input type="hidden" name="sections-${index}-section-id" value="" data-server-section-id>
      <input type="hidden" name="sections-${index}-client-section-id" value="" data-client-section-id>
      <div class="row g-3">
        <div class="col-md-5">
          <label class="form-label">Hạng mục</label>
          <select class="form-select" name="sections-${index}-category_id" data-custom-select="category">
            <option value="">Chọn hạng mục</option>
            ${optionHtml(categories)}
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label">Trạng thái</label>
          <select class="form-select" name="sections-${index}-status" data-custom-select="status">
            ${optionHtml(statuses, "INFO")}
          </select>
        </div>
        <div class="col-md-3 d-flex align-items-end justify-content-md-end">
          <button class="btn btn-outline-danger btn-sm" type="button" data-remove-section><i class="bi bi-trash me-1"></i>Xóa</button>
        </div>
        <div class="col-12">
          <label class="form-label">Nội dung</label>
          <textarea class="form-control" name="sections-${index}-content" rows="3"></textarea>
        </div>
        <div class="col-12" data-report-attachment-picker>
          <div class="d-flex flex-wrap justify-content-between gap-2 align-items-baseline"><label class="form-label mb-0">Ảnh đính kèm</label><span class="small text-muted" data-attachment-counter aria-live="polite"></span></div>
          <label class="upload-dropzone" for="section-${index}-images" role="button" tabindex="0">
            <input class="visually-hidden" id="section-${index}-images" name="sections-${index}-images" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" multiple data-report-attachment-input>
            <span class="upload-title"><i class="bi bi-images me-1"></i>Chọn ảnh đính kèm</span>
            <span class="upload-help" data-attachment-help>Kéo thả ảnh vào đây hoặc bấm để chọn</span>
          </label>
          <div class="upload-preview-grid mt-2" data-attachment-preview></div>
        </div>
      </div>
    `;
    container.appendChild(section);
    initCustomSelects(section);
    document.dispatchEvent(new CustomEvent("starx:report-section-added", { detail: section }));
  };

  container.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-section]");
    if (!removeButton) {
      return;
    }
    const row = removeButton.closest("[data-section-row]");
    if (row) {
      const clientSectionId = row.querySelector("[data-client-section-id]")?.value || "";
      row.remove();
      document.dispatchEvent(new CustomEvent("starx:report-section-removed", { detail: clientSectionId }));
    }
  });

  if (addButton) {
    addButton.addEventListener("click", addSection);
  }

  if (!container.querySelector("[data-section-row]")) {
    addSection();
  }
}

function initCustomSelects(root = document) {
  root.querySelectorAll("select[data-custom-select]").forEach((select) => {
    if (select.dataset.customReady === "1") {
      return;
    }
    select.dataset.customReady = "1";
    select.classList.add("custom-select-native");

    const wrapper = document.createElement("div");
    wrapper.className = `custom-select custom-select-${select.dataset.customSelect || "default"}`;
    if (select.disabled) {
      wrapper.classList.add("disabled");
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "custom-select-toggle";
    button.disabled = select.disabled;
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");

    const menu = document.createElement("div");
    const menuId = `status-selector-${crypto.randomUUID?.() || Math.random().toString(36).slice(2)}`;
    menu.id = menuId;
    menu.className = "custom-select-menu";
    menu.setAttribute("role", "listbox");
    button.setAttribute("aria-controls", menuId);

    Array.from(select.options).forEach((option) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "custom-select-option";
      item.dataset.value = option.value;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.selected));
      item.innerHTML = optionMarkup(option, select.dataset.customSelect);
      const choose = () => {
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        closeCustomSelects();
        button.focus();
      };
      item.addEventListener("click", choose);
      item.addEventListener("keydown", (event) => {
        const choices = [...menu.querySelectorAll(".custom-select-option")];
        const index = choices.indexOf(item);
        if (["Enter", " "].includes(event.key)) { event.preventDefault(); choose(); }
        else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) { event.preventDefault(); const next = event.key === "Home" ? 0 : event.key === "End" ? choices.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length; choices[next]?.focus(); }
        else if (event.key === "Escape") { closeCustomSelects(); button.focus(); }
      });
      menu.appendChild(item);
    });

    select.addEventListener("change", () => {
      updateCustomSelect(select, button, menu);
    });

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const wasOpen = wrapper.classList.contains("open");
      closeCustomSelects();
      wrapper.classList.toggle("open", !wasOpen);
      button.setAttribute("aria-expanded", String(!wasOpen));
    });
    button.addEventListener("keydown", (event) => {
      const choices = [...menu.querySelectorAll(".custom-select-option")];
      const current = Math.max(0, choices.findIndex((item) => item.dataset.value === select.value));
      if (["Enter", " "].includes(event.key)) {
        event.preventDefault();
        if (!wrapper.classList.contains("open")) button.click(); else choices[current]?.focus();
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? choices.length - 1 : (current + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
        if (!wrapper.classList.contains("open")) button.click();
        choices[next]?.focus();
      } else if (event.key === "Escape") { closeCustomSelects(); button.focus(); }
    });

    wrapper.append(button, menu);
    select.insertAdjacentElement("afterend", wrapper);
    updateCustomSelect(select, button, menu);
  });
}

function closeCustomSelects() {
  document.querySelectorAll(".custom-select.open").forEach((select) => {
    select.classList.remove("open");
    select.querySelector(".custom-select-toggle")?.setAttribute("aria-expanded", "false");
  });
}

document.addEventListener("click", closeCustomSelects);

function updateCustomSelect(select, button, menu) {
  const selected = select.selectedOptions[0] || select.options[0];
  button.innerHTML = optionMarkup(selected, select.dataset.customSelect);
  menu.querySelectorAll(".custom-select-option").forEach((item) => {
    item.classList.toggle("active", item.dataset.value === select.value);
    item.setAttribute("aria-selected", String(item.dataset.value === select.value));
  });
}

function optionMarkup(option, type) {
  const label = option.textContent || "Chọn";
  const tone = option.dataset.tone || "";
  const iconHtml = type === "status" ? `<span class="status-icon-chip status-dot-${escapeHtml(tone || "info")}">${statusIconMarkup(option.dataset.iconKey || "info-circle-fill")}</span>` : renderCategoryIcon(option.dataset.icon || "");
  const selected = type === "status" ? '<span class="custom-select-check" aria-hidden="true">✓</span>' : "";
  return `<span class="custom-select-label">${iconHtml}<span>${escapeHtml(label)}</span></span>${selected}`;
}

function statusIconMarkup(iconKey) {
  const sprite = document.documentElement.dataset.statusIconSprite || "";
  const safeKey = /^[a-z0-9-]+$/.test(iconKey) ? iconKey : "info-circle-fill";
  if (sprite) return `<svg class="status-svg" aria-hidden="true" focusable="false"><use href="${escapeHtml(sprite)}#${safeKey}"></use></svg>`;
  return '<svg class="status-svg" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="7"></circle><path d="M8 4.5v.1M8 7v4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"></path></svg>';
}

function initStatusBadges(root = document) {
  root.querySelectorAll("[data-status-icon-key]").forEach((badge) => {
    if (badge.dataset.statusIconReady === "1") return;
    badge.dataset.statusIconReady = "1";
    badge.insertAdjacentHTML("afterbegin", `${statusIconMarkup(badge.dataset.statusIconKey)} `);
  });
}

function renderCategoryIcon(icon) {
  const value = String(icon || "📌").trim();
  const normalized = value.startsWith("bi-") ? value.slice(3) : value;
  if (/^[a-z0-9][a-z0-9-]{0,48}$/.test(normalized)) {
    return `<i class="bi bi-${escapeHtml(normalized)}"></i>`;
  }
  return `<span class="category-emoji">${escapeHtml(value || "📌")}</span>`;
}

function initUploadPreviews(root = document) {
  root.querySelectorAll("[data-upload-input]").forEach((input) => {
    if (input.dataset.previewReady === "1") {
      return;
    }
    input.dataset.previewReady = "1";
    const dropzone = input.closest(".upload-dropzone");
    const preview = (dropzone ? dropzone.parentElement.querySelector("[data-upload-preview]") : null)
      || input.parentElement.querySelector("[data-upload-preview]");
    if (!preview) {
      return;
    }

    input.addEventListener("change", () => renderUploadPreview(input, preview));

    if (dropzone) {
      ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.classList.add("dragover");
        });
      });
      ["dragleave", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.classList.remove("dragover");
        });
      });
      dropzone.addEventListener("drop", (event) => {
        input.files = event.dataTransfer.files;
        renderUploadPreview(input, preview);
      });
    }
  });
}

function renderUploadPreview(input, preview) {
  preview.innerHTML = "";
  const files = Array.from(input.files || []);
  files.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "upload-preview-item";

    const media = document.createElement("div");
    media.className = "upload-preview-media";
    if (isPreviewableImage(file)) {
      const image = document.createElement("img");
      image.alt = file.name;
      image.src = URL.createObjectURL(file);
      image.onload = () => URL.revokeObjectURL(image.src);
      media.appendChild(image);
    } else if (/\.(heic|heif)$/i.test(file.name)) {
      media.innerHTML = '<span class="small text-muted">Đang tạo xem trước…</span>';
      previewHeic(file).then((url) => {
        const image = document.createElement("img"); image.alt = file.name; image.src = url;
        image.onload = () => URL.revokeObjectURL(url); media.replaceChildren(image);
      }).catch(() => { media.innerHTML = '<i class="bi bi-file-earmark-image"></i>'; });
    } else {
      media.innerHTML = '<i class="bi bi-file-earmark"></i>';
    }

    const name = document.createElement("div");
    name.className = "upload-preview-name";
    name.textContent = file.name;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn-sm btn-outline-danger";
    remove.innerHTML = '<i class="bi bi-x-lg"></i>';
    remove.setAttribute("aria-label", "Xóa ảnh khỏi danh sách");
    remove.addEventListener("click", () => {
      removeFileAt(input, index);
      renderUploadPreview(input, preview);
    });

    item.append(media, name, remove);
    preview.appendChild(item);
  });
}

async function previewHeic(file) {
  const data = new FormData(); data.append("image", file);
  const token = document.querySelector('input[name="csrf_token"]')?.value;
  if (token) data.append("csrf_token", token);
  const response = await fetch("/media-display-preview", { method: "POST", body: data, credentials: "same-origin" });
  if (!response.ok) throw new Error("preview failed");
  return URL.createObjectURL(await response.blob());
}

function isPreviewableImage(file) {
  const extension = (file.name.split(".").pop() || "").toLowerCase();
  return ["jpg", "jpeg", "png", "webp"].includes(extension) && ["image/jpeg", "image/png", "image/webp"].includes(file.type);
}

function removeFileAt(input, indexToRemove) {
  const transfer = new DataTransfer();
  Array.from(input.files || []).forEach((file, index) => {
    if (index !== indexToRemove) {
      transfer.items.add(file);
    }
  });
  input.files = transfer.files;
}

function initIconChoices(root = document) {
  const iconInput = root.querySelector("#icon");
  if (!iconInput) {
    return;
  }
  root.querySelectorAll("[data-icon-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      iconInput.value = button.dataset.iconChoice || "";
      root.querySelectorAll("[data-icon-choice]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      iconInput.focus();
    });
  });
}

function initReportFormValidation() {
  const container = document.querySelector("[data-sections]");
  if (!container) {
    return;
  }
  const form = container.closest("form");
  if (!form) {
    return;
  }

  form.addEventListener("submit", (event) => {
    const invalid = [];
    container.querySelectorAll("[data-section-row]").forEach((row) => {
      const category = row.querySelector("select[name$='-category_id']");
      const status = row.querySelector("select[name$='-status']");
      const content = row.querySelector("textarea[name$='-content']");

      if (category && !category.value) {
        setFieldError(category, "Vui lòng chọn hạng mục.");
        invalid.push(category);
      } else if (category) {
        clearFieldError(category);
      }

      if (status && !status.value) {
        setFieldError(status, "Vui lòng chọn trạng thái.");
        invalid.push(status);
      } else if (status) {
        clearFieldError(status);
      }

      if (content && !content.value.trim()) {
        setFieldError(content, "Mỗi phần báo cáo phải có nội dung.");
        invalid.push(content);
      } else if (content) {
        clearFieldError(content);
      }
    });

    if (invalid.length) {
      event.preventDefault();
      invalid[0].scrollIntoView({ behavior: "smooth", block: "center" });
      invalid[0].focus({ preventScroll: true });
    }
  });
}

function setFieldError(field, message) {
  field.classList.add("is-invalid");
  let feedback = field.parentElement.querySelector(".invalid-feedback[data-js-error]");
  if (!feedback) {
    feedback = document.createElement("div");
    feedback.className = "invalid-feedback";
    feedback.dataset.jsError = "1";
    field.insertAdjacentElement("afterend", feedback);
  }
  feedback.textContent = message;
}

function clearFieldError(field) {
  field.classList.remove("is-invalid");
  const feedback = field.parentElement.querySelector(".invalid-feedback[data-js-error]");
  if (feedback) {
    feedback.remove();
  }
}

function initConfirmActions() {
  const modalElement = document.querySelector("#confirmActionModal");
  const messageElement = modalElement ? modalElement.querySelector("[data-confirm-message]") : null;
  const titleElement = modalElement ? modalElement.querySelector("[data-confirm-title]") : null;
  const acceptButton = modalElement ? modalElement.querySelector("[data-confirm-accept]") : null;
  const modal = modalElement && typeof bootstrap !== "undefined" ? new bootstrap.Modal(modalElement) : null;
  let pendingTrigger = null;

  if (acceptButton) {
    acceptButton.addEventListener("click", () => {
      if (!pendingTrigger) {
        return;
      }
      const trigger = pendingTrigger;
      pendingTrigger = null;
      if (modal) {
        modal.hide();
      }

      const form = trigger.form || trigger.closest("form");
      if (form) {
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit(trigger);
        } else {
          form.submit();
        }
        return;
      }

      if (trigger.href) {
        window.location.href = trigger.href;
      }
    });
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-confirm]");
    if (!trigger) {
      return;
    }

    event.preventDefault();
    pendingTrigger = trigger;
    const message = trigger.dataset.confirm || "Bạn chắc chắn muốn tiếp tục?";
    const title = trigger.dataset.confirmTitle || "Xác nhận thao tác";
    const acceptLabel = trigger.dataset.confirmAccept || "Xác nhận";
    if (messageElement) {
      messageElement.textContent = message;
    }
    if (titleElement) titleElement.textContent = title;
    if (acceptButton) acceptButton.textContent = acceptLabel;
    if (modal) {
      modal.show();
      return;
    }

    if (window.confirm(message)) {
      const form = trigger.form || trigger.closest("form");
      if (form) {
        form.submit();
      } else if (trigger.href) {
        window.location.href = trigger.href;
      }
    }
  });
}

function initAutoOpenModals() {
  document.querySelectorAll(".modal[data-open-on-load='1']").forEach((element) => {
    if (typeof bootstrap !== "undefined") bootstrap.Modal.getOrCreateInstance(element).show();
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function initPartnerDynamicFields() {
  const container = document.querySelector("[data-partner-fields]");
  if (!container) {
    return;
  }

  const definitions = JSON.parse(container.dataset.definitions || "[]");
  const collections = JSON.parse(container.dataset.collections || "[]");
  const fieldSelect = document.querySelector("[data-partner-field-select]");
  const collectionSelect = document.querySelector("[data-partner-collection-select]");
  const addButton = document.querySelector("[data-add-partner-field]");
  let nextIndex = Number(container.dataset.nextIndex || "0");

  const selectedIds = () =>
    new Set(Array.from(container.querySelectorAll("[data-field-row]")).map((row) => String(row.dataset.fieldId)));

  const removeEmptyState = () => {
    const empty = container.querySelector("[data-empty-fields]");
    if (empty) {
      empty.remove();
    }
  };

  const inputHtml = (field, inputName) => {
    if (field.field_type === "textarea") {
      return `<textarea class="form-control" name="${inputName}" rows="3"></textarea>`;
    }
    if (field.field_type === "number") {
      return `<input class="form-control" type="number" step="any" name="${inputName}">`;
    }
    if (field.field_type === "date") {
      return `<input class="form-control" type="date" name="${inputName}">`;
    }
    if (field.field_type === "boolean") {
      return `<div class="form-check"><input class="form-check-input" type="checkbox" name="${inputName}"><label class="form-check-label">Có</label></div>`;
    }
    if (field.field_type === "select") {
      const options = (field.options || []).map((option) => `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`).join("");
      return `<select class="form-select" name="${inputName}"><option value="">Chọn</option>${options}</select>`;
    }
    if (field.field_type === "multi_select") {
      const options = (field.options || []).map((option) => `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`).join("");
      return `<select class="form-select" name="${inputName}" multiple>${options}</select>`;
    }
    const type = field.field_type === "email" ? "email" : field.field_type === "url" ? "url" : "text";
    return `<input class="form-control" type="${type}" name="${inputName}">`;
  };

  const addField = (fieldId) => {
    const field = definitions.find((item) => String(item.id) === String(fieldId));
    if (!field || selectedIds().has(String(field.id))) {
      return;
    }
    removeEmptyState();
    const index = nextIndex++;
    const row = document.createElement("div");
    row.className = "border rounded p-3";
    row.dataset.fieldRow = "";
    row.dataset.fieldId = String(field.id);
    row.innerHTML = `
      <div class="d-flex justify-content-between gap-2 mb-2">
        <label class="form-label mb-0">${escapeHtml(field.label)}</label>
        <button class="btn btn-sm btn-outline-danger" type="button" data-remove-field aria-label="Xóa trường"><i class="bi bi-x-lg"></i></button>
      </div>
      <input type="hidden" name="fields[${index}][field_definition_id]" value="${escapeHtml(field.id)}">
      ${inputHtml(field, `fields[${index}][value]`)}
    `;
    container.appendChild(row);
  };

  if (addButton && fieldSelect) {
    addButton.addEventListener("click", () => addField(fieldSelect.value));
  }

  if (collectionSelect) {
    collectionSelect.addEventListener("change", () => {
      const collection = collections.find((item) => String(item.id) === String(collectionSelect.value));
      if (collection) {
        collection.field_ids.forEach(addField);
      }
      collectionSelect.value = "";
    });
  }

  container.addEventListener("click", (event) => {
    const remove = event.target.closest("[data-remove-field]");
    if (!remove) {
      return;
    }
    remove.closest("[data-field-row]").remove();
    if (!container.querySelector("[data-field-row]")) {
      container.innerHTML = '<div class="text-muted small" data-empty-fields>Chưa có thông tin mở rộng.</div>';
    }
  });
}

function initRequiredFormValidation() {
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.matches("[data-validate-required]")) {
      return;
    }
    const invalid = [];
    form.querySelectorAll("[required]").forEach((field) => {
      if (!field.value.trim()) {
        let message = "Vui lòng nhập thông tin bắt buộc.";
        if (field.name === "partner_id") {
          message = "Vui lòng chọn đối tác.";
        } else if (field.name === "relationship_type") {
          message = "Vui lòng chọn loại quan hệ.";
        } else if (field.tagName === "SELECT") {
          message = "Vui lòng chọn thông tin.";
        }
        setFieldError(field, message);
        invalid.push(field);
      } else {
        clearFieldError(field);
      }
    });
    if (invalid.length) {
      event.preventDefault();
      invalid[0].scrollIntoView({ behavior: "smooth", block: "center" });
      invalid[0].focus({ preventScroll: true });
    }
  });
}

function initProjectUpdateDateValidation() {
  document.querySelectorAll("[data-project-update-form]").forEach((form) => {
    const field = form.querySelector("[data-project-update-date]");
    if (!field) {
      return;
    }
    const validate = () => {
      const isFutureDate = Boolean(field.value && field.max && field.value > field.max);
      if (isFutureDate) {
        setFieldError(field, "Ngày cập nhật không được lớn hơn ngày hôm nay.");
      } else {
        clearFieldError(field);
      }
      return isFutureDate;
    };
    field.addEventListener("input", validate);
    field.addEventListener("change", validate);
    form.addEventListener("submit", (event) => {
      if (!validate()) {
        return;
      }
      event.preventDefault();
      field.scrollIntoView({ behavior: "smooth", block: "center" });
      field.focus({ preventScroll: true });
    });
  });
}

function initPartnerDepartmentSelect() {
  const companySelect = document.querySelector("[data-company-select]");
  const departmentSelect = document.querySelector("[data-department-select]");
  if (!companySelect || !departmentSelect) {
    return;
  }
  const message = document.querySelector("[data-no-departments-message]");
  const syncDepartments = () => {
    const companyId = companySelect.value;
    let visibleCount = 0;
    Array.from(departmentSelect.options).forEach((option) => {
      if (!option.value) {
        option.hidden = false;
        return;
      }
      const visible = option.dataset.companyId === companyId;
      option.hidden = !visible;
      if (visible) {
        visibleCount += 1;
      }
      if (!visible && option.selected) {
        option.selected = false;
      }
    });
    if (message) {
      message.classList.toggle("d-none", !companyId || visibleCount > 0);
    }
  };
  companySelect.addEventListener("change", syncDepartments);
  syncDepartments();
}

function initPartnerHeadToggle() {
  const departmentSelect = document.querySelector("[data-department-select]");
  const wrapper = document.querySelector("[data-department-head-wrapper]");
  const checkbox = document.querySelector("[data-department-head-checkbox]");
  const positionInput = document.querySelector("[data-position-input]");
  if (!departmentSelect || !wrapper || !checkbox || !positionInput) {
    return;
  }
  const sync = () => {
    const option = departmentSelect.selectedOptions[0];
    const isSpecial = option && option.dataset.isSpecial === "1";
    wrapper.classList.toggle("d-none", Boolean(isSpecial));
    if (isSpecial) {
      checkbox.checked = false;
      positionInput.readOnly = false;
      return;
    }
    if (checkbox.checked) {
      positionInput.value = "Trưởng phòng";
      positionInput.readOnly = true;
    } else {
      positionInput.readOnly = false;
    }
  };
  departmentSelect.addEventListener("change", sync);
  checkbox.addEventListener("change", sync);
  sync();
}

function initRelationshipPartnerProfileDisplay() {
  const partnerSelect = document.querySelector("[data-relation-partner-select]");
  const departmentField = document.querySelector("[data-relation-department-display]");
  const positionField = document.querySelector("[data-relation-position-display]");
  if (!partnerSelect || !departmentField || !positionField) {
    return;
  }
  const sync = () => {
    const option = partnerSelect.selectedOptions[0];
    if (!option || !option.value) {
      departmentField.value = "Chưa chọn đối tác";
      positionField.value = "Chưa chọn đối tác";
      return;
    }
    departmentField.value = option.dataset.department || "Chưa có phòng ban";
    positionField.value = option.dataset.position || "Chưa có vị trí";
  };
  partnerSelect.addEventListener("change", sync);
  sync();
}

function initPartnerOrgChartModal() {
  const modalElement = document.querySelector("#departmentSummaryModal");
  const modalBody = modalElement ? modalElement.querySelector("[data-department-modal-body]") : null;
  if (!modalElement || !modalBody || typeof bootstrap === "undefined") {
    return;
  }
  const modal = new bootstrap.Modal(modalElement);

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-department-node]");
    if (!trigger) {
      return;
    }
    const url = trigger.dataset.departmentSummaryUrl;
    if (!url) {
      return;
    }
    modalBody.innerHTML = '<div class="text-muted">Đang tải dữ liệu...</div>';
    modal.show();
    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Không tải được dữ liệu phòng ban.");
        }
        return response.text();
      })
      .then((html) => {
        modalBody.innerHTML = html;
      })
      .catch(() => {
        modalBody.innerHTML = '<div class="alert alert-danger mb-0">Không tải được dữ liệu phòng ban. Vui lòng thử lại.</div>';
      });
  });
}
document.addEventListener("DOMContentLoaded", () => {
  const presetData = document.getElementById("project-membership-presets");
  if (!presetData) return;
  const presets = JSON.parse(presetData.dataset.presets || "{}");
  document.querySelectorAll(".membership-form").forEach((form) => {
    const select = form.querySelector(".membership-preset");
    if (!select) return;
    select.addEventListener("change", () => form.querySelectorAll(".membership-capability").forEach((box) => {
      box.checked = (presets[select.value] || []).includes(box.name);
    }));
    if (!form.querySelector(".membership-capability:checked")) {
      select.dispatchEvent(new Event("change"));
    }
  });
  const users = JSON.parse(presetData.dataset.users || "[]");
  document.querySelectorAll("[data-user-search]").forEach((input) => input.addEventListener("input", () => {
    const form = input.closest("form"), results = form.querySelector("[data-user-results]");
    const query = input.value.toLowerCase().trim();
    const matches = users.filter((user) => `${user.name} ${user.username} ${user.email}`.toLowerCase().includes(query));
    results.innerHTML = query ? (matches.length ? matches.map((user) => `<button type="button" class="list-group-item list-group-item-action" data-picker-id="${user.id}"><strong>${escapeHtml(user.name)}</strong><small class="d-block text-muted">${escapeHtml(user.username)} · ${escapeHtml(user.email)} · ${escapeHtml(user.role)}</small></button>`).join("") : '<div class="list-group-item text-muted">Không tìm thấy người dùng phù hợp.</div>') : "";
  }));
  document.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-picker-id]"); if (!choice) return;
    const form = choice.closest("form"), user = users.find((item) => String(item.id) === choice.dataset.pickerId);
    form.querySelector("[data-selected-user-id]").value = user.id;
    form.querySelector("[data-selected-user]").innerHTML = `<span class="badge text-bg-primary">${escapeHtml(user.name)} · ${escapeHtml(user.username)}</span> <button type="button" class="btn btn-link btn-sm p-0" data-clear-user>Đổi</button>`;
    form.querySelector("[data-user-results]").innerHTML = "";
  });
  document.addEventListener("click", (event) => { if (event.target.matches("[data-clear-user]")) { const form = event.target.closest("form"); form.querySelector("[data-selected-user-id]").value = ""; form.querySelector("[data-selected-user]").innerHTML = ""; } });
});
