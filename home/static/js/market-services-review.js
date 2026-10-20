(() => {
  const dialog = document.querySelector('#service-review');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const subjectLabel = dialog.querySelector('[data-service-subject-label]');
  const subject = dialog.querySelector('[data-service-subject]');
  const amount = dialog.querySelector('[data-service-amount]');
  const note = dialog.querySelector('[data-service-note]');
  const title = dialog.querySelector('#service-review-title');
  const confirm = dialog.querySelector('[data-service-confirm]');
  let pending = null;
  let approved = null;

  document.querySelectorAll('form[data-service-review]').forEach(form => {
    form.addEventListener('submit', event => {
      if (approved === form) { approved = null; return; }
      event.preventDefault();
      const button = event.submitter || form.querySelector('button[type="submit"], button:not([type])');
      if (!button) return;
      if (!button.formNoValidate && !form.reportValidity()) return;
      const action = button.value || button.textContent.trim();
      subjectLabel.textContent = 'Personagens';
      if (form.classList.contains('training-start')) {
        const training = form.querySelector('#training-choice').selectedOptions[0];
        subjectLabel.textContent = 'Personagem e treinamento';
        title.textContent = 'Revisar treinamento';
        subject.textContent = `${form.dataset.character} · ${training.textContent.trim()}`;
        amount.textContent = form.dataset.cost;
        note.textContent = 'O custo será debitado agora da ficha selecionada. A proficiência será creditada após 30 dias.';
      } else if (form.classList.contains('loan-proposal')) {
        const own = form.dataset.character;
        const other = form.querySelector('#loan-player').selectedOptions[0]?.textContent.trim() || '';
        const requesting = form.querySelector('#loan-role').value === 'solicitar';
        title.textContent = 'Revisar proposta de empréstimo';
        subject.textContent = requesting ? `${own} solicita a ${other}` : `${own} oferece a ${other}`;
        amount.textContent = `${form.querySelector('#loan-value').value} PO`;
        note.textContent = 'A proposta será enviada. O ouro só será transferido se a outra pessoa aceitar.';
      } else {
        const character = form.dataset.character;
        const counterpart = form.dataset.counterpart || '';
        subjectLabel.textContent = character
          ? (form.classList.contains('loan-payment') ? 'Ficha debitada e credor' : 'Ficha selecionada e contraparte')
          : 'Personagens';
        subject.textContent = character ? `${character} → ${counterpart}` : counterpart;
        const balance = form.dataset.balance || '';
        if (form.classList.contains('loan-payment')) {
          const full = button.name === 'valor_po';
          const requestedPc = Number(form.querySelector('input[name="valor_po"]').value) * 100;
          const balancePc = Number(form.dataset.balancePc);
          const settlesBalance = full || (balancePc > 0 && requestedPc >= balancePc);
          title.textContent = settlesBalance ? 'Revisar quitação' : 'Revisar pagamento';
          amount.textContent = settlesBalance ? balance : `${form.querySelector('input[name="valor_po"]').value} PO (saldo: ${balance})`;
          note.textContent = settlesBalance
            ? 'O saldo devido será debitado da sua ficha e o empréstimo será quitado.'
            : 'O valor informado será debitado da sua ficha.';
        } else {
          title.textContent = 'Revisar ' + button.textContent.trim().toLowerCase();
          amount.textContent = balance;
          note.textContent = action === 'aceitar'
            ? 'Ao aceitar, o ouro será transferido do credor ao devedor.'
            : action === 'quitar'
              ? 'A equipe marcará este contrato como quitado.'
              : 'Esta ação será enviada para o empréstimo indicado.';
        }
      }
      confirm.textContent = button.textContent.trim();
      pending = { form, button };
      dialog.showModal();
    });
  });

  dialog.querySelector('[data-service-back]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    const button = pending?.button;
    pending = null;
    button?.focus({ preventScroll: true });
  });
  confirm.addEventListener('click', () => {
    if (!pending) return;
    const { form, button } = pending;
    if (!button.formNoValidate && !form.reportValidity()) return;
    pending = null;
    dialog.close();
    approved = form;
    if (form.classList.contains('loan-payment') && button.name === 'valor_po') {
      form.querySelector('input[name="valor_po"]').value = '';
    }
    form.requestSubmit(button);
  });
})();
