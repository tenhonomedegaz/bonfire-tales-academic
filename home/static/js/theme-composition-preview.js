/* Appearance-only enhancement. No save, purchase, fetch or entitlement changes. */
(() => {
  'use strict';
  const keys = ['forja-de-brasas', 'aurora-glacial', 'circulo-arcano'];
  document.addEventListener('change', event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== 'radio') return;
    const selector = input.name === 'ficha_theme' ? '.ficha' : input.name === 'profile_theme' ? '.public-profile-page.is-preview' : '';
    if (!selector) return;
    document.querySelectorAll(selector).forEach(root => {
      keys.forEach(key => root.classList.remove('collection-' + key));
      if (keys.includes(input.value)) root.classList.add('collection-' + input.value);
    });
  });
})();
