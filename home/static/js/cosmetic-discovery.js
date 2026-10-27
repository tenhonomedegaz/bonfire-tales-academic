(() => {
  'use strict';
  function start() {
    const form = document.querySelector('[data-discovery-filters]');
    if (!form) return;
    const cards = [...document.querySelectorAll('[data-discovery-card]')];
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
    function filter() {
      const q = normalize(form.elements.q.value);
      let count = 0;
      cards.forEach(card => {
        card.hidden = !(normalize(card.dataset.search).includes(q) &&
          (!form.elements.tipo.value || card.dataset.kind === form.elements.tipo.value) &&
          (!form.elements.colecao.value || card.dataset.collection === form.elements.colecao.value) &&
          (!form.elements.estado.value || card.dataset.state === form.elements.estado.value));
        if (!card.hidden) count++;
      });
      document.querySelector('[data-discovery-count]').textContent = count;
      document.querySelector('[data-discovery-empty]').hidden = count !== 0;
    }
    form.addEventListener('input', filter);
    form.addEventListener('change', filter);
    form.addEventListener('submit', event => { event.preventDefault(); filter(); });
    document.querySelector('[data-discovery-reset]').addEventListener('click', event => {
      event.preventDefault();
      ['q', 'tipo', 'colecao', 'estado'].forEach(key => { form.elements[key].value = ''; });
      filter();
      form.elements.q.focus();
    });
    filter();

    const dialog = document.querySelector('[data-discovery-dialog]');
    if (!dialog || typeof dialog.showModal !== 'function') return;
    const mount = dialog.querySelector('[data-discovery-dialog-art]');
    let opener;
    cards.forEach(card => {
      const button = card.querySelector('[data-discovery-preview]');
      button.hidden = false;
      button.addEventListener('click', () => {
        opener = button;
        dialog.querySelector('h2').textContent = card.querySelector('h2').textContent;
        dialog.querySelector('#discovery-dialog-reason').textContent = card.querySelector('.discovery-reason').textContent;
        const art = card.querySelector('.discovery-art').cloneNode(true);
        art.querySelectorAll('img').forEach(image => { image.loading = 'eager'; });
        mount.replaceChildren(art);
        dialog.showModal();
        if (typeof window.CosmeticRenderer?.mount === 'function') window.CosmeticRenderer.mount(mount);
      });
    });
    dialog.querySelector('[data-discovery-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { mount.replaceChildren(); if (opener) opener.focus(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
