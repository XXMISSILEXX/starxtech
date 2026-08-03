(() => {
  const color = (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim();

  const start = async () => {
    const root = document.querySelector('[data-progress-dashboard-chart]');
    if (!root || !root.dataset.chartUrl || root.dataset.chartsInitialized === 'true') return;
    root.dataset.chartsInitialized = 'true';
    const canvas = root.querySelector('[data-progress-dashboard-chart-canvas]');
    const summary = root.querySelector('[data-progress-dashboard-chart-summary]');
    if (!canvas || typeof Chart !== 'function') return;
    try {
      const response = await fetch(root.dataset.chartUrl, {headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('progress chart request failed');
      const data = await response.json();
      const labels = Array.isArray(data.labels) ? data.labels : [];
      if (!labels.length) {
        if (summary) summary.textContent = 'Giai đoạn này chưa có khu vực nào.';
        return;
      }
      const moneyMode = Array.isArray(data.completed) && Array.isArray(data.remaining);
      const primary = color('--sx-primary');
      const completedColor = color('--sx-chart-good');
      const remainingColor = color('--sx-chart-neutral');
      const datasets = moneyMode
        ? [
          {label: 'Đã hoàn thành', data: data.completed, backgroundColor: completedColor, borderColor: completedColor, borderWidth: 1, stack: 'value'},
          {label: 'Còn lại', data: data.remaining, backgroundColor: remainingColor, borderColor: remainingColor, borderWidth: 2, stack: 'value'},
        ]
        : [{label: 'Hoàn thành (%)', data: data.percentages || [], backgroundColor: primary}];
      const options = moneyMode
        ? {
          responsive: true,
          maintainAspectRatio: false,
          scales: {x: {stacked: true}, y: {stacked: true, beginAtZero: true}},
        }
        : {
          responsive: true,
          maintainAspectRatio: false,
          scales: {y: {beginAtZero: true, max: 100, ticks: {callback: (value) => `${value}%`}}},
        };
      new Chart(canvas, {type: 'bar', data: {labels, datasets}, options});
      if (summary) summary.textContent = `Hoàn thành toàn giai đoạn: ${Number(data.overall_percent || 0).toLocaleString('vi-VN')}%.`;
    } catch (_error) {
      if (summary) summary.textContent = 'Không thể tải biểu đồ khu vực. Vui lòng thử lại.';
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
