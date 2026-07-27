(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.StarXVietnameseDate = api;
}(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  function parse(value) {
    const text = String(value || "").trim();
    if (!/^\d{2}\/\d{2}\/\d{4}$/.test(text)) return null;
    const [day, month, year] = text.split("/").map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return null;
    return { day, month, year, iso: `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}` };
  }

  function format(date) {
    if (!(date instanceof Date) || Number.isNaN(date.valueOf())) return "";
    return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}/${date.getFullYear()}`;
  }

  return { parse, format };
}));
