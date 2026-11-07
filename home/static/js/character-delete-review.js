(() => {
  const dialog = document.querySelector('[data-character-delete-review]');
  if (!dialog || typeof dialog.showModal !== 'function') return;

  const description = dialog.querySelector('[data-character-delete-description]');
  const cancel = dialog.querySelector('[data-character-delete-cancel]');
  const confirm = dialog.querySelector('[data-character-delete-confirm]');
  let pendingForm = null;
  let pendingSubmitter = null;

  for (const form of document.querySelectorAll('form[data-character-delete]')) {
    // Retain the native confirmation if dialog support or this script is unavailable.
    form.onsubmit = null;
    form.addEventListener('submit', event => {
      if (form.dataset.characterDeleteConfirmed === 'true') return;
      event.preventDefault();
      pendingForm = form;
      pendingSubmitter = event.submitter || form.querySelector('button[type="submit"]');
      description.textContent = `A ficha ${form.dataset.characterName || 'selecionada'} será removida permanentemente da sua conta.`;
      dialog.showModal();
    });
  }

  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    if (dialog.open) return;
    pendingForm = null;
    pendingSubmitter = null;
  });
  confirm.addEventListener('click', () => {
    if (!pendingForm) return;
    const form = pendingForm;
    const submitter = pendingSubmitter;
    form.dataset.characterDeleteConfirmed = 'true';
    form.requestSubmit(submitter);
    delete form.dataset.characterDeleteConfirmed;
  });
})();
