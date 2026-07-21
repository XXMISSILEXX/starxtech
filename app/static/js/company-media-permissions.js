(() => {
  const root = document.querySelector('[data-company-media-permissions]');
  const source = document.getElementById('company-media-permission-principals');
  if (!root || !source) return;

  const principals = JSON.parse(source.textContent || '[]');
  const form = root.querySelector('[data-permission-form]');
  const search = root.querySelector('[data-principal-search]');
  const results = root.querySelector('[data-principal-results]');
  const typeInput = root.querySelector('[data-principal-type]');
  const idInput = root.querySelector('[data-principal-id]');
  const selected = root.querySelector('[data-selected-principal]');
  const selectedLabel = root.querySelector('[data-selected-principal-label]');
  const clear = root.querySelector('[data-clear-principal]');
  const submit = root.querySelector('[data-submit-permission]');
  const submitLabel = root.querySelector('[data-submit-label]');
  const formTitle = root.querySelector('[data-form-title]');
  const cancel = root.querySelector('[data-cancel-edit]');
  const required = root.querySelector('[data-principal-required]');
  const flags = [...root.querySelectorAll('[data-permission-flag]')];
  const presets = [...root.querySelectorAll('[data-permission-preset]')];
  const presetFlags = { view: ['can_view'], view_download: ['can_view', 'can_download'], collaborator: ['can_view', 'can_download', 'can_upload', 'can_edit'], manager: ['can_view', 'can_download', 'can_upload', 'can_edit', 'can_delete', 'can_share'] };
  let editing = false;

  const escapeHtml = (value) => { const node = document.createElement('span'); node.textContent = value || ''; return node.innerHTML; };
  const label = (principal) => principal.type === 'user' ? `${principal.name}${principal.username ? ` · ${principal.username}` : ''}${principal.email ? ` · ${principal.email}` : ''}` : `${principal.name}${principal.description ? ` · ${principal.description}` : ''}`;
  function setPreset(name) { const enabled = presetFlags[name]; if (enabled) flags.forEach((flag) => { flag.checked = enabled.includes(flag.dataset.permissionFlag); }); presets.forEach((button) => button.classList.toggle('active', button.dataset.permissionPreset === name)); }
  function setEditLock(locked) { editing = locked; search.disabled = locked; clear.disabled = locked; clear.classList.toggle('d-none', locked); }
  function clearPrincipal() { typeInput.value = ''; idInput.value = ''; selected.classList.add('d-none'); submit.disabled = true; required.classList.add('d-none'); }
  function choosePrincipal(principal) { typeInput.value = principal.type; idInput.value = principal.id; selectedLabel.textContent = label(principal); selected.classList.remove('d-none'); submit.disabled = false; required.classList.add('d-none'); results.classList.add('d-none'); search.value = ''; search.setAttribute('aria-expanded', 'false'); }
  function renderResults() { if (editing) return; const term = search.value.trim().toLocaleLowerCase(); if (!term) { results.classList.add('d-none'); results.replaceChildren(); return; } const matches = principals.filter((principal) => Object.values(principal).join(' ').toLocaleLowerCase().includes(term)).slice(0, 8); results.replaceChildren(...matches.map((principal) => { const button = document.createElement('button'); button.type = 'button'; button.className = 'list-group-item list-group-item-action'; button.setAttribute('role', 'option'); const detail = principal.type === 'user' ? `${principal.username}${principal.email ? ` · ${principal.email}` : ''} · ${principal.role || ''}` : principal.description || principal.code || ''; button.innerHTML = `<span class="d-block fw-semibold">${escapeHtml(principal.name)}</span><small class="text-muted">${escapeHtml(principal.type === 'user' ? 'Người dùng' : 'Vai trò')} · ${escapeHtml(detail)}</small>`; button.addEventListener('click', () => choosePrincipal(principal)); return button; })); results.classList.toggle('d-none', matches.length === 0); search.setAttribute('aria-expanded', String(matches.length > 0)); }
  function resetForm() { form.reset(); setEditLock(false); clearPrincipal(); setPreset('view'); formTitle.textContent = 'Thêm quyền truy cập'; submitLabel.textContent = 'Thêm quyền'; cancel.classList.add('d-none'); }
  search.addEventListener('input', renderResults); search.addEventListener('focus', renderResults); clear.addEventListener('click', clearPrincipal); presets.forEach((button) => button.addEventListener('click', () => setPreset(button.dataset.permissionPreset))); flags.forEach((flag) => flag.addEventListener('change', () => setPreset('custom')));
  form.addEventListener('submit', (event) => { if (!idInput.value) { event.preventDefault(); required.classList.remove('d-none'); search.focus(); } });
  root.querySelectorAll('[data-edit-permission]').forEach((button) => button.addEventListener('click', () => { const row = button.closest('[data-acl-entry]'); choosePrincipal({ type: row.dataset.principalType, id: row.dataset.principalId, name: row.dataset.principalName, description: row.dataset.principalDetail }); flags.forEach((flag) => { const key = flag.dataset.permissionFlag.replace(/_([a-z])/g, (_, char) => char.toUpperCase()); flag.checked = row.dataset[key] === '1'; }); setPreset('custom'); setEditLock(true); formTitle.textContent = 'Cập nhật quyền truy cập'; submitLabel.textContent = 'Cập nhật quyền'; cancel.classList.remove('d-none'); form.scrollIntoView({ behavior: 'smooth', block: 'center' }); }));
  cancel.addEventListener('click', resetForm);
})();
