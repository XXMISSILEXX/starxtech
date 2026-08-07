(() => {
  const color = (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const formatPercent = (value) => Number(value).toLocaleString('vi-VN', {maximumFractionDigits: 1});

  const percentageLabels = {
    id: 'progressDashboardPercentageLabels',
    afterDatasetsDraw(chart, _args, options) {
      const percentages = options.percentages || [];
      const datasetIndex = options.datasetIndex || 0;
      const dataset = chart.data.datasets[datasetIndex];
      const elements = chart.getDatasetMeta(datasetIndex).data;
      const context = chart.ctx;
      if (!dataset || !context) return;
      context.save();
      context.fillStyle = color('--sx-text') || '#1f2937';
      context.font = '600 12px sans-serif';
      context.textAlign = 'center';
      context.textBaseline = 'bottom';
      dataset.data.forEach((value, index) => {
        const percentage = percentages[index];
        const element = elements[index];
        if (value === null || value === undefined || percentage === null || percentage === undefined || !element) return;
        const position = element.getProps ? element.getProps(['x', 'y'], true) : element;
        context.fillText(`${formatPercent(percentage)}%`, position.x, position.y - 6);
      });
      context.restore();
    },
  };

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
      const moneyMode = !data.item_name && Array.isArray(data.completed) && Array.isArray(data.remaining);
      const primary = color('--sx-primary');
      const completedColor = color('--sx-chart-good');
      const remainingColor = color('--sx-chart-neutral');
      const percentages = Array.isArray(data.percentages) ? data.percentages : [];
      const datasets = moneyMode
        ? [
          {label: 'Đã hoàn thành', data: data.completed, backgroundColor: completedColor, borderColor: completedColor, borderWidth: 1, stack: 'value'},
          {label: 'Còn lại', data: data.remaining, backgroundColor: remainingColor, borderColor: remainingColor, borderWidth: 2, stack: 'value'},
        ]
        : [{label: 'Hoàn thành (%)', data: percentages, backgroundColor: primary}];
      const largestPercent = Math.max(0, ...percentages.filter((value) => Number.isFinite(Number(value))).map(Number));
      const options = moneyMode
        ? {
          responsive: true,
          maintainAspectRatio: false,
          layout: {padding: {top: 20}},
          plugins: {progressDashboardPercentageLabels: {percentages, datasetIndex: 1}},
          scales: {x: {stacked: true}, y: {stacked: true, beginAtZero: true}},
        }
        : {
          responsive: true,
          maintainAspectRatio: false,
          layout: {padding: {top: 20}},
          plugins: {progressDashboardPercentageLabels: {percentages, datasetIndex: 0}},
          scales: {
            y: {
              beginAtZero: true,
              max: Math.max(100, Math.ceil(largestPercent / 10) * 10),
              ticks: {callback: (value) => `${value}%`},
            },
          },
        };
      new Chart(canvas, {type: 'bar', data: {labels, datasets}, options, plugins: [percentageLabels]});
      if (summary) {
        const total = data.overall_percent === null || data.overall_percent === undefined ? '—' : formatPercent(data.overall_percent);
        summary.textContent = data.item_name
          ? `Hoàn thành hạng mục “${data.item_name}”: ${total}%.`
          : `Hoàn thành toàn giai đoạn: ${total}%.`;
      }
    } catch (_error) {
      if (summary) summary.textContent = 'Không thể tải biểu đồ khu vực. Vui lòng thử lại.';
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
