const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/construction-progress-overlays.js", "utf8");

function page() {
  const dom = new JSDOM(`<!doctype html><form data-progress-group-form><div data-item-rows><div data-progress-item-row><input name="items-0-name"><input data-delete-item type="checkbox"><div data-delete-preview class="d-none" data-entry-count="2">sẽ xoá 2 phiếu</div></div></div><div data-delete-confirm class="d-none"></div><button data-batch-save class="btn-primary"></button><button type="button" data-add-item-row></button></form><template data-item-row-template><div data-progress-item-row><input name="items-__INDEX__-name"><button data-remove-item-row></button></div></template>`, {runScripts: "outside-only"});
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
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

test("daily-entry overlay filters items by group and preserves indexed rows", () => {
  const dom = new JSDOM(`<!doctype html><form data-progress-entry-form><div data-entry-rows><div data-progress-entry-row><select data-entry-group name="entries-0-group_id"><option value=""></option><option value="1" selected>Khu 1</option><option value="2">Khu 2</option></select><select data-entry-item name="entries-0-item_id"><option value=""></option><option value="11" data-group-id="1" selected>A</option><option value="22" data-group-id="2">B</option></select><button data-remove-entry-row></button></div></div><button type="button" data-add-entry-row></button></form><template data-entry-row-template><div data-progress-entry-row><select data-entry-group name="entries-__INDEX__-group_id"><option value=""></option><option value="1">Khu 1</option></select><select data-entry-item name="entries-__INDEX__-item_id"><option value=""></option><option value="11" data-group-id="1">A</option></select><button data-remove-entry-row></button></div></template>`, {runScripts: "outside-only"});
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  const group = dom.window.document.querySelector("[data-entry-group]");
  const item = dom.window.document.querySelector("[data-entry-item]");
  assert.equal(item.querySelector('[value="22"]').disabled, true);
  group.value = "2";
  group.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  assert.equal(item.value, "");
  dom.window.document.querySelector("[data-add-entry-row]").click();
  assert.equal(dom.window.document.querySelectorAll('[name="entries-1-item_id"]').length, 1);
});

test("server-requested overlay reopens after a validation error", () => {
  const dom = new JSDOM(`<!doctype html><div id="createEntries"></div><div data-open-progress-modal="createEntries"></div>`, {runScripts: "outside-only"});
  let opened = null;
  dom.window.bootstrap = {Modal: class { constructor(element) { opened = element.id; } show() {} }};
  dom.window.eval(source);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  assert.equal(opened, "createEntries");
});

test("overlay reopening waits for DOMContentLoaded when the page is still loading", () => {
  const dom = new JSDOM(`<!doctype html><div id="createGroup"></div><div data-open-progress-modal="createGroup"></div>`, {runScripts: "outside-only"});
  Object.defineProperty(dom.window.document, "readyState", {configurable: true, value: "loading"});
  let opened = null;
  dom.window.bootstrap = {Modal: class { constructor(element) { opened = element.id; } show() {} }};
  dom.window.eval(source);
  assert.equal(opened, null);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  assert.equal(opened, "createGroup");
});
