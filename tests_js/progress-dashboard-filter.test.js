const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/progress-dashboard-filter.js", "utf8");
const template = fs.readFileSync("app/templates/dashboard/progress.html", "utf8");

function page() {
  const dom = new JSDOM(`<!doctype html><form data-progress-dashboard-filter-form><select data-progress-dashboard-filter-select name="type_id"><option value="1">Giai đoạn</option></select><select data-progress-dashboard-filter-select name="item_name"><option value="">Tất cả</option><option value="Điện">Điện</option></select><button type="submit">Lọc</button></form>`, {runScripts: "outside-only"});
  Object.defineProperty(dom.window.document, "readyState", {configurable: true, value: "loading"});
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  return dom;
}

test("submits the filter form when either selection changes", () => {
  const dom = page();
  const form = dom.window.document.querySelector("form");
  let submitted = 0;
  form.addEventListener("submit", (event) => { event.preventDefault(); submitted += 1; });

  for (const select of form.querySelectorAll("select")) {
    select.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  }

  assert.equal(submitted, 2);
});

test("template keeps a CSP-safe data hook and a native submit fallback", () => {
  assert.match(template, /data-progress-dashboard-filter-form/);
  assert.match(template, /data-progress-dashboard-filter-select/);
  assert.match(template, /<button class="btn btn-primary" type="submit">Lọc<\/button>/);
  assert.doesNotMatch(template, /onchange="this\.form\.submit\(\)"/);
});
