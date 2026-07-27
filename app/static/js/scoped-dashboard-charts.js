(() => {
  const SECTION_COLORS = ['#6c757d', '#198754', '#0dcaf0', '#ffc107', '#dc3545'];
  const ISSUE_COLORS = ['#0dcaf0', '#ffc107', '#198754', '#6c757d'];
  const OVERALL_COLORS = { UPDATED: '#6c757d', GOOD: '#198754', PROCESSING: '#0dcaf0', ATTENTION: '#ffc107', CRITICAL: '#dc3545' };
  const CONTRACTOR_COVERAGE_COLORS = ['#0d6efd', '#6f42c1', '#198754', '#fd7e14', '#0dcaf0', '#dc3545', '#20c997', '#ffc107', '#6610f2', '#6c757d'];
  const PROJECT_ACTIVITY_COLORS = ['#0d6efd', '#6f42c1', '#198754', '#fd7e14', '#0dcaf0', '#dc3545', '#20c997', '#ffc107', '#6610f2', '#6c757d'];

  const canvas = (id) => document.getElementById(id);
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const summary = (id, labels, values, suffix = '') => {
    const target = canvas(id)?.closest('.card-body')?.querySelector('[data-chart-summary]');
    if (!target) return;
    target.textContent = labels.length ? labels.map((label, index) => `${label}: ${values[index] ?? 0}${suffix}`).join('; ') : 'Chưa có dữ liệu trong phạm vi hiển thị.';
  };
  const chart = (id, config) => {
    const target = canvas(id);
    if (!target || typeof Chart !== 'function') return;
    config.options = { ...(config.options || {}) };
    if (reducedMotion) config.options.animation = false;
    if (target.classList.contains('system-analytics-canvas')) config.options.maintainAspectRatio = false;
    new Chart(target, config);
  };
  const bars = (labels, values, colors) => ({
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: colors }] },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });
  const formatPercentage = (value) => `${Number(value || 0).toFixed(1).replace(/\.0$/, '')}%`;
  const activityElements = (id) => {
    const target = canvas(id);
    const body = target?.closest('.card-body');
    return {
      target,
      wrap: target?.closest('[data-activity-chart]'),
      summary: body?.querySelector('[data-chart-summary]'),
      empty: body?.querySelector('[data-chart-empty]'),
    };
  };
  const generatedProjectColor = (projectId) => {
    const text = String(projectId);
    let hash = 0;
    for (let index = 0; index < text.length; index += 1) hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
    return `hsl(${Math.abs(hash) % 360} 62% 46%)`;
  };
  const projectColorMap = (issues, reports) => {
    const ids = [...new Set([...(issues.project_ids || []), ...(reports.project_ids || [])])]
      .sort((left, right) => String(left).localeCompare(String(right), 'en', { numeric: true }));
    return new Map(ids.map((projectId, index) => [String(projectId), PROJECT_ACTIVITY_COLORS[index] || generatedProjectColor(projectId)]));
  };
  const activityDoughnut = (id, activity, colors, datasetLabel, singular, emptyText) => {
    const elements = activityElements(id);
    const labels = Array.isArray(activity.labels) ? activity.labels : [];
    const values = Array.isArray(activity.values) ? activity.values : [];
    const percentages = Array.isArray(activity.percentages) ? activity.percentages : [];
    const ids = Array.isArray(activity.project_ids) ? activity.project_ids : [];
    const totalCount = Number(activity.total_count || 0);
    if (!elements.target) return;
    if (!totalCount) {
      if (elements.wrap) elements.wrap.hidden = true;
      if (elements.summary) elements.summary.hidden = true;
      if (elements.empty) {
        elements.empty.hidden = false;
        elements.empty.textContent = emptyText;
      }
      return;
    }
    if (elements.wrap) elements.wrap.hidden = false;
    if (elements.summary) {
      elements.summary.hidden = false;
      elements.summary.textContent = labels.map((label, index) => `${String(label || '')}: ${Number(values[index] || 0)} ${singular} (${formatPercentage(percentages[index])})`).join('; ');
    }
    if (elements.empty) elements.empty.hidden = true;
    chart(id, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ label: datasetLabel, data: values, backgroundColor: ids.map((projectId) => colors.get(String(projectId)) || generatedProjectColor(projectId)) }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: true, position: 'bottom', labels: { boxWidth: 12, padding: 12 } },
          tooltip: {
            callbacks: {
              label: (context) => {
                const index = context.dataIndex;
                return `${String(labels[index] || '')}: ${Number(values[index] || 0)} ${singular} · ${formatPercentage(percentages[index])}`;
              },
            },
          },
        },
      },
    });
  };

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

      if (data.system_analytics) {
        const analytics = data.system_analytics;
        const customers = analytics.customer_project_share;
        const statuses = analytics.project_status_distribution;
        const coverage = analytics.contractor_project_coverage;
        const issues = analytics.project_activity.current_issues;
        const reports = analytics.project_activity.daily_reports.periods[String(analytics.project_activity.default_days)];
        const activityColors = projectColorMap(issues, reports);
        chart('system-customer-project-share', {
          type: 'doughnut',
          data: { labels: customers.labels, datasets: [{ data: customers.values, backgroundColor: ['#0d6efd', '#6f42c1', '#198754', '#fd7e14', '#6c757d', '#20c997'] }] },
        });
        chart('system-project-status-distribution', {
          type: 'doughnut',
          data: { labels: statuses.labels, datasets: [{ data: statuses.values, backgroundColor: ['#198754', '#ffc107', '#0dcaf0', '#6c757d'] }] },
        });
        chart('system-contractor-project-coverage', contractorCoverageBars(coverage.labels, coverage.values));
        activityDoughnut('system-current-issues', issues, activityColors, 'Số vấn đề tồn đọng', 'vấn đề', 'Chưa có vấn đề tồn đọng trong phạm vi được phân quyền.');
        activityDoughnut('system-daily-report-activity', reports, activityColors, 'Số báo cáo ngày', 'báo cáo', 'Chưa có báo cáo ngày trong khoảng thời gian được chọn.');
        summary('system-customer-project-share', customers.labels, customers.percentages, '%');
        summary('system-project-status-distribution', statuses.labels, statuses.values);
        summary('system-contractor-project-coverage', coverage.labels, coverage.values, ' dự án đang hoạt động');
      }
    } catch (_error) {
      root.insertAdjacentHTML('afterbegin', '<div class="alert alert-warning">Không thể tải biểu đồ dashboard. Vui lòng thử lại.</div>');
    }
  };

  const horizontalBars = (labels, values, color, suffix = '') => ({
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: color }] },
    options: {
      indexAxis: 'y', responsive: true,
      plugins: { tooltip: { callbacks: { label: (context) => `${context.raw}${suffix}` } } },
      scales: { x: { beginAtZero: true } },
    },
  });

  const contractorCoverageBars = (labels, values) => ({
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: labels.map((_label, index) => CONTRACTOR_COVERAGE_COLORS[index % CONTRACTOR_COVERAGE_COLORS.length]) }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (context) => `${context.label}: ${context.raw} dự án đang hoạt động` } },
      },
      scales: {
        x: { title: { display: true, text: 'Đối tác' } },
        y: { beginAtZero: true, title: { display: true, text: 'Số dự án đang hoạt động' }, ticks: { precision: 0 } },
      },
    },
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
