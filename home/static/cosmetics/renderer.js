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
        if (!entry || !validRetraction(entry, slot)) continue;
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
        if (entry.parts) image.dataset.cosmeticParts = JSON.stringify(entry.parts);
        if (entry.mask_url) image.dataset.cosmeticMask = entry.mask_url;
        applyOpacity(image, entry);
        if (entry.motion === 'retract') {
          const viewport = document.createElement('span');
          viewport.className = 'cosmetic-retract-viewport';
          if (entry.retract_mask_url) {
            const mask = 'url(' + JSON.stringify(entry.retract_mask_url) + ')';
            viewport.style.maskImage = viewport.style.webkitMaskImage = mask;
          }
          for (const [key, unit] of Object.entries({x:'%', y:'%', rotate:'deg', duration:'ms', delay:'ms'})) {
            image.style.setProperty('--cosmetic-retract-' + key, entry.retract[key] + unit);
          }
          image.decoding = 'async';
          image.loading = 'lazy';
          viewport.appendChild(image);
          layer.appendChild(viewport);
          continue;
        }
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

  function validRetraction(entry, slot) {
    if (typeof entry !== 'object' || Array.isArray(entry)) return false;
    if (entry.motion !== 'retract') {
      return !['retract', 'retract_mask', 'retract_mask_url', 'retract_mask_style'].some(key => Object.hasOwn(entry, key));
    }
    const bounds = {x:[-100,100], y:[-100,100], rotate:[-45,45], duration:[100,1500], delay:[0,500]};
    const value = entry.retract;
    return slot === 'avatar' && entry.sprite === 'full' &&
      !['sequence', 'parts', 'placement', 'mobile', 'pivot', 'motion_params'].some(key => Object.hasOwn(entry, key)) &&
      value && typeof value === 'object' && !Array.isArray(value) &&
      Object.keys(value).length === 5 && Object.entries(bounds).every(([key, [low, high]]) =>
        Object.hasOwn(value, key) && typeof value[key] === 'number' && Number.isFinite(value[key]) &&
        value[key] >= low && value[key] <= high) &&
      (!Object.hasOwn(entry, 'retract_mask_url') ||
        (typeof entry.retract_mask_url === 'string' && entry.retract_mask_url.length > 0));
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

  function mountSequence(layer, image, parentGroup = null) {
    let seq;
    try { seq = JSON.parse(image.dataset.cosmeticSequence); } catch { image.remove(); return; }
    const finite = n => typeof n === 'number' && Number.isFinite(n);
    const rows = seq?.rows === undefined ? 1 : seq.rows;
    const width = Number(image.getAttribute('width'));
    const height = Number(image.getAttribute('height'));
    const poseBounds = {shift:[-25,25], x:[-100,100], y:[-100,100], rotate:[-15,15], scaleX:[.8,1.2], scaleY:[.8,1.2]};
    if (!Number.isInteger(seq?.columns) || seq.columns < 1 || seq.columns > 8 ||
        !Number.isInteger(rows) || rows < 1 || rows > 8 ||
        !finite(seq.duration) || seq.duration < 1 || seq.duration > 120 ||
        !finite(seq.delay) || seq.delay < -120 || seq.delay > 0 ||
        !finite(seq.backdrop) || seq.backdrop < 0 || seq.backdrop > .85 ||
        (parentGroup && seq.backdrop !== 0) ||
        !Array.isArray(seq.frames) || seq.frames.length < 4 || seq.frames.length > 64 ||
        !seq.frames.every((f, i) => f && finite(f.at) && f.at >= 0 && f.at <= 1 &&
          (!i || f.at > seq.frames[i - 1].at) && Number.isInteger(f.frame) &&
          f.frame >= 0 && f.frame < seq.columns * rows && finite(f.opacity) && f.opacity >= 0 && f.opacity <= 1 &&
          Object.entries(poseBounds).every(([key, [low, high]]) => f[key] === undefined ||
            (finite(f[key]) && f[key] >= low && f[key] <= high))) ||
        seq.frames[0].at !== 0 || seq.frames.at(-1).at !== 1 ||
        !Number.isInteger(width) || width < 32 || width > 4096 ||
        !Number.isInteger(height) || height < 32 || height > 4096) {
      image.remove(); return;
    }
    if (Object.hasOwn(seq, 'backdropFrames') &&
        (seq.backdrop <= 0 || !Array.isArray(seq.backdropFrames) ||
         seq.backdropFrames.length < 4 || seq.backdropFrames.length > 64 ||
         !seq.backdropFrames.every((f, i) => f && typeof f === 'object' && !Array.isArray(f) &&
           Object.keys(f).length === 2 && Object.hasOwn(f, 'at') && Object.hasOwn(f, 'opacity') &&
           finite(f.at) && f.at >= 0 && f.at <= 1 && (!i || f.at > seq.backdropFrames[i - 1].at) &&
           finite(f.opacity) && f.opacity >= 0 && f.opacity <= 1) ||
         seq.backdropFrames[0].at !== 0 || seq.backdropFrames.at(-1).at !== 1)) {
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
    viewport.style.aspectRatio = (width / seq.columns) + ' / ' + (height / rows);
    viewport.style.transformOrigin = 'var(--cosmetic-pivot-x,50%) var(--cosmetic-pivot-y,50%)';
    if (seq.columns === 1 && rows === 1 && image.dataset.cosmeticMask) {
      const maskImage = 'url(' + JSON.stringify(image.dataset.cosmeticMask) + ')';
      viewport.classList.add('cosmetic-atlas--masked');
      viewport.style.maskImage = maskImage;
      viewport.style.webkitMaskImage = maskImage;
      viewport.style.maskSize = viewport.style.webkitMaskSize = '100% 100%';
      viewport.style.maskRepeat = viewport.style.webkitMaskRepeat = 'no-repeat';
    }
    const opacityValue = image.style.getPropertyValue('--cosmetic-opacity');
    const opacity = opacityValue === '' ? 1 : Number(opacityValue);
    image.replaceWith(viewport);
    delete image.dataset.cosmeticSequence;
    image.className = 'cosmetic-atlas-image';
    image.style.width = (seq.columns * 100) + '%';
    image.style.height = (rows * 100) + '%';
    viewport.appendChild(image);
    const timing = {duration:seq.duration * 1000, delay:seq.delay * 1000, iterations:Infinity, fill:'both'};
    const animations = layer._cosmeticSequences || (layer._cosmeticSequences = []);
    const group = image._cosmeticSequenceGroup = {layer, viewport, animations:[], shade:null, children:[]};
    if (parentGroup) parentGroup.children.push(group);
    const schedule = (node, frames) => {
      const animation = node.animate(frames, timing);
      animations.push(animation);
      group.animations.push(animation);
    };
    // Individual pose properties compose with the existing CSS float transform.
    schedule(viewport, seq.frames.map(f => ({offset:f.at, opacity:f.opacity * opacity,
      translate:(f.x || 0) + '% ' + (f.y || 0) + '%', rotate:(f.rotate || 0) + 'deg',
      scale:(f.scaleX ?? 1) + ' ' + (f.scaleY ?? 1)})));
    schedule(image, seq.frames.map(f => ({offset:f.at,
      transform:'translate(' + ((-100 * (f.frame % seq.columns) + (f.shift || 0)) / seq.columns) + '%,' +
        (-100 * Math.floor(f.frame / seq.columns) / rows) + '%)', easing:'steps(1, end)'})));
    if (seq.backdrop) {
      const shade = document.createElement('span');
      shade.className = 'cosmetic-sequence-shade';
      group.shade = shade;
      layer.prepend(shade);
      schedule(shade, (seq.backdropFrames || seq.frames).map(f => ({offset:f.at, opacity:f.opacity * seq.backdrop})));
    }
    if (!parentGroup && seq.columns === 1 && rows === 1 && image.dataset.cosmeticParts) {
      let parts;
      try { parts = JSON.parse(image.dataset.cosmeticParts); } catch { parts = null; }
      delete image.dataset.cosmeticParts;
      if (Array.isArray(parts) && parts.length >= 1 && parts.length <= 6) {
        viewport.classList.add('cosmetic-atlas--rig');
        for (const part of parts) {
          if (!part || part.parts || !part.placement || !part.sequence || part.sequence.backdrop !== 0) continue;
          const positioned = document.createElement('span');
          positioned.className = 'cosmetic-positioned cosmetic-part';
          positioned.classList.toggle('cosmetic-part--mobile', Boolean(part.mobile));
          for (const [layout, prefix] of [[part.placement, ''], [part.mobile, 'mobile-'], [part.pivot, 'pivot-']]) {
            if (!layout) continue;
            for (const key of ['x', 'y', 'width']) {
              if (finite(layout[key])) positioned.style.setProperty('--cosmetic-' + prefix + key, layout[key] + '%');
            }
          }
          const child = document.createElement('img');
          child.className = 'cosmetic-layer cosmetic-layer--' + part.motion;
          child.src = part.url;
          child.dataset.fallback = part.fallback;
          child.dataset.cosmeticSequence = JSON.stringify(part.sequence);
          if (part.mask_url) child.dataset.cosmeticMask = part.mask_url;
          child.width = part.width;
          child.height = part.height;
          child.alt = '';
          applyOpacity(child, part);
          positioned.appendChild(child);
          viewport.appendChild(positioned);
          mountSequence(layer, child, group);
        }
      }
    }
  }
  function removeSequence(group) {
    for (const child of group.children) removeSequence(child);
    for (const animation of group.animations) animation.cancel();
    group.layer._cosmeticSequences = group.layer._cosmeticSequences.filter(a => !group.animations.includes(a));
    group.shade?.remove();
    group.viewport.remove();
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
      if (group) removeSequence(group);
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
