const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/construction-progress-overlays.js", "utf8");

function page() {
  const dom = new JSDOM(`<!doctype html><form data-progress-group-form><div data-item-rows><div data-progress-item-row><input data-delete-item type="checkbox"><div data-delete-preview class="d-none" data-entry-count="2">sẽ xoá 2 phiếu</div></div></div><div data-delete-confirm class="d-none"></div><button data-batch-save class="btn-primary"></button><button type="button" data-add-item-row></button></form><template data-item-row-template><div data-progress-item-row><input name="items-__INDEX__-name"><button data-remove-item-row></button></div></template>`, {runScripts: "outside-only"});
  dom.window.eval(source);
  return dom;
}

test("edit overlay exposes real deletion warning and one confirmation checkbox", () => {
  const dom = page();
  const checkbox = dom.window.document.querySelector("[data-delete-item]");
  checkbox.checked = true;
  checkbox.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  assert.equal(dom.window.document.querySelector("[data-delete-preview]").classList.contains("d-none"), false);
  assert.equal(dom.window.document.querySelector("[data-delete-confirm]").classList.contains("d-none"), false);
  assert.equal(dom.window.document.querySelector("[data-batch-save]").classList.contains("btn-warning"), true);
  assert.match(dom.window.document.querySelector("[data-delete-preview]").textContent, /sẽ xoá 2 phiếu/);
});

test("new overlay row receives an indexed field name", () => {
  const dom = page();
  dom.window.document.querySelector("[data-add-item-row]").click();
  assert.equal(dom.window.document.querySelectorAll("[data-progress-item-row]").length, 2);
  assert.equal(dom.window.document.querySelectorAll('[name="items-1-name"]').length, 1);
  assert.doesNotMatch(source, /form\.submit\(/);
});
