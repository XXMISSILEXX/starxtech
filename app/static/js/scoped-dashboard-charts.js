(() => {
  const SECTION_COLORS = ['#6c757d', '#198754', '#0dcaf0', '#ffc107', '#dc3545'];
  const ISSUE_COLORS = ['#0dcaf0', '#ffc107', '#198754', '#6c757d'];
  const OVERALL_COLORS = { UPDATED: '#6c757d', GOOD: '#198754', PROCESSING: '#0dcaf0', ATTENTION: '#ffc107', CRITICAL: '#dc3545' };

  const canvas = (id) => document.getElementById(id);
  const chart = (id, config) => {
    const target = canvas(id);
    if (target && typeof Chart === 'function') new Chart(target, config);
  };
  const bars = (labels, values, colors) => ({
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: colors }] },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });

  const init = async () => {
    const root = document.getElementById('scoped-dashboard-charts');
    if (!root || !root.dataset.dashboardApi || root.dataset.chartsInitialized === 'true') return;
    root.dataset.chartsInitialized = 'true';
    try {
      const response = await fetch(root.dataset.dashboardApi, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('dashboard request failed');
      const data = await response.json();
      const section = data.section_status;
      if (!section || section.keys.length !== 5 || section.values.length !== 5 || !data.trend) throw new Error('dashboard contract invalid');

      chart('scoped-section-pie', {
        type: 'doughnut',
        data: { labels: section.labels, datasets: [{ data: section.values, backgroundColor: SECTION_COLORS }] },
      });
      chart('scoped-section-trend', {
        type: 'bar',
        data: {
          labels: data.trend.days,
          datasets: section.keys.map((key, index) => ({ label: section.labels[index], data: data.trend.series[key], backgroundColor: SECTION_COLORS[index], stack: 'sections' })),
        },
        options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } },
      });
      chart('scoped-submissions', bars(data.submissions.labels, data.submissions.values, '#198754'));
      chart('scoped-overall-status', bars(data.overall_status.labels, data.overall_status.keys.map((key) => OVERALL_COLORS[key] ? 1 : 0), data.overall_status.keys.map((key) => OVERALL_COLORS[key] || '#dee2e6')));
      chart('scoped-issues-status', bars(data.persistent_issues.status.labels, data.persistent_issues.status.values, ISSUE_COLORS));
      chart('scoped-issues-severity', bars(data.persistent_issues.severity.labels, data.persistent_issues.severity.values, ['#6c757d', '#0dcaf0', '#ffc107', '#dc3545']));
      chart('scoped-issues-project', bars(data.persistent_issues.by_project.labels, data.persistent_issues.by_project.values, '#dc3545'));
      chart('scoped-contractors-role', bars(data.contractors.labels, data.contractors.values, ['#0d6efd', '#6f42c1']));
    } catch (_error) {
      root.insertAdjacentHTML('afterbegin', '<div class="alert alert-warning">Không thể tải biểu đồ dashboard. Vui lòng thử lại.</div>');
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
