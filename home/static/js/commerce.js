/* Progressive storefront filters and review. All prices/permissions remain server-side. */
(() => {
  'use strict';
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  const store = document.querySelector('[data-co-store]');
  if (store) {
    const search = store.querySelector('[data-co-search]');
    const kind = store.querySelector('[data-co-kind]');
    const items = [...store.querySelectorAll('[data-co-item]')];
    const count = store.querySelector('[data-co-count]');
    const empty = store.querySelector('[data-co-empty]');
    function filter() {
      let visible = 0;
      for (const item of items) {
        const matches = normalize(item.dataset.name).includes(normalize(search.value)) && (!kind.value || kind.value === item.dataset.kind);
        item.hidden = !matches;
        if (matches) visible++;
      }
      count.textContent = visible + (visible === 1 ? ' oferta' : ' ofertas');
      empty.hidden = visible !== 0 || items.length === 0;
    }
    search.addEventListener('input', filter);
    kind.addEventListener('change', filter);
    for (const button of store.querySelectorAll('[data-co-reset]')) button.addEventListener('click', () => { search.value = ''; kind.value = ''; filter(); search.focus(); });
    filter();
  }
  const dialog = document.getElementById('co-review');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  let pending = null;
  let opener = null;
  let approved = null;
  const proceed = dialog.querySelector('[data-co-proceed]');
  function review(form, button) {
    if (!form.reportValidity()) return;
    pending = form; opener = button;
    dialog.querySelector('[data-co-product]').textContent = form.dataset.product || '';
    dialog.querySelector('[data-co-amount]').textContent = form.dataset.amount || '';
    dialog.querySelector('[data-co-mode]').textContent = form.dataset.mode || '';
    const character = form.querySelector('[name="character"]');
    const selected = character ? character.options[character.selectedIndex] : null;
    dialog.querySelector('[data-co-note]').textContent = (form.dataset.note || '') + (selected ? ' Personagem: ' + selected.textContent + '.' : '');
    const demo = form.hasAttribute('data-co-readonly');
    dialog.querySelector('[data-co-demo]').hidden = !demo;
    proceed.disabled = demo;
    proceed.textContent = demo ? 'Desativado na prévia' : character || form.dataset.mode === 'Resgate de evento' ? 'Confirmar resgate' : 'Continuar para o Asaas';
    dialog.showModal();
  }
  for (const form of document.querySelectorAll('form[data-purchase-review]')) {
    form.addEventListener('submit', event => {
      if (approved === form && !form.hasAttribute('data-co-readonly')) { approved = null; return; }
      event.preventDefault(); review(form, event.submitter);
    });
    const demoButton = form.querySelector('[data-co-review-demo]');
    if (demoButton) demoButton.addEventListener('click', () => review(form, demoButton));
  }
  for (const close of dialog.querySelectorAll('[data-co-close]')) close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { pending = null; approved = null; if (opener) opener.focus(); });
  proceed.addEventListener('click', () => {
    const form = pending;
    if (!form || form.hasAttribute('data-co-readonly') || !form.reportValidity()) return;
    // Preserve the native method, action, target, CSRF and hidden fields.
    pending = null; dialog.close(); approved = form;
    form.requestSubmit();
  });
})();
