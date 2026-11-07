(() => {
  const dialog = document.querySelector('[data-character-publication-review]');
  if (!dialog || typeof dialog.showModal !== 'function') return;

  const title = dialog.querySelector('[data-character-publication-title]');
  const description = dialog.querySelector('[data-character-publication-description]');
  const visibility = dialog.querySelector('[data-character-publication-visibility]');
  const preview = dialog.querySelector('[data-character-publication-preview]');
  const confirm = dialog.querySelector('[data-character-publication-confirm]');
  const cancel = dialog.querySelector('[data-character-publication-cancel]');
  let pendingForm = null;
  let pendingSubmitter = null;

  for (const form of document.querySelectorAll('form[data-character-publication-action]')) {
    form.addEventListener('submit', event => {
      if (form.dataset.characterPublicationConfirmed === 'true') return;
      event.preventDefault();
      pendingForm = form;
      pendingSubmitter = event.submitter || form.querySelector('button[type="submit"]');
      const publishing = form.dataset.characterPublicationAction === 'publish';
      const name = form.dataset.characterName || 'esta ficha';
      title.textContent = publishing ? 'Publicar ficha' : 'Retirar publicação';
      description.textContent = publishing
        ? `A ficha ${name} ficará visível para visitantes. Revise as escolhas salvas antes de publicar.`
        : `A ficha ${name} deixará de aparecer para visitantes. Suas escolhas de apresentação serão preservadas.`;
      if (publishing) {
        const visible = ['descrição', 'atributos', 'perícias', 'resumo mecânico'].filter((_, index) =>
          [form.dataset.characterDescription, form.dataset.characterAttributes,
            form.dataset.characterSkills, form.dataset.characterSummary][index] === 'true');
        visibility.textContent = visible.length
          ? `A apresentação salva inclui: ${visible.join(', ')}.`
          : 'A apresentação salva não inclui descrição nem grupos mecânicos.';
      }
      visibility.hidden = !publishing;
      preview.href = form.dataset.characterPreviewUrl;
      preview.hidden = !publishing;
      confirm.textContent = publishing ? 'Publicar ficha' : 'Retirar publicação';
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
    form.dataset.characterPublicationConfirmed = 'true';
    form.requestSubmit(submitter);
    delete form.dataset.characterPublicationConfirmed;
  });
})();
