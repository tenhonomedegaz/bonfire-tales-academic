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
      for (const image of layer.querySelectorAll('img.cosmetic-layer--breeze')) {
        const breeze = document.createElement('span');
        breeze.className = 'cosmetic-breeze';
        image.replaceWith(breeze);
        image.classList.remove('cosmetic-layer--breeze');
        image.classList.add('cosmetic-breeze-base');
        breeze.appendChild(image);
        for (const name of ['clouds', 'branches']) {
          const copy = image.cloneNode(true);
          copy.className = 'cosmetic-layer cosmetic-layer--' +
            (image.classList.contains('cosmetic-layer--right') ? 'right' :
             image.classList.contains('cosmetic-layer--left') ? 'left' : 'center') +
            ' cosmetic-breeze-' + name;
          breeze.appendChild(copy);
        }
      }
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
      layer.classList.toggle('cosmetic-layers--overlay', pack.overlay === true);
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
          applyOpacity(helmet, entry);
          helmet.dataset.cosmeticHelmet = '';
          for (const [sprite,part] of [['open','open'],['closed','brow'],['closed','left'],['closed','right'],['closed','chin']]) {
            helmet.appendChild(spriteNode(entry,sprite,'cosmetic-helmet-' + part));
          }
          layer.appendChild(helmet);
          continue;
        }
        if (['open','closed'].includes(entry.sprite)) {
          const sprite = spriteNode(entry,entry.sprite,'cosmetic-layer');
          applyOpacity(sprite, entry);
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
        applyOpacity(image, entry);
        if (entry.placement && slot === 'banner') {
          const positioned = document.createElement('span');
          positioned.className = 'cosmetic-positioned';
          for (const key of ['x', 'y']) {
            const value = entry.pivot?.[key];
            if (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100) {
              positioned.style.setProperty('--cosmetic-pivot-' + key, value + '%');
            }
          }
          for (const [layout, prefix] of [[entry.placement, ''], [entry.mobile, 'mobile-']]) {
            if (!layout) continue;
            for (const key of ['x', 'y', 'width']) {
              if (typeof layout[key] === 'number' && Number.isFinite(layout[key])) {
                positioned.style.setProperty('--cosmetic-' + prefix + key, layout[key] + '%');
              }
            }
          }
          for (const [key, value] of Object.entries(entry.motion_params || {})) {
            if (['distance', 'duration', 'delay'].includes(key) && typeof value === 'number' && Number.isFinite(value)) {
              positioned.style.setProperty('--cosmetic-drift-' + key, value + (key === 'distance' ? '%' : 's'));
            }
          }
          positioned.appendChild(image);
          layer.appendChild(positioned);
        } else {
          layer.appendChild(image);
        }
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
  function applyOpacity(node, entry) {
    if (typeof entry.opacity === 'number' && Number.isFinite(entry.opacity) && entry.opacity >= 0 && entry.opacity <= 1) {
      node.style.setProperty('--cosmetic-opacity', entry.opacity);
    }
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
