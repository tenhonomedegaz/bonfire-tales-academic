/* Busca compartilhada: filtra os nós existentes, sem modificar escolhas/limites. */
(function () {
  'use strict';
  let sequence = 0;
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  function attach(root) {
    if (root.dataset.spellPickerReady) return;
    root.dataset.spellPickerReady = '1';
    if (!root.id) root.id = 'spell-picker-' + (++sequence);
    if (root.tagName === 'SELECT') {
      const wrapper = document.createElement('div');
      wrapper.className = 'spell-picker-select';
      root.before(wrapper);
      wrapper.append(root);
    }
    const ui = document.createElement('div');
    ui.className = 'spell-picker-tools';
    root.before(ui);
    const search = root.dataset.spellInput ? document.querySelector(root.dataset.spellInput) : document.createElement('input');
    if (!search) return;
    if (!root.dataset.spellInput) {
      const label = document.createElement('label');
      label.textContent = root.dataset.spellPicker || 'Buscar magias';
      search.type = 'search';
      search.placeholder = 'Nome em português ou inglês';
      label.append(search);
      ui.append(label);
    }
    search.setAttribute('aria-controls', root.id);
    search.autocomplete = 'off';
    const level = root.dataset.spellLevelInput ? document.querySelector(root.dataset.spellLevelInput) : document.createElement('select');
    const ownLevel = !root.dataset.spellLevelInput;
    if (ownLevel) {
      level.setAttribute('aria-label', 'Filtrar por círculo');
      level.setAttribute('aria-controls', root.id);
      ui.append(level);
    }
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.className = 'spell-picker-status';
    const summary = document.createElement('div');
    summary.className = 'spell-picker-summary';
    summary.setAttribute('aria-label', 'Escolhas selecionadas');
    ui.append(status, summary);
    function rows() {
      return root.tagName === 'SELECT' ? Array.from(root.options).filter(r => r.value) : Array.from(root.querySelectorAll(root.dataset.spellRow || 'label'));
    }
    function selected(row) {
      return row.tagName === 'OPTION' ? row.selected : !!row.querySelector('input:checked') || row.dataset.spellSelected === 'true';
    }
    function name(row) { return (row.dataset.spellName || row.dataset.search || row.textContent).trim(); }
    let previousChosen = [];
    function update() {
      const all = rows();
      if (ownLevel) {
        const levels = [...new Set(all.map(row => row.dataset.spellLevel || row.dataset.level).filter(Boolean))].sort((a, b) => Number(a) - Number(b));
        const signature = levels.join(',');
        if (level.dataset.levels !== signature) {
          const previous = level.value;
          level.replaceChildren(new Option('Todos os círculos', ''), ...levels.map(value => new Option(value === '0' ? 'Truques' : value + 'º círculo', value)));
          level.value = levels.includes(previous) ? previous : '';
          level.dataset.levels = signature;
        }
        level.hidden = levels.length < 2;
      }
      const query = normalize(search.value);
      const chosen = all.filter(selected);
      let shown = 0;
      all.forEach(row => {
        const matches = (!query || normalize(name(row)).includes(query)) &&
          (!level || !level.value || (row.dataset.spellLevel || row.dataset.level) === level.value);
        row.classList.toggle('spell-picker-hidden', !matches);
        row.hidden = !matches;
        if (matches) shown++;
      });
      if (root.dataset.spellGroup) {
        root.querySelectorAll(root.dataset.spellGroup).forEach(group => {
          const filtering = !!(query || (level && level.value));
          const hasMatch = all.some(row => group.contains(row) && !row.hidden);
          group.hidden = filtering && !hasMatch;
          if (group.tagName === 'DETAILS') {
            if (filtering && hasMatch && !group.open) {
              group.open = true;
              group.dataset.spellPickerAutoOpen = '1';
            } else if (!filtering && group.dataset.spellPickerAutoOpen === '1') {
              group.open = false;
              delete group.dataset.spellPickerAutoOpen;
            }
          }
        });
      }
      status.textContent = (shown ? shown + ' de ' + all.length + ' resultados.' : 'Nenhum resultado.') + ' ' + chosen.length + ' selecionada(s).';
      const signature = chosen.map(row => [row.value || '', name(row)]);
      const fingerprint = JSON.stringify(signature);
      if (summary.dataset.signature !== fingerprint || chosen.some((row, i) => row !== previousChosen[i])) {
        previousChosen = chosen;
        summary.dataset.signature = fingerprint;
        summary.replaceChildren();
        chosen.forEach(row => {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = name(row);
          button.title = 'Mostrar escolha selecionada';
          button.addEventListener('click', () => {
            search.value = '';
            if (level) level.value = '';
            update();
            const target = row.tagName === 'OPTION' ? root : row.querySelector('input:not([type=hidden]):not(:disabled), button:not(:disabled), a, select:not(:disabled)') || row;
            if (!target.matches('input,button,a,select')) target.tabIndex = -1;
            target.focus();
            target.scrollIntoView({ block: 'nearest' });
          });
          summary.append(button);
        });
      }
    }
    search.addEventListener('input', update);
    search.addEventListener('keydown', event => {
      if (event.key === 'Enter') event.preventDefault();
      if (event.key === 'Escape') { event.preventDefault(); search.value = ''; update(); }
    });
    if (level) level.addEventListener('change', update);
    root.addEventListener('change', update);
    // Criação e level-up reconstroem catálogos; consultar novos nós e reaplicar a busca.
    new MutationObserver(update).observe(root, { childList: true, subtree: true,
      attributes: true, attributeFilter: ['disabled', 'selected', 'checked', 'data-spell-selected'] });
    const form = root.closest('form');
    if (form) form.addEventListener('reset', () => requestAnimationFrame(update));
    update();
  }
  function scan(node) {
    if (node.nodeType !== 1 && node !== document) return;
    if (node.matches && node.matches('[data-spell-picker]')) attach(node);
    node.querySelectorAll('[data-spell-picker]').forEach(attach);
  }
  scan(document);
  new MutationObserver(changes => changes.forEach(change => change.addedNodes.forEach(scan)))
    .observe(document.body, { childList: true, subtree: true });
})();
