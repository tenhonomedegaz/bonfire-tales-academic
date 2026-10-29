/* Static media only. The server validates manifest paths and ownership. */
(() => {
  'use strict';

  const seen = new Set();
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  function syncSequences(layer) {
    const paused = document.hidden || reducedMotion.matches ||
      !layer.classList.contains('is-visible') || layer.classList.contains('is-paused') ||
      Boolean(layer.closest('.preview-paused'));
    for (const animation of layer._cosmeticSequences || []) {
      if (paused) animation.pause();
      else animation.play();
    }
  }
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    for (const entry of entries) {
      entry.target.classList.toggle('is-visible', entry.isIntersecting);
      syncSequences(entry.target);
    }
  }, { rootMargin: '80px' }) : null;

  function mount(root) {
    for (const layer of seen) {
      if (document.contains(layer)) continue;
      if (observer) observer.unobserve(layer);
      for (const animation of layer._cosmeticSequences || []) animation.cancel();
      seen.delete(layer);
    }
    for (const layer of root.querySelectorAll('[data-cosmetic-layers]')) {
      if (seen.has(layer)) continue;
      seen.add(layer);
      const owner = layer.parentElement;
      for (const image of layer.querySelectorAll('img[data-cosmetic-sequence]')) mountSequence(layer, image);
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
      syncSequences(layer);
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
        if (entry.sequence) image.dataset.cosmeticSequence = JSON.stringify(entry.sequence);
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

  function mountSequence(layer, image) {
    let seq;
    try { seq = JSON.parse(image.dataset.cosmeticSequence); } catch { image.remove(); return; }
    const finite = n => typeof n === 'number' && Number.isFinite(n);
    if (!Number.isInteger(seq?.columns) || seq.columns < 2 || seq.columns > 8 ||
        !finite(seq.duration) || seq.duration < 1 || seq.duration > 120 ||
        !finite(seq.delay) || seq.delay < -120 || seq.delay > 0 ||
        !finite(seq.backdrop) || seq.backdrop < 0 || seq.backdrop > .85 ||
        !Array.isArray(seq.frames) || seq.frames.length < 4 || seq.frames.length > 24 ||
        !seq.frames.every((f, i) => finite(f.at) && f.at >= 0 && f.at <= 1 &&
          (!i || f.at > seq.frames[i - 1].at) && Number.isInteger(f.frame) &&
          f.frame >= 0 && f.frame < seq.columns && finite(f.opacity) && f.opacity >= 0 && f.opacity <= 1 &&
          (f.shift === undefined || (finite(f.shift) && f.shift >= -25 && f.shift <= 25))) ||
        seq.frames[0].at !== 0 || seq.frames.at(-1).at !== 1 || !image.width || !image.height) {
      image.remove(); return;
    }
    const viewport = document.createElement('span');
    viewport.className = 'cosmetic-layer cosmetic-atlas';
    viewport.classList.toggle('cosmetic-atlas--ambient', seq.backdrop === 0 && seq.frames.every(f => f.opacity > 0));
    if (image.classList.contains('cosmetic-layer--float')) {
      viewport.classList.add('cosmetic-layer--float');
      viewport.style.setProperty('--cosmetic-float-duration', (seq.duration * 4) + 's');
      viewport.style.setProperty('--cosmetic-float-delay', seq.delay + 's');
    }
    viewport.style.aspectRatio = (image.width / seq.columns) + ' / ' + image.height;
    const opacityValue = image.style.getPropertyValue('--cosmetic-opacity');
    const opacity = opacityValue === '' ? 1 : Number(opacityValue);
    image.replaceWith(viewport);
    delete image.dataset.cosmeticSequence;
    image.className = 'cosmetic-atlas-image';
    image.style.width = (seq.columns * 100) + '%';
    viewport.appendChild(image);
    const timing = {duration:seq.duration * 1000, delay:seq.delay * 1000, iterations:Infinity, fill:'both'};
    const animations = layer._cosmeticSequences || (layer._cosmeticSequences = []);
    const group = image._cosmeticSequenceGroup = {layer, viewport, animations:[], shade:null};
    const schedule = (node, frames) => {
      const animation = node.animate(frames, timing);
      animations.push(animation);
      group.animations.push(animation);
    };
    schedule(viewport, seq.frames.map(f => ({offset:f.at, opacity:f.opacity * opacity})));
    schedule(image, seq.frames.map(f => ({offset:f.at,
      transform:'translateX(' + ((-100 * f.frame + (f.shift || 0)) / seq.columns) + '%)', easing:'steps(1, end)'})));
    if (seq.backdrop) {
      const shade = document.createElement('span');
      shade.className = 'cosmetic-sequence-shade';
      group.shade = shade;
      layer.prepend(shade);
      schedule(shade, seq.frames.map(f => ({offset:f.at, opacity:f.opacity * seq.backdrop})));
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
      const group = image._cosmeticSequenceGroup;
      if (group) {
        for (const animation of group.animations) animation.cancel();
        group.layer._cosmeticSequences = group.layer._cosmeticSequences.filter(a => !group.animations.includes(a));
        group.shade?.remove();
        group.viewport.remove();
      }
      image.remove();
    }
  }, true);

  document.addEventListener('visibilitychange', () => {
    for (const layer of document.querySelectorAll('[data-cosmetic-layers]')) {
      layer.classList.toggle('is-paused', document.hidden);
      syncSequences(layer);
    }
  });
  reducedMotion.addEventListener('change', () => {
    for (const layer of seen) syncSequences(layer);
  });

  mount(document);
  const preview = document.getElementById('perfil-preview-stage');
  if (preview && 'MutationObserver' in window) {
    new MutationObserver(() => mount(preview)).observe(preview, { childList: true, subtree: true });
  }
})();
