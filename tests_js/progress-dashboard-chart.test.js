const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/progress-dashboard-chart.js", "utf8");

async function page(data) {
  const dom = new JSDOM(`<!doctype html><div data-progress-dashboard-chart data-chart-url="/projects/1/progress/types/2/chart-data"><canvas data-progress-dashboard-chart-canvas></canvas><p data-progress-dashboard-chart-summary></p></div>`, {runScripts: "outside-only"});
  Object.defineProperty(dom.window.document, "readyState", {configurable: true, value: "loading"});
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
  assert.equal(charts[0].config.options.maintainAspectRatio, false);
  assert.equal(charts[0].config.options.scales.y.max, 100);
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
  assert.equal(charts[0].config.options.scales.y.stacked, true);
});
