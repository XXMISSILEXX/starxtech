const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const themeSource = fs.readFileSync("app/static/js/theme-preload.js", "utf8");
const preferencesSource = fs.readFileSync("app/static/js/account-preferences.js", "utf8");
const baseTemplate = fs.readFileSync("app/templates/base.html", "utf8");
const profileTemplate = fs.readFileSync("app/templates/account/profile.html", "utf8");

function page({ dark = false } = {}) {
  const dom = new JSDOM(`<!doctype html><html data-appearance="system" data-resolved-theme="light" data-accent="blue" data-bs-theme="light" data-theme-storage-key="starx.ui-preferences.3"><body>
    <form action="/account/preferences" data-account-preferences><input name="csrf_token" value="token"><input type="radio" name="appearance" value="system" checked><input type="radio" name="appearance" value="dark"><input type="radio" name="appearance" value="light"><input type="radio" name="accent" value="blue" checked><input type="radio" name="accent" value="orange"><button data-preferences-save></button><div data-preferences-toast hidden tabindex="-1"></div></form>
  </body></html>`, { runScripts: "outside-only", url: "https://starx.test/account/" });
  const listeners = [];
  const media = { matches: dark, addEventListener: (_name, callback) => listeners.push(callback) };
  dom.window.matchMedia = () => media;
  dom.window.eval(themeSource);
  return { dom, media, listeners };
}

test("theme preload resolves System and reacts to OS colour-scheme changes", () => {
  const { dom, media, listeners } = page({ dark: true });
  const root = dom.window.document.documentElement;
  assert.equal(root.dataset.appearance, "system");
  assert.equal(root.dataset.resolvedTheme, "dark");
  assert.equal(root.dataset.bsTheme, "dark");
  media.matches = false;
  listeners[0]();
  assert.equal(root.dataset.resolvedTheme, "light");
});

test("settings preview updates attributes immediately and saves only confirmed values in localStorage", async () => {
  const { dom } = page();
  const { window } = dom;
  window.fetch = async () => ({ ok: true, json: async () => ({ message: "Đã lưu", preferences: { appearance: "dark", accent: "orange" } }) });
  window.eval(preferencesSource);
  window.document.dispatchEvent(new window.Event("DOMContentLoaded"));
  const form = window.document.querySelector("form");
  const dark = form.querySelector('[name="appearance"][value="dark"]');
  const orange = form.querySelector('[name="accent"][value="orange"]');
  dark.checked = true; dark.dispatchEvent(new window.Event("change", { bubbles: true }));
  orange.checked = true; orange.dispatchEvent(new window.Event("change", { bubbles: true }));
  assert.equal(window.document.documentElement.dataset.resolvedTheme, "dark");
  assert.equal(window.document.documentElement.dataset.accent, "orange");
  assert.equal(window.localStorage.getItem("starx.ui-preferences.3"), null);
  form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(window.localStorage.getItem("starx.ui-preferences.3"), '{"appearance":"dark","accent":"orange"}');
  assert.match(form.querySelector("[data-preferences-toast]").textContent, /Đã lưu/);
});

test("templates provide data attributes, CSP-safe external scripts, and accessible radio labels", () => {
  assert.match(baseTemplate, /data-appearance=/);
  assert.match(baseTemplate, /data-resolved-theme=/);
  assert.match(baseTemplate, /data-accent=/);
  assert.match(baseTemplate, /js\/theme-preload\.js/);
  assert.doesNotMatch(baseTemplate, /<script>(?!<)/);
  assert.match(profileTemplate, /type="radio" name="appearance"/);
  assert.match(profileTemplate, /type="radio" name="accent"/);
  assert.match(profileTemplate, /for="appearance-\{\{ value \}\}"/);
  assert.match(profileTemplate, /aria-live="polite"/);
  assert.match(profileTemplate, /data-account-preferences/);
});
