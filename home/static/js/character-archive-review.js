(() => {
  const dialog = document.querySelector('[data-character-archive-review]');
  if (!dialog || typeof dialog.showModal !== 'function') return;

  const title = dialog.querySelector('[data-character-archive-title]');
  const description = dialog.querySelector('[data-character-archive-description]');
  const confirm = dialog.querySelector('[data-character-archive-confirm]');
  const cancel = dialog.querySelector('[data-character-archive-cancel]');
  let pendingForm = null;
  let pendingSubmitter = null;

  for (const form of document.querySelectorAll('form[data-character-archive-action]')) {
    form.addEventListener('submit', event => {
      if (form.dataset.characterArchiveConfirmed === 'true') return;
      event.preventDefault();
      pendingForm = form;
      pendingSubmitter = event.submitter || form.querySelector('button[type="submit"]');
      const name = form.dataset.characterName || 'esta ficha';
      const restoring = form.dataset.characterArchiveAction === 'restore';
      title.textContent = restoring ? 'Restaurar ficha ativa' : 'Arquivar ficha';
      description.textContent = restoring
        ? `A ficha ${name} voltará a ocupar uma vaga ativa. Ela continuará privada até você publicá-la.`
        : `A ficha ${name} será retirada da publicação e ficará preservada no cofre. A vaga ativa ficará livre.`;
      confirm.textContent = restoring ? 'Restaurar ficha' : 'Arquivar ficha';
      dialog.showModal();
    });
  }

  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    pendingForm = null;
    pendingSubmitter = null;
  });
  confirm.addEventListener('click', () => {
    if (!pendingForm) return;
    const form = pendingForm;
    const submitter = pendingSubmitter;
    form.dataset.characterArchiveConfirmed = 'true';
    form.requestSubmit(submitter);
    delete form.dataset.characterArchiveConfirmed;
  });
})();
