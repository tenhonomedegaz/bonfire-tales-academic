/* Static media only. The server validates manifest paths and ownership. */
(() => {
  'use strict';

  const seen = new Set();
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    for (const entry of entries) {
      entry.target.classList.toggle('is-visible', entry.isIntersecting);
    }
  }, { rootMargin: '80px' }) : null;

  function mount(root) {
    for (const layer of seen) {
      if (document.contains(layer)) continue;
      if (observer) observer.unobserve(layer);
      seen.delete(layer);
    }
    for (const layer of root.querySelectorAll('[data-cosmetic-layers]')) {
      if (seen.has(layer)) continue;
      seen.add(layer);
      layer.classList.toggle('is-paused', document.hidden);
      if (observer) observer.observe(layer);
      else layer.classList.add('is-visible');
    }
  }

  document.addEventListener('error', event => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.closest('[data-cosmetic-layers]')) return;
    const fallback = image.dataset.fallback;
    if (fallback && image.getAttribute('src') !== fallback) {
      image.src = fallback;
    } else {
      image.remove();
    }
  }, true);

  document.addEventListener('visibilitychange', () => {
    for (const layer of document.querySelectorAll('[data-cosmetic-layers]')) {
      layer.classList.toggle('is-paused', document.hidden);
    }
  });

  mount(document);
  const preview = document.getElementById('perfil-preview-stage');
  if (preview && 'MutationObserver' in window) {
    new MutationObserver(() => mount(preview)).observe(preview, { childList: true, subtree: true });
  }
})();
