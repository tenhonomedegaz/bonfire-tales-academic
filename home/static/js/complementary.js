/* Client-only filtering. Reading state and notification ownership stay server-side. */
(() => {
  'use strict';
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  const matches = (text, state, query, selected) => (!selected || selected === state) && norm(text).includes(norm(query));
  if (typeof module === 'object' && module.exports) module.exports = {norm, matches};
  if (typeof document === 'undefined') return;
  for (const root of document.querySelectorAll('[data-cp-filter-root]')) {
    const query = root.querySelector('[data-cp-filter-query]');
    const state = root.querySelector('[data-cp-filter-state]');
    const count = root.querySelector('[data-cp-filter-count]');
    const empty = root.querySelector('[data-cp-filter-empty]');
    const items = [...root.querySelectorAll('[data-cp-filter-item]')];
    const links = [...root.querySelectorAll('[data-cp-filter-link]')];
    function filter() {
      let visible = 0;
      for (const item of items) {
        item.hidden = !matches(item.textContent, item.dataset.state || '', query.value, state?.value || '');
        if (!item.hidden) visible++;
      }
      for (const link of links) {
        const target = (link.getAttribute('href') || '').slice(1);
        link.hidden = !items.some(item => item.id === target && !item.hidden);
      }
      if (count) count.textContent = visible + (state ? (visible === 1 ? ' notificação' : ' notificações') : (visible === 1 ? ' registro' : ' registros'));
      if (empty) empty.hidden = visible > 0 || items.length === 0;
    }
    query.addEventListener('input', filter);
    state?.addEventListener('change', filter);
    filter();
  }
})();
