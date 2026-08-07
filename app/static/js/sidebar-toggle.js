(() => {
  const root = document.documentElement;
  const storageKey = root.dataset.sidebarStorageKey;
  const collapsedValue = "collapsed";

  const isStoredCollapsed = () => {
    if (!storageKey) return false;
    try {
      return window.localStorage.getItem(storageKey) === collapsedValue;
    } catch (_error) {
      return false;
    }
  };

  if (isStoredCollapsed()) root.classList.add("sidebar-collapsed");

  const initializeToggle = () => {
    const toggle = document.querySelector("[data-sidebar-toggle]");
    if (!toggle) return;

    const icon = toggle.querySelector("i");
    const apply = (collapsed, persist = false) => {
      root.classList.toggle("sidebar-collapsed", collapsed);
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng");
      icon?.classList.toggle("bi-chevron-left", !collapsed);
      icon?.classList.toggle("bi-chevron-right", collapsed);

      if (!persist || !storageKey) return;
      try {
        window.localStorage.setItem(storageKey, collapsed ? collapsedValue : "expanded");
      } catch (_error) {
        // Local storage can be unavailable in private browsing contexts.
      }
    };

    apply(root.classList.contains("sidebar-collapsed"));
    toggle.addEventListener("click", () => apply(!root.classList.contains("sidebar-collapsed"), true));
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeToggle, { once: true });
  else initializeToggle();
})();
