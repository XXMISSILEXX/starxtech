const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/persistent-issue-sections.js", "utf8");

function page() {
  const dom = new JSDOM(`<!doctype html><form><div data-issue-sections data-can-write="1" data-categories='[{"id":1,"name":"Tiến độ"},{"id":2,"name":"Chất lượng"}]' data-owners='[{"id":3,"name":"Reporter"}]'></div><button type="button" data-add-issue-section>Thêm hạng mục</button></form>`, {runScripts: "outside-only"});
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

test("the editor waits for DOMContentLoaded when loaded before its marker", () => {
  assert.match(source, /document\.readyState === "loading"/);
  assert.match(source, /DOMContentLoaded/);
});
