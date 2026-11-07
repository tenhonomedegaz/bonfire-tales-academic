(() => {
  const dialog = document.querySelector('[data-master-moderation-dialog]');
  const forms = document.querySelectorAll('form[data-master-moderation]');
  if (!dialog || !forms.length || typeof dialog.showModal !== 'function') return;

  const description = dialog.querySelector('[data-master-moderation-description]');
  const action = dialog.querySelector('[data-master-moderation-action]');
  const content = dialog.querySelector('[data-master-moderation-content]');
  const noteLabel = dialog.querySelector('[data-master-moderation-note-label]');
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
    const kind = form.dataset.masterModeration;
    noteLabel.textContent = {verificacao: 'Evidência registrada', vitrine: 'Motivo da decisão'}[kind] || 'Retorno privado';
    note.textContent = (form.elements.namedItem('nota') || form.elements.namedItem('observacao'))?.value.trim() || 'Nenhum retorno preenchido.';
    const descriptions = {
      mesa: selectedAction === 'aprovar'
        ? 'A aprovação publica este anúncio após a validação atual do servidor.'
        : 'O pedido de ajustes devolve este anúncio ao autor sem publicá-lo.',
      trabalho: selectedAction === 'aprovar'
        ? 'A aprovação publica este trabalho após a validação atual do servidor.'
        : 'O pedido de ajustes devolve este trabalho ao autor sem publicá-lo.',
      permissao: {
        autorizar: 'Autorizar libera a apresentação pública do mestre no site.',
        recusar: 'A solicitação será recusada no site.',
        suspender: 'A apresentação pública do mestre será suspensa no site.',
      }[selectedAction],
      verificacao: {
        validar: 'Esta mesa será registrada como verificada para a elegibilidade da vitrine.',
        invalidar: 'A evidência desta mesa deixará de contar para a elegibilidade da vitrine.',
      }[selectedAction],
      vitrine: selectedAction === 'autorizar'
        ? 'Esta autorização permite enviar anúncios demonstrativos à revisão; não libera cobrança.'
        : 'A autorização de envio de anúncios demonstrativos será revogada.',
    };
    description.textContent = descriptions[kind] || 'Revise esta decisão antes de enviar.';
    if (kind === 'verificacao') {
      description.textContent += ` Divulgação aberta: ${form.elements.namedItem('aberta')?.checked ? 'sim' : 'não'}.`;
    }
    const link = kind === 'mesa' || kind === 'trabalho'
      ? article?.querySelector('a.mh-text-link[href]') : null;
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
