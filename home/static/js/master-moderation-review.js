(() => {
  const dialog = document.querySelector('[data-master-moderation-dialog]');
  const forms = document.querySelectorAll('form[data-master-moderation]');
  if (!dialog || !forms.length || typeof dialog.showModal !== 'function') return;

  const description = dialog.querySelector('[data-master-moderation-description]');
  const action = dialog.querySelector('[data-master-moderation-action]');
  const content = dialog.querySelector('[data-master-moderation-content]');
  const note = dialog.querySelector('[data-master-moderation-note]');
  const detail = dialog.querySelector('[data-master-moderation-detail]');
  const cancel = dialog.querySelector('[data-master-moderation-cancel]');
  const confirm = dialog.querySelector('[data-master-moderation-confirm]');
  let pending = null;
  let sending = false;

  forms.forEach(form => form.addEventListener('submit', event => {
    if (sending || !form.reportValidity()) return;
    event.preventDefault();
    const submitter = event.submitter || form.querySelector('button');
    const article = form.closest('article');
    const selectedAction = submitter?.value;
    action.textContent = submitter?.textContent.trim() || 'Revisar';
    content.textContent = article?.querySelector('h2, h3')?.textContent.trim() || 'Conteúdo selecionado';
    note.textContent = form.elements.namedItem('nota')?.value.trim() || 'Nenhum retorno preenchido.';
    description.textContent = selectedAction === 'aprovar'
      ? 'A aprovação publica este conteúdo após a validação atual do servidor.'
      : 'O pedido de ajustes devolve este conteúdo ao autor sem publicá-lo.';
    const link = article?.querySelector('a.mh-text-link[href]');
    detail.hidden = !link;
    if (link) detail.href = link.href;
    pending = {form, submitter};
    dialog.showModal();
  }));

  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    if (dialog.open) return;
    const submitter = pending?.submitter;
    pending = null;
    if (!sending) submitter?.focus();
  });
  confirm.addEventListener('click', () => {
    if (!pending) return;
    const {form, submitter} = pending;
    if (!form.reportValidity()) { dialog.close(); return; }
    sending = true;
    confirm.disabled = true;
    form.requestSubmit(submitter);
  });
})();
