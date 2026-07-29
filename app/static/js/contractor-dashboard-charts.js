(() => {
  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const color = (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const chart = (id, labels, values, colors) => {
    const target = document.getElementById(id);
    if (!target || typeof Chart !== 'function') return;
    new Chart(target, { type: 'bar', data: { labels, datasets: [{ data: values, backgroundColor: colors }] }, options: { responsive: true, animation: reducedMotion ? false : undefined, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }, plugins: { legend: { display: false } } } });
    const summary = target.parentElement.querySelector('[data-chart-summary]');
    if (summary) summary.textContent = labels.map((label, index) => `${label}: ${values[index]}`).join('; ') || 'Chưa có dữ liệu.';
  };
  const init = async () => {
    window.StarXTheme?.applyChartDefaults();
    const root = document.getElementById('contractor-dashboard-charts');
    if (!root || root.dataset.chartsInitialized === 'true') return;
    root.dataset.chartsInitialized = 'true';
    try {
      const response = await fetch(root.dataset.dashboardApi, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('dashboard request failed');
      const data = await response.json();
      chart('contractor-projects-by-customer', data.projects_by_customer.labels, data.projects_by_customer.values, color('--sx-primary'));
      chart('contractor-assignment-roles', data.assignment_roles.labels, data.assignment_roles.values, [color('--sx-chart-good'), color('--sx-chart-purple')]);
      chart('contractor-assignment-statuses', data.assignment_statuses.labels, data.assignment_statuses.values, [color('--sx-chart-good'), color('--sx-chart-attention'), color('--sx-chart-info'), color('--sx-chart-neutral')]);
    } catch (_error) {
      root.insertAdjacentHTML('afterbegin', '<div class="alert alert-warning" role="alert">Không thể tải biểu đồ dashboard. Vui lòng thử lại.</div>');
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
