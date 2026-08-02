(() => {
  const template = document.querySelector("template[data-item-row-template]");
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
      const index = rows.querySelectorAll("[data-progress-item-row]").length;
      const fragment = template.content.cloneNode(true);
      fragment.querySelectorAll("[name]").forEach((input) => { input.name = input.name.replace("__INDEX__", index); });
      const row = fragment.querySelector("[data-progress-item-row]");
      rows.append(fragment);
      bindRow(rows.lastElementChild, form);
    });
    refreshDeleteState(form);
  });
  const reopen = document.querySelector("[data-open-progress-modal]")?.dataset.openProgressModal;
  if (reopen && window.bootstrap) new window.bootstrap.Modal(document.getElementById(reopen)).show();
})();
