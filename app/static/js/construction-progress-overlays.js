(() => {
  const template = document.querySelector("template[data-item-row-template]");
  const entryTemplate = document.querySelector("template[data-entry-row-template]");
  const nextRowIndex = (rows, prefix) => Math.max(-1, ...[...rows.querySelectorAll("[name]")].map((input) => Number(input.name.match(new RegExp(`^${prefix}-(\\d+)-`))?.[1])).filter(Number.isInteger)) + 1;
  const refreshDeleteState = (form) => {
    const deleting = [...form.querySelectorAll("[data-delete-item]")].filter((input) => input.checked);
    form.querySelectorAll("[data-delete-preview]").forEach((preview) => preview.classList.toggle("d-none", !preview.closest("[data-progress-item-row]").querySelector("[data-delete-item]").checked));
    const confirmation = form.querySelector("[data-delete-confirm]");
    const save = form.querySelector("[data-batch-save]");
    if (confirmation) confirmation.classList.toggle("d-none", deleting.length === 0);
    if (save) save.classList.toggle("btn-warning", deleting.length > 0);
  };
  const bindRow = (row, form) => {
    row.querySelector("[data-remove-item-row]")?.addEventListener("click", () => row.remove());
    row.querySelector("[data-delete-item]")?.addEventListener("change", () => refreshDeleteState(form));
  };
  document.querySelectorAll("form[data-progress-group-form]").forEach((form) => {
    form.querySelectorAll("[data-progress-item-row]").forEach((row) => bindRow(row, form));
    form.querySelector("[data-add-item-row]")?.addEventListener("click", () => {
      const rows = form.querySelector("[data-item-rows]");
      const index = nextRowIndex(rows, "items");
      const fragment = template.content.cloneNode(true);
      fragment.querySelectorAll("[name]").forEach((input) => { input.name = input.name.replace("__INDEX__", index); });
      const row = fragment.querySelector("[data-progress-item-row]");
      rows.append(fragment);
      bindRow(rows.lastElementChild, form);
    });
    refreshDeleteState(form);
  });
  const filterEntryItems = (row) => {
    const groupId = row.querySelector("[data-entry-group]").value;
    const item = row.querySelector("[data-entry-item]");
    [...item.options].forEach((option) => {
      if (!option.dataset.groupId) return;
      const visible = option.dataset.groupId === groupId;
      option.hidden = !visible;
      option.disabled = !visible;
    });
    if (item.selectedOptions[0]?.disabled) item.value = "";
  };
  const bindEntryRow = (row) => {
    row.querySelector("[data-entry-group]").addEventListener("change", () => filterEntryItems(row));
    row.querySelector("[data-remove-entry-row]").addEventListener("click", () => row.remove());
    filterEntryItems(row);
  };
  document.querySelectorAll("form[data-progress-entry-form]").forEach((form) => {
    form.querySelectorAll("[data-progress-entry-row]").forEach(bindEntryRow);
    form.querySelector("[data-add-entry-row]").addEventListener("click", () => {
      const rows = form.querySelector("[data-entry-rows]");
      const index = nextRowIndex(rows, "entries");
      const fragment = entryTemplate.content.cloneNode(true);
      fragment.querySelectorAll("[name]").forEach((input) => { input.name = input.name.replace("__INDEX__", index); });
      rows.append(fragment);
      bindEntryRow(rows.lastElementChild);
    });
  });
  const reopen = document.querySelector("[data-open-progress-modal]")?.dataset.openProgressModal;
  if (reopen && window.bootstrap) new window.bootstrap.Modal(document.getElementById(reopen)).show();
})();
