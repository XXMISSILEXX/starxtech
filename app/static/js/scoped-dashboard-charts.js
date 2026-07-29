(() => {
  const color = (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const sectionColors = () => ['--sx-chart-neutral', '--sx-chart-good', '--sx-chart-info', '--sx-chart-attention', '--sx-chart-critical'].map(color);
  const issueColors = () => ['--sx-chart-info', '--sx-chart-attention', '--sx-chart-good', '--sx-chart-neutral'].map(color);
  const overallColors = () => ({ UPDATED: color('--sx-chart-neutral'), GOOD: color('--sx-chart-good'), PROCESSING: color('--sx-chart-info'), ATTENTION: color('--sx-chart-attention'), CRITICAL: color('--sx-chart-critical') });
  const palette = () => ['--sx-primary', '--sx-chart-purple', '--sx-chart-good', '--sx-chart-orange', '--sx-chart-info', '--sx-chart-critical', '--sx-chart-teal', '--sx-chart-attention', '--sx-chart-processing', '--sx-chart-neutral'].map(color);
  // Named contract retained for the dashboard coverage chart; values come from CSS tokens.
  const CONTRACTOR_COVERAGE_COLORS = () => palette();

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
    const colors = palette();
    return new Map(ids.map((projectId, index) => [String(projectId), colors[index] || generatedProjectColor(projectId)]));
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
    window.StarXTheme?.applyChartDefaults();
    const root = document.getElementById('scoped-dashboard-charts');
    if (!root || !root.dataset.dashboardApi || root.dataset.chartsInitialized === 'true') return;
    root.dataset.chartsInitialized = 'true';
    try {
      const response = await fetch(root.dataset.dashboardApi, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('dashboard request failed');
      const data = await response.json();
      const section = data.section_status;
      if (!section || section.keys.length !== 5 || section.values.length !== 5 || !data.trend) throw new Error('dashboard contract invalid');

      const statusColors = sectionColors();
      const overall = overallColors();
      const paletteColors = palette();
      chart('scoped-section-pie', {
        type: 'doughnut',
        data: { labels: section.labels, datasets: [{ data: section.values, backgroundColor: statusColors }] },
      });
      chart('scoped-section-trend', {
        type: 'bar',
        data: {
          labels: data.trend.days,
          datasets: section.keys.map((key, index) => ({ label: section.labels[index], data: data.trend.series[key], backgroundColor: statusColors[index], stack: 'sections' })),
        },
        options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } },
      });
      chart('scoped-submissions', bars(data.submissions.labels, data.submissions.values, color('--sx-chart-good')));
      chart('scoped-overall-status', bars(data.overall_status.labels, data.overall_status.keys.map((key) => overall[key] ? 1 : 0), data.overall_status.keys.map((key) => overall[key] || color('--sx-surface-emphasis'))));
      chart('scoped-issues-status', bars(data.persistent_issues.status.labels, data.persistent_issues.status.values, issueColors()));
      chart('scoped-issues-severity', bars(data.persistent_issues.severity.labels, data.persistent_issues.severity.values, [color('--sx-chart-neutral'), color('--sx-chart-info'), color('--sx-chart-attention'), color('--sx-chart-critical')]));
      chart('scoped-issues-project', bars(data.persistent_issues.by_project.labels, data.persistent_issues.by_project.values, color('--sx-chart-critical')));
      chart('scoped-contractors-role', bars(data.contractors.labels, data.contractors.values, [color('--sx-primary'), color('--sx-chart-purple')]));

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
          data: { labels: customers.labels, datasets: [{ data: customers.values, backgroundColor: paletteColors.slice(0, 6) }] },
        });
        chart('system-project-status-distribution', {
          type: 'doughnut',
          data: { labels: statuses.labels, datasets: [{ data: statuses.values, backgroundColor: [color('--sx-chart-good'), color('--sx-chart-attention'), color('--sx-chart-info'), color('--sx-chart-neutral')] }] },
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
      datasets: [{ data: values, backgroundColor: labels.map((_label, index) => { const colors = CONTRACTOR_COVERAGE_COLORS(); return colors[index % colors.length]; }) }],
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
