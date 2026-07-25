(() => {
  const cards = () => [...document.querySelectorAll('[data-report-attachment-card]')].filter((card) => ['processing', 'partial'].includes(card.dataset.attachmentStatus));
  let timer, attempts = 0, controller;
  const token = () => document.querySelector('input[name="csrf_token"]')?.value || '';
  const update = (card, item) => {
    card.dataset.attachmentStatus = item.status;
    const image = card.querySelector('[data-report-attachment-thumbnail]') || card.querySelector('.report-thumb');
    const trigger = card.querySelector('[data-media-preview-trigger]');
    if (item.thumbnail_url && image) { const preload = new Image(); preload.onload = () => { image.src = item.thumbnail_url; image.classList.add('is-ready'); }; preload.src = item.thumbnail_url; }
    if (item.preview_url && trigger) { trigger.dataset.previewEndpoint = item.preview_url; trigger.dataset.downloadEndpoint ||= card.querySelector('[data-download-endpoint]')?.dataset.downloadEndpoint || trigger.dataset.downloadEndpoint; }
    const label = card.querySelector('[data-report-attachment-processing]');
    if (item.status === 'ready') label?.remove();
    if (item.status === 'failed' && label) { label.textContent = item.message || 'Không thể tạo ảnh xem trước'; label.classList.remove('text-muted'); label.classList.add('text-danger'); }
    if (item.status === 'recovery_pending' && label) { label.textContent = item.message || 'Ảnh đang chờ xử lý lại.'; label.classList.remove('text-danger'); label.classList.add('text-muted'); }
  };
  const poll = async () => {
    if (document.visibilityState !== 'visible' || attempts++ >= 40) return;
    const pending = cards(); if (!pending.length) return;
    controller?.abort(); controller = new AbortController();
    try { const response = await fetch('/attachments/status-batch', {method:'POST', credentials:'same-origin', cache:'no-store', signal:controller.signal, headers:{'Content-Type':'application/json','X-CSRFToken':token()}, body:JSON.stringify({attachment_ids:pending.map((card) => Number(card.dataset.attachmentId))})}); if (!response.ok) throw new Error(); const data = await response.json(); data.attachments.forEach((item) => { const card = document.querySelector(`[data-report-attachment-card][data-attachment-id="${item.attachment_id}"]`); if (card) update(card, item); }); } catch (_) {} finally { if (cards().length && attempts < 40) timer = setTimeout(poll, 1800); }
  };
  document.addEventListener('DOMContentLoaded', () => { if (cards().length) timer = setTimeout(poll, 750); document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && cards().length) { clearTimeout(timer); poll(); } }); window.addEventListener('pagehide', () => { clearTimeout(timer); controller?.abort(); }); });
})();
