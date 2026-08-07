const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/progress-dashboard-chart.js", "utf8");

async function page(data) {
  const dom = new JSDOM(`<!doctype html><div data-progress-dashboard-chart data-chart-url="/projects/1/progress/types/2/chart-data"><canvas data-progress-dashboard-chart-canvas></canvas><p data-progress-dashboard-chart-summary></p></div>`, {runScripts: "outside-only"});
  Object.defineProperty(dom.window.document, "readyState", {configurable: true, value: "loading"});
  const colors = {"--sx-primary": "#2563eb", "--sx-chart-good": "#16a34a", "--sx-chart-neutral": "#64748b"};
  dom.window.getComputedStyle = () => ({getPropertyValue: (token) => colors[token] || ""});
  const charts = [];
  dom.window.Chart = class { constructor(target, config) { charts.push({target, config}); } };
  dom.window.fetch = async (url, options) => ({ok: true, json: async () => data});
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  return {dom, charts};
}

test("loads chart data and renders one vertical bar for every area", async () => {
  const {charts, dom} = await page({labels: ["Khu A", "Khu B"], percentages: [25, 75], overall_percent: 50});

  assert.equal(charts.length, 1);
  assert.deepEqual(Array.from(charts[0].config.data.labels), ["Khu A", "Khu B"]);
  assert.equal(charts[0].config.data.datasets[0].data.length, 2);
  assert.equal(charts[0].config.data.datasets[0].backgroundColor, "#2563eb");
  assert.equal(charts[0].config.data.datasets[0].backgroundColor.startsWith("var("), false);
  assert.equal(charts[0].config.options.maintainAspectRatio, false);
  assert.equal(charts[0].config.options.scales.y.max, 100);
  assert.equal(charts[0].config.plugins[0].id, "progressDashboardPercentageLabels");
  assert.match(dom.window.document.querySelector("[data-progress-dashboard-chart-summary]").textContent, /50%/);
  assert.match(source, /fetch\(root\.dataset\.chartUrl, \{headers: \{Accept: 'application\/json'\}\}\)/);
});

test("does not create a Chart when chart-data has no area labels", async () => {
  const {charts, dom} = await page({labels: [], percentages: [], overall_percent: 0});

  assert.equal(charts.length, 0);
  assert.match(dom.window.document.querySelector("[data-progress-dashboard-chart-summary]").textContent, /chưa có khu vực nào/i);
});

test("uses completed and remaining stacked datasets for money progress", async () => {
  const {charts} = await page({labels: ["Khu A"], percentages: [50], overall_percent: 50, completed: [300], remaining: [700]});

  assert.equal(charts.length, 1);
  assert.deepEqual(Array.from(charts[0].config.data.datasets, (dataset) => dataset.label), ["Đã hoàn thành", "Còn lại"]);
  assert.equal(charts[0].config.data.datasets[0].backgroundColor.startsWith("var("), false);
  assert.equal(charts[0].config.data.datasets[1].backgroundColor.startsWith("var("), false);
  assert.equal(charts[0].config.data.datasets[1].borderWidth, 2);
  assert.equal(charts[0].config.options.scales.y.stacked, true);
});

test("uses a larger percentage axis and a filtered-item summary when a value exceeds 100%", async () => {
  const {charts, dom} = await page({labels: ["C1"], percentages: [105.8], overall_percent: 105.8, item_name: "Điện"});

  assert.equal(charts[0].config.options.scales.y.max, 110);
  assert.match(dom.window.document.querySelector("[data-progress-dashboard-chart-summary]").textContent, /Hạng mục “Điện”: 105,8%/i);
});

test("percentage label plugin draws values but skips null bars", async () => {
  const {charts} = await page({labels: ["C1", "C2"], percentages: [25, null], overall_percent: 25, item_name: "Điện"});
  const config = charts[0].config;
  const drawn = [];
  const context = {
    save() {}, restore() {},
    fillText: (...args) => drawn.push(args),
  };
  config.plugins[0].afterDatasetsDraw({
    data: config.data,
    ctx: context,
    getDatasetMeta: () => ({data: [{x: 20, y: 30}, {x: 40, y: 50}]}),
  }, {}, config.options.plugins.progressDashboardPercentageLabels);

  assert.deepEqual(drawn, [["25%", 20, 24]]);
});
