(() => {
  const form = document.querySelector('.bs-acquire form');
  const dialog = document.querySelector('[data-slot-redemption-dialog]');
  if (!form || !dialog || typeof dialog.showModal !== 'function') return;

  const cancel = dialog.querySelector('[data-slot-redemption-cancel]');
  const confirm = dialog.querySelector('[data-slot-redemption-confirm]');
  let submitter = null;
  let sending = false;

  form.addEventListener('submit', event => {
    if (sending) return;
    event.preventDefault();
    submitter = event.submitter || form.querySelector('button');
    dialog.showModal();
  });
  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    if (!sending) submitter?.focus();
    submitter = null;
  });
  confirm.addEventListener('click', () => {
    if (!submitter) return;
    sending = true;
    confirm.disabled = true;
    form.requestSubmit(submitter);
  });
})();
