(() => {
  const modal = document.getElementById('projectDocumentFolderActionModal');
  const form = modal?.querySelector('[data-folder-action-form]');
  const title = modal?.querySelector('[data-folder-action-title]') || modal?.querySelector('#projectDocumentFolderActionTitle');
  const nameFields = modal?.querySelector('[data-folder-rename-fields]');
  const moveFields = modal?.querySelector('[data-folder-move-fields]');
  const nameInput = modal?.querySelector('[name="name"]');
  const destination = modal?.querySelector('[name="parent_id"]');
  const submit = modal?.querySelector('[data-folder-action-submit]');
  if (!modal || !form || !title || !nameFields || !moveFields || !nameInput || !destination || !submit) return;

  document.querySelectorAll('[data-folder-rename], [data-folder-move]').forEach((button) => button.addEventListener('click', () => {
    const isMove = button.hasAttribute('data-folder-move');
    form.action = button.dataset.folderUrl;
    title.textContent = isMove ? 'Di chuyển thư mục' : 'Đổi tên thư mục';
    nameFields.classList.toggle('d-none', isMove);
    moveFields.classList.toggle('d-none', !isMove);
    nameInput.required = !isMove;
    destination.required = isMove;
    submit.textContent = isMove ? 'Di chuyển' : 'Lưu';
    if (isMove) {
      destination.replaceChildren();
      JSON.parse(button.dataset.destinations || '[]').forEach((item) => destination.add(new Option(item.name, item.id)));
    } else {
      nameInput.value = button.dataset.folderName || '';
    }
    bootstrap.Modal.getOrCreateInstance(modal).show();
  }));
})();
