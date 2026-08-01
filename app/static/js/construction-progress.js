document.querySelectorAll("[data-progress-chart]").forEach(async (canvas) => {
  const data = await fetch(canvas.dataset.chartUrl).then((response) => response.json());
  const money = Array.isArray(data.completed);
  new Chart(canvas, {type: "bar", data: {labels: data.labels, datasets: money ? [{label: "Đã thực hiện", data: data.completed, backgroundColor: "#198754", stack: "money"}, {label: "Còn lại", data: data.remaining, backgroundColor: "#dee2e6", stack: "money"}] : [{label: "Hoàn thành (%)", data: data.percentages, backgroundColor: "#0d6efd"}]}, options: {responsive: true, scales: {y: {beginAtZero: true, max: money ? undefined : 100}}, plugins: {legend: {display: money}}}});
});
