/* Persistent issue section editor.  It deliberately does not share the daily-report editor. */
(() => {
  const start = () => {
    const container = document.querySelector("[data-issue-sections]");
    if (!container || container.dataset.canWrite !== "1") return;

    const addButton = document.querySelector("[data-add-issue-section]");
    const categories = JSON.parse(container.dataset.categories || "[]");
    const owners = JSON.parse(container.dataset.owners || "[]");
    const severityOptions = JSON.parse(container.dataset.severityOptions || "[]");
    const statusOptions = JSON.parse(container.dataset.statusOptions || "[]");

    const rows = () => [...container.querySelectorAll("[data-issue-section-row]")];
    const indexes = () => rows().flatMap((row) => [...row.querySelectorAll("[name^='sections-']")])
      .map((field) => Number((field.name.match(/^sections-(\d+)-/) || [])[1]))
      .filter(Number.isInteger);
    const nextIndex = () => (indexes().length ? Math.max(...indexes()) + 1 : 0);
    const option = (value, label, selected = false) => {
      const element = document.createElement("option");
      element.value = String(value); element.textContent = label; element.selected = selected;
      return element;
    };
    const selectedCategoryIds = (except = null) => new Set(rows()
      .filter((row) => row !== except)
      .map((row) => row.querySelector("[data-issue-section-category]")?.value)
      .filter(Boolean));

    const updateNumbers = () => rows().forEach((row, index) => {
      row.querySelector("[data-issue-section-title-text]").textContent = `Hạng mục ${index + 1}`;
    });

    const setTitleIcon = (row, categoryId) => {
      const icon = row.querySelector("[data-issue-section-title-icon]");
      const category = categories.find((item) => String(item.id) === String(categoryId));
      if (!category && categoryId) return;
      icon.replaceChildren();
      if (!category) {
        icon.hidden = true;
        return;
      }
      icon.innerHTML = category.icon || "";
      icon.hidden = false;
    };

    const setDetailsVisible = (row, visible) => {
      const details = row.querySelector("[data-issue-section-details]");
      details.hidden = !visible;
      details.querySelectorAll("input, select, textarea").forEach((field) => { field.disabled = !visible; });
    };

    const refreshCategories = () => rows().forEach((row) => {
      const select = row.querySelector("[data-issue-section-category]");
      const selected = select.value;
      const selectedOption = [...select.options].find((item) => item.value === selected);
      const selectedLabel = selectedOption?.textContent || selected;
      const usedElsewhere = selectedCategoryIds(row);
      select.replaceChildren(option("", "Chọn hạng mục", !selected));
      categories.forEach((category) => {
        if (!usedElsewhere.has(String(category.id)) || String(category.id) === selected) {
          select.append(option(category.id, category.name, String(category.id) === selected));
        }
      });
      if (selected && !categories.some((category) => String(category.id) === selected)) {
        select.append(option(selected, selectedLabel, true));
      }
      setDetailsVisible(row, Boolean(selected));
      setTitleIcon(row, selected);
    });

    const field = (tag, name, value = "") => {
      const element = document.createElement(tag);
      element.name = name;
      if (tag === "textarea") element.value = value;
      else element.value = value;
      return element;
    };
    const labeled = (label, control, classes = "col-md-4") => {
      const wrap = document.createElement("div"); wrap.className = classes;
      const caption = document.createElement("label"); caption.className = "form-label"; caption.textContent = label;
      wrap.append(caption, control); return wrap;
    };
    const selectField = (name, values, selected) => {
      const select = field("select", name); select.className = "form-select"; select.required = true;
      values.forEach((item) => select.append(option(item.value, item.label, item.value === selected)));
      return select;
    };
    const createRow = () => {
      const index = nextIndex();
      const row = document.createElement("section");
      row.className = "border rounded p-3 mb-3"; row.dataset.issueSectionRow = "";
      const heading = document.createElement("div"); heading.className = "d-flex justify-content-between align-items-center gap-2 mb-3";
      const title = document.createElement("h3"); title.className = "h6 mb-0"; title.dataset.issueSectionTitle = "";
      const titleIcon = document.createElement("span"); titleIcon.className = "me-1"; titleIcon.dataset.issueSectionTitleIcon = ""; titleIcon.hidden = true;
      const titleText = document.createElement("span"); titleText.dataset.issueSectionTitleText = "";
      title.append(titleIcon, titleText);
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "btn btn-outline-danger btn-sm"; remove.dataset.removeIssueSection = ""; remove.textContent = "Xóa hạng mục";
      heading.append(title, remove);
      const sectionId = field("input", `sections-${index}-section-id`); sectionId.type = "hidden";
      const category = field("select", `sections-${index}-category_id`); category.className = "form-select"; category.required = true; category.dataset.issueSectionCategory = "";
      const categoryRow = document.createElement("div"); categoryRow.className = "row g-3"; categoryRow.append(labeled("Loại hạng mục", category, "col-md-6"));
      const details = document.createElement("div"); details.className = "row g-3 mt-0"; details.dataset.issueSectionDetails = "";
      const severity = selectField(`sections-${index}-severity`, severityOptions, "MEDIUM");
      const status = selectField(`sections-${index}-status`, statusOptions, "OPEN");
      const dueDate = field("input", `sections-${index}-due_date`); dueDate.type = "date"; dueDate.className = "form-control";
      const owner = field("select", `sections-${index}-owner_user_id`); owner.className = "form-select"; owner.append(option("", "👤 Chưa có người phụ trách", true)); owners.forEach((item) => owner.append(option(item.id, `👤 ${item.name}`)));
      const description = field("textarea", `sections-${index}-description`); description.className = "form-control"; description.rows = 3;
      const solution = field("textarea", `sections-${index}-proposed_solution`); solution.className = "form-control"; solution.rows = 3;
      details.append(
        labeled("Mức độ", severity), labeled("Trạng thái", status), labeled("Hạn xử lý", dueDate),
        labeled("Người phụ trách", owner, "col-md-6"), labeled("Mô tả vấn đề", description, "col-12"),
        labeled("Đề xuất giải pháp", solution, "col-12"),
      );
      row.append(heading, sectionId, categoryRow, details); container.append(row);
      setDetailsVisible(row, false); refreshCategories(); updateNumbers(); category.focus();
    };

    container.addEventListener("change", (event) => {
      if (event.target.matches("[data-issue-section-category]")) refreshCategories();
    });
    container.addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-issue-section]");
      if (!button) return;
      button.closest("[data-issue-section-row]")?.remove(); refreshCategories(); updateNumbers();
    });
    addButton?.addEventListener("click", createRow);
    refreshCategories(); updateNumbers();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
