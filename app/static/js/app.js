document.addEventListener("DOMContentLoaded", () => {
  initReportSections();
  initDashboardCharts();
  initConfirmActions();
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
        const selected = value === String(selectedValue) ? " selected" : "";
        return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(label)}</option>`;
      })
      .join("");

  const addSection = () => {
    const index = nextIndex();
    const section = document.createElement("div");
    section.className = "report-section p-3 mb-3";
    section.dataset.sectionRow = "";
    section.innerHTML = `
      <div class="row g-3">
        <div class="col-md-5">
          <label class="form-label">Hạng mục</label>
          <select class="form-select" name="sections-${index}-category_id">
            <option value="">Chọn hạng mục</option>
            ${optionHtml(categories)}
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label">Trạng thái</label>
          <select class="form-select" name="sections-${index}-status">
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
        <div class="col-12">
          <label class="form-label">Ảnh đính kèm</label>
          <input class="form-control" name="sections-${index}-images" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" multiple>
        </div>
      </div>
    `;
    container.appendChild(section);
  };

  container.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-section]");
    if (!removeButton) {
      return;
    }
    const row = removeButton.closest("[data-section-row]");
    if (row) {
      row.remove();
    }
  });

  if (addButton) {
    addButton.addEventListener("click", addSection);
  }

  if (!container.querySelector("[data-section-row]")) {
    addSection();
  }
}

function initConfirmActions() {
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-confirm]");
    if (!trigger) {
      return;
    }

    if (!window.confirm(trigger.dataset.confirm || "Bạn chắc chắn muốn tiếp tục?")) {
      event.preventDefault();
    }
  });
}

function initDashboardCharts() {
  const charts = document.querySelectorAll("[data-dashboard-chart]");
  if (!charts.length || typeof Chart === "undefined") {
    return;
  }

  charts.forEach((canvas) => {
    fetch(canvas.dataset.url)
      .then((response) => response.json())
      .then((data) => {
        const chartType = canvas.dataset.dashboardChart === "pie" ? "pie" : "bar";
        new Chart(canvas, {
          type: chartType,
          data: {
            labels: data.labels,
            datasets: [
              {
                data: data.counts,
                backgroundColor: [
                  "#64748b",
                  "#22c55e",
                  "#38bdf8",
                  "#f59e0b",
                  "#ef4444",
                ],
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                display: chartType === "pie",
                position: "bottom",
                labels: {
                  boxWidth: 12,
                  boxHeight: 12,
                  color: "#475569",
                  font: {
                    family: "Inter, system-ui, sans-serif",
                    weight: "600",
                  },
                },
              },
              tooltip: {
                backgroundColor: "#0f172a",
                padding: 12,
                titleFont: {
                  family: "Inter, system-ui, sans-serif",
                },
                bodyFont: {
                  family: "Inter, system-ui, sans-serif",
                },
              },
            },
            scales:
              chartType === "bar"
                ? {
                    y: {
                      beginAtZero: true,
                      grid: {
                        color: "#e2e8f0",
                      },
                      ticks: {
                        color: "#64748b",
                        precision: 0,
                      },
                    },
                    x: {
                      grid: {
                        display: false,
                      },
                      ticks: {
                        color: "#64748b",
                      },
                    },
                  }
                : {},
          },
        });
      });
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
