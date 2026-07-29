(() => {
  const init = () => {
    const form = document.querySelector('[data-account-preferences]');
    if (!form) return;
    const toast = form.querySelector('[data-preferences-toast]');
    const save = form.querySelector('[data-preferences-save]');
    const values = () => ({
      appearance: form.querySelector('[name="appearance"]:checked')?.value,
      accent: form.querySelector('[name="accent"]:checked')?.value,
    });
    const showToast = (message, tone) => {
      toast.textContent = message;
      toast.className = `alert alert-${tone} mt-3 mb-0`;
      toast.hidden = false;
      toast.focus();
    };
    const preview = () => window.StarXTheme?.apply(values());
    form.querySelectorAll('input[type="radio"]').forEach((input) => input.addEventListener('change', preview));

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      toast.hidden = true;
      try {
        const response = await fetch(form.action, {
          method: 'POST', body: new FormData(form), credentials: 'same-origin',
          headers: { Accept: 'application/json' },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Không thể lưu cài đặt.');
        window.StarXTheme?.apply(result.preferences);
        window.StarXTheme?.store(result.preferences);
        showToast(result.message, 'success');
      } catch (error) {
        showToast(error.message || 'Không thể lưu cài đặt. Vui lòng thử lại.', 'danger');
      } finally {
        save.disabled = false;
      }
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
