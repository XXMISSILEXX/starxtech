const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/sidebar-toggle.js", "utf8");

function page({ storedValue = null, userId = 3 } = {}) {
  const dom = new JSDOM(`<!doctype html><html data-sidebar-storage-key="starx.sidebar.${userId}"><body><button data-sidebar-toggle aria-expanded="true" aria-label="Thu gọn thanh điều hướng"><i class="bi bi-chevron-left"></i></button></body></html>`, {
    runScripts: "outside-only",
    url: "https://starx.test/reports/dashboard/system",
  });
  const storageKey = `starx.sidebar.${userId}`;
  if (storedValue) dom.window.localStorage.setItem(storageKey, storedValue);
  dom.window.eval(source);
  return { dom, storageKey };
}

function ready(dom) {
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
}

test("clicking the toggle changes its state and persists collapse", () => {
  const { dom, storageKey } = page();
  ready(dom);

  dom.window.document.querySelector("[data-sidebar-toggle]").click();

  assert.equal(dom.window.document.documentElement.classList.contains("sidebar-collapsed"), true);
  assert.equal(dom.window.localStorage.getItem(storageKey), "collapsed");
});

test("clicking again returns the sidebar to its initial expanded state", () => {
  const { dom, storageKey } = page();
  ready(dom);
  const toggle = dom.window.document.querySelector("[data-sidebar-toggle]");

  toggle.click();
  toggle.click();

  assert.equal(dom.window.document.documentElement.classList.contains("sidebar-collapsed"), false);
  assert.equal(dom.window.localStorage.getItem(storageKey), "expanded");
});

test("a stored collapsed value is applied before the toggle is initialized", () => {
  const { dom } = page({ storedValue: "collapsed" });

  assert.equal(dom.window.document.documentElement.classList.contains("sidebar-collapsed"), true);
});

test("sidebar state uses the authenticated user's id in its localStorage key", () => {
  const { dom, storageKey } = page({ userId: 42 });
  ready(dom);

  dom.window.document.querySelector("[data-sidebar-toggle]").click();

  assert.equal(storageKey, "starx.sidebar.42");
  assert.equal(dom.window.localStorage.getItem("starx.sidebar.42"), "collapsed");
});

test("the aria state and chevron direction follow the sidebar state", () => {
  const { dom } = page();
  ready(dom);
  const toggle = dom.window.document.querySelector("[data-sidebar-toggle]");
  const icon = toggle.querySelector("i");

  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(icon.classList.contains("bi-chevron-left"), true);
  toggle.click();
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.equal(toggle.getAttribute("aria-label"), "Mở rộng thanh điều hướng");
  assert.equal(icon.classList.contains("bi-chevron-right"), true);
});
