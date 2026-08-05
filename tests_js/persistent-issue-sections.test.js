const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/persistent-issue-sections.js", "utf8");

function page() {
  const dom = new JSDOM(`<!doctype html><form><div data-issue-sections data-can-write="1" data-categories='[{"id":1,"name":"Tiến độ","icon":"<i class=\\"bi bi-tools\\"></i>"},{"id":2,"name":"Chất lượng","icon":"<span class=\\"category-emoji\\">🔎</span>"}]' data-owners='[{"id":3,"name":"Reporter"}]' data-severity-options='[{"value":"LOW","label":"🟢 Thấp"},{"value":"MEDIUM","label":"🟡 Trung bình"},{"value":"HIGH","label":"🟠 Cao"},{"value":"CRITICAL","label":"🔴 Nghiêm trọng"}]' data-status-options='[{"value":"OPEN","label":"🟡 Đang mở"},{"value":"PROCESSING","label":"🔵 Đang xử lý"},{"value":"RESOLVED","label":"☑️ Đã xử lý"},{"value":"CLOSED","label":"✅ Đã đóng"}]'></div><button type="button" data-add-issue-section>Thêm hạng mục</button></form>`, {runScripts: "outside-only"});
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  return dom;
}

test("add shows only category first, then details after choosing a category", () => {
  const dom = page();
  dom.window.document.querySelector("[data-add-issue-section]").click();
  const row = dom.window.document.querySelector("[data-issue-section-row]");
  const select = row.querySelector("[data-issue-section-category]");
  assert.equal(row.querySelector("[data-issue-section-details]").hidden, true);
  assert.equal(select.name, "sections-0-category_id");
  select.value = "1";
  select.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  assert.equal(row.querySelector("[data-issue-section-details]").hidden, false);
  assert.equal(row.querySelector("[name='sections-0-status']").value, "OPEN");
});

test("used categories disappear from other rows and return after removal", () => {
  const dom = page();
  const add = dom.window.document.querySelector("[data-add-issue-section]");
  add.click();
  const first = dom.window.document.querySelector("[data-issue-section-row]");
  const firstSelect = first.querySelector("[data-issue-section-category]");
  firstSelect.value = "1";
  firstSelect.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  add.click();
  const second = dom.window.document.querySelectorAll("[data-issue-section-row]")[1];
  const secondSelect = second.querySelector("[data-issue-section-category]");
  assert.equal([...secondSelect.options].some((option) => option.value === "1"), false);
  first.querySelector("[data-remove-issue-section]").click();
  assert.equal([...secondSelect.options].some((option) => option.value === "1"), true);
});

test("new section uses the server-provided Vietnamese severity and status labels", () => {
  const dom = page();
  dom.window.document.querySelector("[data-add-issue-section]").click();
  const row = dom.window.document.querySelector("[data-issue-section-row]");
  const texts = (name) => [...row.querySelector(`[name='sections-0-${name}']`).options].map((option) => option.textContent);

  assert.deepEqual(texts("severity"), ["🟢 Thấp", "🟡 Trung bình", "🟠 Cao", "🔴 Nghiêm trọng"]);
  assert.deepEqual(texts("status"), ["🟡 Đang mở", "🔵 Đang xử lý", "☑️ Đã xử lý", "✅ Đã đóng"]);
  assert.equal(texts("severity").includes("CRITICAL"), false);
  assert.equal(texts("status").includes("CLOSED"), false);
});

test("section title gains the selected category icon and stays empty before selection", () => {
  const dom = page();
  dom.window.document.querySelector("[data-add-issue-section]").click();
  const row = dom.window.document.querySelector("[data-issue-section-row]");
  const icon = row.querySelector("[data-issue-section-title-icon]");
  const select = row.querySelector("[data-issue-section-category]");

  assert.equal(icon.hidden, true);
  assert.equal(icon.innerHTML, "");
  select.value = "1";
  select.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  assert.equal(icon.hidden, false);
  assert.match(icon.innerHTML, /bi-tools/);
});

test("the editor waits for DOMContentLoaded when loaded before its marker", () => {
  assert.match(source, /document\.readyState === "loading"/);
  assert.match(source, /DOMContentLoaded/);
});
