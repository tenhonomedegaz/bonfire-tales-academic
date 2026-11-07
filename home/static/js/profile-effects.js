/* Decorative only: independent of CosmeticRenderer and persisted cosmetics. */
(() => {
  'use strict';
  if (window.__bonfireProfileEffects) return;
  window.__bonfireProfileEffects = true;

  const targets = '.profile-header.profile-hero, .public-profile-card, .ficha-header, .cosmetic-effect-sample';
  const roots = '.profile-page, .public-profile-page, .ficha';
  const effects = ['soft-glow', 'glass', 'embers', 'aurora', 'starfall'];
  const motifs = new Set(['facets', 'runes', 'sun', 'leaves', 'flames',
    'thorns', 'crystal', 'moon', 'eclipse', 'bats']);
  const legacyMotifs = {bonfire: 'flames', arcane: 'runes', verdant: 'leaves', moonlit: 'moon'};
  const layerClass = 'profile-effect-layer';
  const sceneClass = 'profile-theme-scene';
  let scheduled = false;

  function effectFor(target) {
    const owner = target.matches('.cosmetic-effect-sample') ? target : target.closest(roots);
    if (!owner || owner.classList.contains('effect-none')) return 'none';
    return effects.find(effect => owner.classList.contains(`effect-${effect}`)) || 'none';
  }

  function render(target) {
    const effect = effectFor(target);
    const layers = Array.from(target.children).filter(child => child.classList.contains(layerClass));
    if (target.dataset.profileEffect === effect &&
        (effect === 'none' ? layers.length === 0 : layers.length === 1)) return;
    layers.forEach(layer => layer.remove());
    target.dataset.profileEffect = effect;
    if (effect === 'none') return;

    const layer = document.createElement('span');
    layer.className = layerClass;
    layer.setAttribute('aria-hidden', 'true');
    const count = {embers: 12, starfall: 3, 'soft-glow': 4, aurora: 4}[effect] || 2;
    for (let index = 0; index < count; index += 1) {
      const mark = document.createElement('span');
      mark.className = 'profile-effect-mark';
      mark.style.setProperty('--pe-index', index);
      mark.style.setProperty('--pe-x', `${3 + (index * 29) % 94}%`);
      mark.style.setProperty('--pe-delay', `${-index * 1.73}s`);
      layer.appendChild(mark);
    }
    target.appendChild(layer);
  }

  function renderTheme(target) {
    if (target.matches('.cosmetic-effect-sample')) return;
    const owner = target.closest(roots);
    let motif = owner?.dataset.themeMotif;
    const paletteOnly = owner?.dataset.themeCategory === 'classico' || owner?.classList.contains('skin-illustrated');
    if (paletteOnly) motif = 'none';
    // Legacy palettes receive the same compositions as their data-driven equivalents.
    if ((!motif || motif === 'none') && !paletteOnly) {
      const legacy = Object.keys(legacyMotifs).find(key => owner?.classList.contains(`theme-${key}`));
      motif = legacy ? legacyMotifs[legacy] : 'none';
    }
    if (!motifs.has(motif)) motif = 'none';
    const scenes = Array.from(target.children).filter(child => child.classList.contains(sceneClass));
    if (target.dataset.profileMotif === motif &&
        (motif === 'none' ? scenes.length === 0 : scenes.length === 1)) return;
    scenes.forEach(scene => scene.remove());
    target.dataset.profileMotif = motif;
    if (motif === 'none') return;
    const scene = document.createElement('span');
    scene.className = sceneClass;
    scene.setAttribute('aria-hidden', 'true');
    for (const part of ['emblem', 'fringe']) {
      const node = document.createElement('span');
      node.className = `profile-theme-${part}`;
      scene.appendChild(node);
    }
    for (let index = 0; index < 3; index += 1) {
      const mote = document.createElement('span');
      mote.className = 'profile-theme-mote';
      mote.style.setProperty('--motif-index', index);
      scene.appendChild(mote);
    }
    target.appendChild(scene);
  }

  function refresh() {
    scheduled = false;
    document.querySelectorAll(targets).forEach(target => {
      render(target);
      renderTheme(target);
    });
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(refresh);
  }

  function isDecoration(node) {
    return node.nodeType === 1 && (node.classList.contains(layerClass) ||
      node.classList.contains(sceneClass) || Boolean(node.closest(`.${layerClass}, .${sceneClass}`)));
  }

  function start() {
    const visibility = () => {
      document.documentElement.toggleAttribute('data-profile-effects-paused', document.hidden);
      if (!document.hidden) schedule();
    };
    visibility();
    refresh();
    // Ignore our own overlay insertion/removal; observe classes, never our data/style writes.
    const observer = new MutationObserver(records => {
      if (records.some(record => {
        if (isDecoration(record.target)) return false;
        if (record.type === 'attributes') return true;
        return [...record.addedNodes, ...record.removedNodes].some(node =>
          node.nodeType === 1 && !isDecoration(node));
      })) schedule();
    });
    observer.observe(document.body, {subtree: true, childList: true,
      attributes: true, attributeFilter: ['class', 'data-theme-motif']});
    document.addEventListener('visibilitychange', visibility);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }
})();
