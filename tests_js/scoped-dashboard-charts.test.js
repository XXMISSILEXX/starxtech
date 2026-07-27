const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/scoped-dashboard-charts.js", "utf8");

function activity(projectIds, labels, values) {
  const total = values.reduce((sum, value) => sum + value, 0);
  return {
    project_ids: projectIds,
    labels,
    values,
    total_count: total,
    percentages: values.map((value) => total ? Number(((value / total) * 100).toFixed(1)) : 0),
  };
}

function payload(issues, reports) {
  return {
    section_status: { keys: ["INFO", "GOOD", "PROCESSING", "ATTENTION", "CRITICAL"], labels: [], values: [0, 0, 0, 0, 0] },
    trend: { days: [], series: {} },
    submissions: { labels: [], values: [] },
    overall_status: { labels: [], keys: [], values: [] },
    persistent_issues: { status: { labels: [], values: [] }, severity: { labels: [], values: [] }, by_project: { labels: [], values: [] } },
    contractors: { labels: [], values: [] },
    system_analytics: {
      customer_project_share: { labels: [], values: [], percentages: [] },
      project_status_distribution: { labels: [], values: [] },
      contractor_project_coverage: { labels: [], values: [] },
      project_activity: { default_days: 30, current_issues: issues, daily_reports: { periods: { "7": reports, "30": reports, "90": reports } } },
    },
  };
}

async function page(data) {
  const dom = new JSDOM(`<!doctype html><div id="scoped-dashboard-charts" data-dashboard-api="/api"><div class="card-body"><div data-activity-chart><canvas class="system-analytics-canvas" id="system-current-issues"></canvas></div><p data-chart-summary></p><p data-chart-empty hidden></p></div><div class="card-body"><div data-activity-chart><canvas class="system-analytics-canvas" id="system-daily-report-activity"></canvas></div><p data-chart-summary></p><p data-chart-empty hidden></p></div></div>`, { runScripts: "outside-only", url: "https://starx.test" });
  const charts = [];
  dom.window.matchMedia = () => ({ matches: true });
  dom.window.Chart = function Chart(_target, config) { charts.push(config); };
  dom.window.fetch = async () => ({ ok: true, json: async () => data });
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  return { dom, charts };
}

test("project activity uses matching doughnut colours, Vietnamese tooltips, and summaries", async () => {
  const issues = activity([2, 1], ["P002 · Beta", "P001 · Alpha"], [1, 2]);
  const reports = activity([1, 3], ["P001 · Alpha", "P003 · Gamma"], [4, 1]);
  const { dom, charts } = await page(payload(issues, reports));
  const issueChart = charts.find((item) => item.data.datasets[0].label === "Số vấn đề tồn đọng");
  const reportChart = charts.find((item) => item.data.datasets[0].label === "Số báo cáo ngày");

  assert.equal(issueChart.type, "doughnut");
  assert.equal(reportChart.type, "doughnut");
  assert.equal(issueChart.data.datasets[0].backgroundColor[1], reportChart.data.datasets[0].backgroundColor[0]);
  assert.match(issueChart.options.plugins.tooltip.callbacks.label({ dataIndex: 0 }), /P002 · Beta: 1 vấn đề · 33\.3%/);
  assert.match(reportChart.options.plugins.tooltip.callbacks.label({ dataIndex: 0 }), /P001 · Alpha: 4 báo cáo · 80%/);
  assert.match(dom.window.document.querySelector("#system-current-issues").closest(".card-body").querySelector("[data-chart-summary]").textContent, /P001 · Alpha: 2 vấn đề \(66\.7%\)/);
  assert.doesNotMatch(dom.window.document.body.textContent, /undefined/);
});

test("empty project activity hides canvases and does not create doughnut charts", async () => {
  const empty = activity([], [], []);
  const { dom, charts } = await page(payload(empty, empty));
  assert.equal(charts.some((item) => item.data.datasets[0].label === "Số vấn đề tồn đọng"), false);
  assert.equal(dom.window.document.querySelector("#system-current-issues").closest("[data-activity-chart]").hidden, true);
  assert.equal(dom.window.document.querySelector("#system-current-issues").closest(".card-body").querySelector("[data-chart-empty]").textContent, "Chưa có vấn đề tồn đọng trong phạm vi được phân quyền.");
  assert.equal(dom.window.document.querySelector("#system-daily-report-activity").closest(".card-body").querySelector("[data-chart-empty]").textContent, "Chưa có báo cáo ngày trong khoảng thời gian được chọn.");
});
