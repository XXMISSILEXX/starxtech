(() => {
  const start = () => {
    const form = document.querySelector('[data-progress-dashboard-filter-form]');
    if (!form || form.dataset.filterInitialized === 'true') return;
    form.dataset.filterInitialized = 'true';
    form.querySelectorAll('[data-progress-dashboard-filter-select]').forEach((select) => {
      select.addEventListener('change', () => form.requestSubmit());
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
