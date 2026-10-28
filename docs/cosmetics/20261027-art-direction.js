document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const config = JSON.parse(document.getElementById('moon-config').textContent);
  const snapshots = window.BonfireMoonPreviews || {};
  const status = document.getElementById('preview-status');
  const localBanner = document.getElementById('local-banner');
  const bannerImages = [...document.querySelectorAll('.moon-hero > .hero-banner')];
  const originalBanner = bannerImages[0].getAttribute('src');
  let objectURL = null;
  const notice = message => { status.textContent = message; status.hidden = !message; };

  function roleFor(filename, family) {
    return Object.keys(config.roles).find(role => filename.startsWith(family + '-' + role + '-v'));
  }
  function toggleAsset(hero, family, role, visible) {
    for (const image of hero.querySelectorAll('[data-cosmetic-layers] img')) {
      const filename = new URL(image.src, location.href).pathname.split('/').pop();
      if (roleFor(filename, family) === role) {
        image.dataset.previewRole = role;
        image.style.visibility = visible ? '' : 'hidden';
      }
    }
  }

  for (const [key, family] of Object.entries(config.families)) {
    const hero = document.querySelector('[data-moon-hero="' + key + '"]');
    const controls = document.querySelector('[data-layer-controls="' + key + '"]');
    const state = document.querySelector('[data-theme-status="' + key + '"]');
    const pack = snapshots[key];
    const ready = pack?.overlay === true && Array.isArray(pack.banner) && pack.banner.length > 0 &&
      typeof window.CosmeticRenderer?.render === 'function';
    if (ready) {
      window.CosmeticRenderer.render(hero, 'banner', [pack]);
      for (const image of hero.querySelectorAll('[data-cosmetic-layers] img')) {
        const role = roleFor(new URL(image.src, location.href).pathname.split('/').pop(), family.family);
        if (role) image.dataset.previewRole = role;
      }
    } else {
      state.hidden = false;
      state.textContent = 'Aguardando snapshot dos manifests transparentes.';
    }
    for (const [role, label] of Object.entries(config.roles)) {
      const option = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = true;
      checkbox.disabled = !ready;
      checkbox.dataset.moon = key;
      checkbox.dataset.layerToggle = role;
      checkbox.addEventListener('change', () => toggleAsset(hero, family.family, role, checkbox.checked));
      option.append(checkbox, document.createTextNode(label));
      controls.appendChild(option);
    }

    const group = document.createElement('section');
    group.className = 'asset-group';
    const title = document.createElement('h3');
    title.textContent = family.label;
    const grid = document.createElement('div');
    grid.className = 'asset-grid';
    const unique = new Map((pack?.banner || []).map(layer => [layer.file, layer]));
    for (const [filename, layer] of unique) {
      const role = roleFor(filename, family.family);
      if (!role) continue;
      const figure = document.createElement('figure');
      const link = document.createElement('a');
      link.href = layer.fallback;
      const image = document.createElement('img');
      image.src = layer.url;
      image.alt = config.roles[role] + ' · ' + family.label;
      image.loading = 'lazy';
      const caption = document.createElement('figcaption');
      caption.textContent = config.roles[role] + ' · ' + filename;
      link.appendChild(image);
      figure.append(link, caption);
      grid.appendChild(figure);
    }
    group.append(title, grid);
    document.getElementById('asset-groups').appendChild(group);
  }

  document.getElementById('toggle-wind').addEventListener('click', event => {
    const paused = event.currentTarget.getAttribute('aria-pressed') !== 'true';
    event.currentTarget.setAttribute('aria-pressed', String(paused));
    event.currentTarget.textContent = paused ? 'Retomar vento' : 'Pausar vento';
    document.documentElement.classList.toggle('preview-paused', paused);
  });
  function replaceBanner(url) {
    for (const image of bannerImages) image.src = url;
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = url.startsWith('blob:') ? url : null;
  }
  localBanner.addEventListener('change', () => {
    const file = localBanner.files[0];
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type) || file.size > 20 * 1024 * 1024) {
      notice('Escolha uma imagem PNG, JPEG, WebP ou GIF de até 20 MB.');
      localBanner.value = '';
      return;
    }
    replaceBanner(URL.createObjectURL(file));
    notice('Banner local: ' + file.name);
  });
  document.getElementById('banner-reset').addEventListener('click', () => {
    replaceBanner(originalBanner);
    localBanner.value = '';
    notice('');
  });
  window.addEventListener('pagehide', () => { if (objectURL) URL.revokeObjectURL(objectURL); });
});
