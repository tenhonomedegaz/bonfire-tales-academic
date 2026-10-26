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
      const owner = layer.parentElement;
      if (layer.dataset.apertureX) {
        owner.classList.add('has-calibrated-portrait');
        for (const [property, value] of [['x', layer.dataset.apertureX], ['y', layer.dataset.apertureY], ['size', layer.dataset.apertureSize]]) {
          const number = Number(value);
          if (Number.isFinite(number) && number > 0 && number < 100) {
            owner.style.setProperty('--portrait-' + property, (property === 'size' ? number * 1.32 : -16 + number * 1.32) + '%');
          }
        }
      }
      layer.classList.toggle('is-paused', document.hidden);
      if (observer) observer.observe(layer);
      else layer.classList.add('is-visible');
    }
  }

  function render(root, slot, packages) {
    if (!root || !['banner', 'ornament', 'avatar'].includes(slot)) return;
    if (slot === 'avatar') {
      root.classList.remove('has-calibrated-portrait');
      for (const key of ['x', 'y', 'size']) root.style.removeProperty('--portrait-' + key);
    }
    root.querySelectorAll(':scope > [data-cosmetic-layers]').forEach(layer => {
      if (layer.classList.contains('cosmetic-layers--' + slot)) layer.remove();
    });
    for (const pack of packages) {
      if (!Array.isArray(pack?.[slot]) || !pack[slot].length) continue;
      const layer = document.createElement('div');
      layer.className = 'cosmetic-layers cosmetic-layers--' + slot;
      layer.dataset.cosmeticLayers = '';
      layer.setAttribute('aria-hidden', 'true');
      for (const entry of pack[slot]) {
        if (entry.aperture) {
          layer.dataset.apertureX = entry.aperture.cx;
          layer.dataset.apertureY = entry.aperture.cy;
          layer.dataset.apertureSize = entry.aperture.diameter;
        }
        if (entry.motion === 'helmet') {
          const helmet = document.createElement('span');
          helmet.className = 'cosmetic-layer cosmetic-helmet';
          helmet.dataset.cosmeticHelmet = '';
          for (const [sprite,part] of [['open','open'],['closed','brow'],['closed','left'],['closed','right'],['closed','chin']]) {
            helmet.appendChild(spriteNode(entry,sprite,'cosmetic-helmet-' + part));
          }
          layer.appendChild(helmet);
          continue;
        }
        if (['open','closed'].includes(entry.sprite)) {
          const sprite = spriteNode(entry,entry.sprite,'cosmetic-layer');
          layer.appendChild(sprite);
          continue;
        }
        const image = document.createElement('img');
        image.className = 'cosmetic-layer cosmetic-layer--' + entry.anchor + ' cosmetic-layer--' + entry.motion;
        image.src = entry.url;
        image.dataset.fallback = entry.fallback;
        image.alt = '';
        image.width = entry.width;
        image.height = entry.height;
        layer.appendChild(image);
      }
      root.appendChild(layer);
    }
    mount(root);
  }

  function spriteNode(entry, sprite, extraClass) {
    const node = document.createElement('span');
    node.className = 'cosmetic-sprite cosmetic-sprite--' + sprite + ' ' + extraClass;
    const image = document.createElement('img');
    image.src = entry.url;
    image.dataset.fallback = entry.fallback;
    image.alt = '';
    image.decoding = 'async';
    node.appendChild(image);
    return node;
  }
  window.CosmeticRenderer = { render, mount };

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
