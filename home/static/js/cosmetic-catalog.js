(() => {
  'use strict';
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

  function enhance(root) {
    if (root.dataset.catalogReady) return;
    const select = root.querySelector('[data-catalog-select]');
    const controls = root.querySelector('[data-catalog-controls]');
    const filter = root.querySelector('[data-catalog-filter]');
    const empty = root.querySelector('[data-catalog-empty]');
    const tiles = [...root.querySelectorAll('[data-catalog-tile]')];
    if (!select || !controls || !filter || !empty) return;
    const radios = tiles.map(tile => tile.querySelector('[data-catalog-radio]'));
    if (radios.some(radio => !radio)) return;

    function sync() {
      radios.forEach(radio => {
        const option = [...select.options].find(item => item.value === radio.value);
        radio.disabled = select.disabled || !option || option.disabled;
        radio.checked = !!option && option.selected;
        radio.closest('[data-catalog-tile]').classList.toggle('is-locked', radio.disabled);
      });
    }

    root.addEventListener('change', event => {
      const radio = event.target;
      if (!radios.includes(radio)) return;
      const option = [...select.options].find(item => item.value === radio.value);
      if (select.disabled || radio.disabled || !option || option.disabled) {
        sync();
        return;
      }
      select.value = radio.value;
      select.dispatchEvent(new Event('input', { bubbles: true }));
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    select.addEventListener('input', sync);
    select.addEventListener('change', sync);
    if (select.form) select.form.addEventListener('reset', () => setTimeout(sync, 0));
    filter.addEventListener('input', () => {
      const term = normalize(filter.value.trim());
      let count = 0;
      tiles.forEach(tile => {
        tile.hidden = !normalize(tile.dataset.catalogSearch || '').includes(term);
        if (!tile.hidden) count += 1;
      });
      empty.hidden = count !== 0;
    });
    // Reveal the catalog only after setup succeeds; the select stays canonical.
    sync();
    controls.hidden = false;
    select.hidden = true;
    root.dataset.catalogReady = 'true';
  }

  function init() {
    document.querySelectorAll('[data-cosmetic-catalog]').forEach(enhance);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
