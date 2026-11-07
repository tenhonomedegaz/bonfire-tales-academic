/* Cards retain the existing select/AJAX contract and a native GET fallback. */
(() => {
  'use strict';
  for (const image of document.querySelectorAll('[data-market-payer-avatar]')) {
    image.addEventListener('error', () => { image.hidden = true; }, {once: true});
    if (image.complete && !image.naturalWidth) image.hidden = true;
  }
  for (const fieldset of document.querySelectorAll('[data-market-characters]')) {
    if (fieldset.dataset.ready) continue;
    const form = fieldset.closest('form');
    const select = form.querySelector('[data-shop-personagem]');
    if (!select) continue;
    fieldset.dataset.ready = 'true';
    const radios = [...fieldset.querySelectorAll('[data-market-character]')];
    select.disabled = true;
    form.querySelector('[data-character-fallback]').hidden = true;
    for (const radio of radios) radio.disabled = false;
    fieldset.hidden = false;
    fieldset.addEventListener('change', event => {
      if (!event.target.matches('[data-market-character]')) return;
      select.value = event.target.value;
      select.dispatchEvent(new Event('change', {bubbles: true}));
    });
    const shop = form.closest('[data-shop-root]');
    if (!shop) continue;
    const sync = () => {
      for (const radio of radios) radio.checked = radio.value === select.value;
      const active = radios.find(radio => radio.checked);
      const wallet = shop.querySelector('[data-shop-carteira]');
      if (active && wallet) active.closest('label').querySelector('[data-market-character-label] small').textContent = wallet.textContent.trim();
    };
    shop.addEventListener('shop:character-changed', sync);
    shop.addEventListener('shop:character-change-failed', sync);
    shop.addEventListener('shop:wallet-changed', sync);
  }
})();
