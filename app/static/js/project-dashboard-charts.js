(() => {
  const STATUS_COUNT = 5;
  const COLORS = ['#6c757d', '#198754', '#0dcaf0', '#ffc107', '#dc3545'];

  const init = async () => {
    const root = document.getElementById('project-dashboard-charts');
    if (!root || !root.dataset.sectionStatusApi || root.dataset.chartsInitialized === 'true') return;
    root.dataset.chartsInitialized = 'true';

    const pieCanvas = document.getElementById('project-section-pie');
    const trendCanvas = document.getElementById('project-section-trend');
    const empty = root.querySelector('[data-chart-empty]');
    const trendEmpty = root.querySelector('[data-chart-trend-empty]');
    const error = root.querySelector('[data-chart-error]');
    const hide = (element) => element?.classList.add('d-none');
    const show = (element) => element?.classList.remove('d-none');
    const chartOptions = {
      animation: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? false : undefined,
    };

    try {
      if (!pieCanvas || !trendCanvas || typeof Chart !== 'function') throw new Error('chart unavailable');
      const response = await fetch(root.dataset.sectionStatusApi, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('chart request failed');
      const data = await response.json();
      const status = data.section_status;
      const trend = data.trend;
      const validStatus = status
        && Array.isArray(status.keys)
        && Array.isArray(status.labels)
        && Array.isArray(status.values)
        && status.keys.length === STATUS_COUNT
        && status.labels.length === STATUS_COUNT
        && status.values.length === STATUS_COUNT
        && status.values.every((value) => Number.isInteger(value) && value >= 0)
        && Number.isInteger(status.total)
        && status.total === status.values.reduce((total, value) => total + value, 0);
      const validTrend = trend
        && Array.isArray(trend.days)
        && trend.days.length === 7
        && status?.keys?.every((key) => Array.isArray(trend.series?.[key]) && trend.series[key].length === trend.days.length);
      if (!validStatus || !validTrend) throw new Error('chart contract invalid');

      if (status.total === 0) {
        pieCanvas.classList.add('d-none');
        show(empty);
      } else {
        new Chart(pieCanvas, {
          type: 'doughnut',
          data: {
            labels: status.labels,
            datasets: [{ data: status.values, backgroundColor: COLORS }],
          },
          options: chartOptions,
        });
      }

      const trendTotal = status.keys.reduce(
        (total, key) => total + trend.series[key].reduce((seriesTotal, value) => seriesTotal + value, 0),
        0,
      );
      if (trendTotal === 0) {
        trendCanvas.classList.add('d-none');
        show(trendEmpty);
      } else {
        new Chart(trendCanvas, {
          type: 'bar',
          data: {
            labels: trend.days,
            datasets: status.keys.map((key, index) => ({
              label: status.labels[index],
              data: trend.series[key],
              backgroundColor: COLORS[index],
              stack: 'section-status',
            })),
          },
          options: {
            ...chartOptions,
            scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
          },
        });
      }
    } catch (_error) {
      pieCanvas?.classList.add('d-none');
      trendCanvas?.classList.add('d-none');
      hide(empty);
      hide(trendEmpty);
      show(error);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
