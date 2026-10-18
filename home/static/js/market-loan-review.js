(() => {
  const dialog = document.querySelector('#loan-review');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const parties = dialog.querySelector('[data-loan-parties]');
  const amount = dialog.querySelector('[data-loan-amount]');
  const note = dialog.querySelector('[data-loan-note]');
  const title = dialog.querySelector('#loan-review-title');
  const confirm = dialog.querySelector('[data-loan-confirm]');
  let pending = null;
  let approved = null;

  document.querySelectorAll('form[data-loan-review]').forEach(form => {
    form.addEventListener('submit', event => {
      if (approved === form) { approved = null; return; }
      event.preventDefault();
      if (!form.reportValidity()) return;
      const button = event.submitter || form.querySelector('button[type="submit"], button:not([type])');
      if (!button) return;
      const action = button.value || button.textContent.trim();
      if (form.classList.contains('loan-proposal')) {
        const own = form.dataset.character;
        const other = form.querySelector('#loan-player').selectedOptions[0]?.textContent.trim() || '';
        const requesting = form.querySelector('#loan-role').value === 'solicitar';
        title.textContent = 'Revisar proposta de empréstimo';
        parties.textContent = requesting ? `${own} solicita a ${other}` : `${own} oferece a ${other}`;
        amount.textContent = `${form.querySelector('#loan-value').value} PO`;
        note.textContent = 'A proposta será enviada. O ouro só será transferido se a outra pessoa aceitar.';
      } else {
        parties.textContent = form.dataset.counterpart || '';
        const balance = form.dataset.balance || '';
        if (form.classList.contains('loan-payment')) {
          const full = button.name === 'valor_po';
          title.textContent = full ? 'Revisar quitação' : 'Revisar pagamento';
          amount.textContent = full ? balance : `${form.querySelector('input[name="valor_po"]').value} PO (saldo: ${balance})`;
          note.textContent = full ? 'O saldo devido será debitado da sua ficha.' : 'O valor informado será debitado da sua ficha.';
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

  dialog.querySelector('[data-loan-back]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    const button = pending?.button;
    pending = null;
    button?.focus({ preventScroll: true });
  });
  confirm.addEventListener('click', () => {
    if (!pending) return;
    const { form, button } = pending;
    if (!form.reportValidity()) return;
    pending = null;
    dialog.close();
    approved = form;
    form.requestSubmit(button);
  });
})();
