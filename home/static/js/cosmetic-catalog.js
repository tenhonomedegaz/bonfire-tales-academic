(() => {
  'use strict';
  const cache = new Map();
  const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  function safeURL(value, kind = 'link') {
    if (typeof value !== 'string' || !value || value.length > 4096) return '';
    try {
      const url = new URL(value, location.href);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return '';
      if (kind === 'local' && url.origin !== location.origin) return '';
      if (kind === 'css' && (url.origin !== location.origin || !['/static/','/media/'].some(prefix=>url.pathname.startsWith(prefix)) || !url.pathname.endsWith('.css'))) return '';
      if (kind === 'link' && url.origin !== location.origin && !['discord.gg', 'discord.com'].includes(url.hostname)) return '';
      return url.href;
    } catch { return ''; }
  }
  const tokens = value => typeof value === 'string' ? value.split(/\s+/).filter(token => /^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(token)) : [];
  function theme(root, payload, form) {
    root.dataset.themeCategory = payload.theme_category === 'especial' ? 'especial' : 'classico';
    for (const name of [...root.classList]) {
      if (/^(theme-|collection-|skin-)/.test(name)) root.classList.remove(name);
    }
    const definition = payload.theme_definition || {};
    const data = { chave: payload.key, classe: tokens(payload.css_class).join(' ') };
    for (const key of ['accent', 'accent2', 'surface', 'deep']) {
      const custom = payload.key === 'custom' && form?.querySelector('[name="custom_' + key + '"]');
      const value = custom ? custom.value : definition[key];
      data[key] = typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value) ? value : '';
    }
    data.gradiente = payload.key === 'custom' ? !!form?.querySelector('[name="custom_gradiente"]')?.checked : definition.gradiente === true;
    data.motif = ['none','facets','runes','sun','leaves','flames','thorns','crystal','moon','eclipse','bats'].includes(definition.motif) ? definition.motif : 'none';
    data.particula = ['subir','cair','flutuar','nenhuma'].includes(definition.particula) ? definition.particula : '';
    data.vel = ['lenta','media','rapida'].includes(definition.vel) ? definition.vel : 'media';
    if (window.TemaSwatch) window.TemaSwatch.aplica(root, data);
    else {
      root.classList.add(...tokens(data.classe));
      for (const [key, property] of Object.entries({accent:'accent',accent2:'accent-2',surface:'surface',deep:'deep'})) {
        if (data[key]) root.style.setProperty('--profile-' + property, data[key]);
      }
    }
  }
  function cleanup(stage) {
    for (const animation of stage.getAnimations?.({subtree: true}) || []) animation.cancel();
    stage.replaceChildren();
    window.CosmeticRenderer?.mount(stage);
  }
  function enhance(root) {
    if (root.dataset.catalogReady) return;
    const find = selector => root.querySelector(selector);
    const select = find('[data-catalog-select]');
    const dialog = find('[data-catalog-dialog]');
    const launcher = find('[data-catalog-open]');
    if (!select || !dialog?.showModal || !launcher) return;
    const tiles = [...root.querySelectorAll('[data-catalog-tile]')];
    const filter = find('[data-catalog-filter]');
    const stage = find('[data-catalog-preview]');
    const apply = find('[data-catalog-apply]');
    const status = find('[data-catalog-status]');
    const acquisition = find('[data-catalog-acquisition]');
    const retry = find('[data-catalog-retry]');
    const originallyLocked = new Set([...select.options].filter(option => option.disabled).map(option => option.value));
    let committed = select.value;
    let candidate = null;
    let response = null;
    let controller = null;
    let sequence = 0;
    let category = 'classico';
    let css = null;
    const blobs = [];
    const optionFor = key => [...select.options].find(option => option.value === key);
    const allowed = key => !select.disabled && !!optionFor(key) && !optionFor(key).disabled && !originallyLocked.has(key);
    function clearPreview() {
      cleanup(stage);
      css?.remove(); css = null;
      blobs.splice(0).forEach(url => URL.revokeObjectURL(url));
    }
    function sync() {
      if (select.value !== committed && !allowed(select.value)) select.value = committed;
      else committed = select.value;
      const tile = tiles.find(item => item.dataset.catalogKey === committed);
      find('[data-catalog-selected-name]').textContent = tile?.dataset.catalogLabel || optionFor(committed)?.textContent || '';
      launcher.title = tile?.dataset.catalogLabel || optionFor(committed)?.textContent || '';
      const art = find('[data-catalog-selected-art]');
      art.replaceChildren();
      const source = safeURL(tile?.querySelector('img')?.getAttribute('src'), 'image');
      if (source) { const img = document.createElement('img'); img.src = source; img.alt = ''; img.width = img.height = 48; art.appendChild(img); }
      else art.textContent = '◇';
      launcher.disabled = select.disabled;
    }
    function filterTiles() {
      const term = normalize(filter.value.trim());
      for (const tile of tiles) tile.hidden = !normalize(tile.dataset.catalogSearch).includes(term) || (root.dataset.catalogType === 'tema' && tile.dataset.catalogItemCategory !== category);
      const visible = tiles.filter(tile => !tile.hidden);
      find('[data-catalog-empty]').hidden = visible.length > 0;
      const active = visible.includes(candidate) ? candidate : visible[0];
      tiles.forEach(tile => tile.tabIndex = tile === active ? 0 : -1);
      root.querySelectorAll('[data-catalog-category]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.catalogCategory === category)));
    }
    function localImage(slot) {
      const form = select.form;
      if (form?.querySelector('[name="clear_' + slot + '"]')?.checked) return '';
      const file = form?.querySelector('[name="' + slot + '_file"]')?.files?.[0];
      if (file && /^image\/(png|jpeg|webp|gif)$/.test(file.type)) {
        const url = URL.createObjectURL(file); blobs.push(url); return url;
      }
      const input = form?.querySelector('[name="' + slot + '_url"]');
      const fallback = slot === 'avatar' ? document.querySelector('#profile-avatar-main > img, #avatar-preview-img, .banner-character-avatar > img')?.getAttribute('src') : '';
      return safeURL(input?.value || fallback, 'image');
    }
    function buildPreview(payload) {
      clearPreview();
      const page = document.createElement('div'); page.className = 'public-profile-page is-preview';
      const current = document.getElementById('profile-root');
      if (current) {
        page.dataset.themeCategory = current.dataset.themeCategory === 'especial' ? 'especial' : 'classico';
        page.classList.add(...[...current.classList].filter(name => /^(theme-|collection-|skin-)/.test(name)));
        for (const name of ['accent','accent-solid','accent-2','surface','deep']) {
          const value = current.style.getPropertyValue('--profile-' + name);
          if (value) page.style.setProperty('--profile-' + name, value);
        }
      }
      const card = document.createElement('div'); card.className = 'public-profile-card';
      const banner = document.createElement('div'); banner.className = 'public-profile-banner';
      const avatar = document.createElement('div'); avatar.className = 'public-profile-avatar';
      const identity = document.createElement('div'); identity.className = 'cosmetic-preview-identity';
      const name = select.form?.querySelector('[name="username"], [name="nome"]')?.value || document.querySelector('.profile-username, .ficha-name')?.textContent?.trim() || 'Bonfire';
      const title = document.createElement('strong'); title.textContent = name;
      const bio = document.createElement('p'); bio.textContent = select.form?.querySelector('[name="bio"]')?.value || '';
      identity.append(title, bio);
      for (const [slot, host] of [['avatar', avatar], ['banner', banner]]) {
        const src = localImage(slot);
        if (src) { const image = document.createElement('img'); image.src = src; image.alt = ''; if (slot === 'banner') image.className = 'public-profile-banner-media'; host.appendChild(image); }
        else if (slot === 'avatar') host.textContent = name.slice(0, 1).toUpperCase();
      }
      card.append(banner, avatar, identity); page.appendChild(card); stage.appendChild(page);
      if (payload.tipo === 'tema') theme(page, payload, select.form);
      else (payload.tipo === 'moldura' ? avatar : page).classList.add(...tokens(payload.css_class));
      const href = safeURL(payload.theme_css_url, 'css');
      if (href && payload.tipo === 'tema') { css = document.createElement('link'); css.rel = 'stylesheet'; css.href = href; document.head.appendChild(css); }
      const pack = payload.package;
      if (pack && typeof pack === 'object' && window.CosmeticRenderer) {
        if (pack.avatar?.length) avatar.classList.add('is-packaged');
        window.CosmeticRenderer.render(avatar, 'avatar', [pack]);
        window.CosmeticRenderer.render(banner, 'banner', [pack]);
        window.CosmeticRenderer.render(banner, 'ornament', [pack]);
      }
    }
    async function choose(tile, force = false) {
      if (!dialog.open || (!force && candidate === tile && (response || controller))) return;
      candidate = tile; response = null;
      const key = tile.dataset.catalogKey;
      const request = ++sequence;
      controller?.abort(); controller = null;
      clearPreview();
      tiles.forEach(item => { item.setAttribute('aria-selected', String(item === tile)); item.tabIndex = item === tile ? 0 : -1; });
      find('[data-catalog-name]').textContent = tile.dataset.catalogLabel;
      find('[data-catalog-description]').textContent = '';
      find('[data-catalog-hint-text]').textContent = tile.dataset.catalogHint || tile.dataset.catalogOrigin || '';
      acquisition.hidden = true; acquisition.removeAttribute('href'); apply.disabled = true; retry.hidden = true;
      status.textContent = 'Carregando…'; stage.setAttribute('aria-busy', 'true');
      const endpoint = safeURL(root.dataset.catalogUrl, 'local');
      try {
        if (!endpoint) throw new Error('missing endpoint');
        const url = new URL(endpoint);
        url.searchParams.set('tipo', root.dataset.catalogType); url.searchParams.set('key', key); url.searchParams.set('escopo', root.dataset.catalogScope);
        const cacheKey = url.href;
        let payload = cache.get(cacheKey);
        if (!payload) {
          controller = new AbortController();
          const result = await fetch(url.href, {signal: controller.signal, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
          if (!result.ok) throw new Error('preview failed');
          payload = await result.json();
          if (!payload || payload.key !== key || payload.tipo !== root.dataset.catalogType) throw new Error('mismatched candidate');
          cache.set(cacheKey, payload);
          if (cache.size > 24) cache.delete(cache.keys().next().value);
        }
        if (request !== sequence || !dialog.open) return;
        response = payload;
        find('[data-catalog-name]').textContent = payload.label || tile.dataset.catalogLabel;
        find('[data-catalog-description]').textContent = typeof payload.description === 'string' ? payload.description : '';
        find('[data-catalog-hint-text]').textContent = payload.unlock_hint || tile.dataset.catalogOrigin || (payload.locked ? 'Bloqueado' : 'Disponível');
        const href = safeURL(payload.acquisition?.url);
        if (href && payload.locked === true) { acquisition.href = href; acquisition.textContent = payload.acquisition.label || 'Como obter'; acquisition.hidden = false; }
        buildPreview(payload);
        apply.disabled = !allowed(key) || payload.locked !== false;
        status.textContent = '';
      } catch (error) {
        if (request !== sequence || !dialog.open || error.name === 'AbortError') return;
        status.textContent = 'Prévia indisponível.'; retry.hidden = false;
      } finally {
        if (request === sequence) { controller = null; stage.removeAttribute('aria-busy'); }
      }
    }
    function stopPreview() {
      ++sequence; controller?.abort(); controller = null; response = null; candidate = null;
      clearPreview();
    }
    function dismiss() { stopPreview(); if (dialog.open) dialog.close(); }
    launcher.addEventListener('click', () => {
      candidate = null; response = null; filter.value = '';
      const tile = tiles.find(item => item.dataset.catalogKey === select.value) || tiles[0];
      if (!tile) return;
      category = tile.dataset.catalogItemCategory; filterTiles();
      dialog.showModal(); launcher.setAttribute('aria-expanded', 'true'); tile.focus(); choose(tile);
    });
    dialog.addEventListener('close', () => {
      stopPreview(); launcher.setAttribute('aria-expanded', 'false'); launcher.focus({preventScroll: true});
    });
    dialog.addEventListener('cancel', event => { event.preventDefault(); dismiss(); });
    root.querySelectorAll('[data-catalog-close]').forEach(button => button.addEventListener('click', dismiss));
    filter.addEventListener('input', filterTiles);
    root.querySelectorAll('[data-catalog-category]').forEach(button => button.addEventListener('click', () => { category = button.dataset.catalogCategory; filterTiles(); }));
    for (const tile of tiles) {
      tile.addEventListener('click', () => choose(tile));
      tile.addEventListener('focus', () => choose(tile));
    }
    dialog.addEventListener('keydown', event => {
      if (event.key === 'Enter' && event.target.matches('input')) {
        event.preventDefault(); tiles.find(tile => !tile.hidden)?.focus();
      }
      if (event.key === 'Tab') {
        const controls = [...dialog.querySelectorAll('button:not(:disabled),input,a[href]')].filter(node => !node.closest('[hidden]') && node.getClientRects().length && node.tabIndex >= 0);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
      const tile = event.target.closest('[data-catalog-tile]');
      if (!tile || !['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
      event.preventDefault();
      const visible = tiles.filter(item => !item.hidden);
      const columns = getComputedStyle(find('.cosmetic-catalog-grid')).gridTemplateColumns.split(' ').length;
      const delta = {ArrowLeft:-1,ArrowRight:1,ArrowUp:-columns,ArrowDown:columns}[event.key] || 0;
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? visible.length - 1 : Math.max(0, Math.min(visible.length - 1, visible.indexOf(tile) + delta));
      visible[index]?.focus();
    });
    retry.addEventListener('click', () => { if (candidate) choose(candidate, true); });
    apply.addEventListener('click', () => {
      const key = candidate?.dataset.catalogKey;
      if (!response || response.key !== key || response.locked !== false || !allowed(key)) return;
      if (response.tipo === 'tema') {
        const profile = document.getElementById('profile-root');
        if (profile) theme(profile, response, select.form);
        const href = safeURL(response.theme_css_url, 'css');
        let link = document.getElementById('perfil-preview-theme-css');
        if (href) {
          if (!link) { link = document.createElement('link'); link.id = 'perfil-preview-theme-css'; link.rel = 'stylesheet'; document.head.appendChild(link); }
          link.href = href;
        } else link?.remove();
      }
      select.value = key; committed = key; sync();
      select.dispatchEvent(new Event('input', {bubbles: true})); select.dispatchEvent(new Event('change', {bubbles: true})); dismiss();
    });
    select.addEventListener('input', sync); select.addEventListener('change', sync);
    select.form?.addEventListener('reset', () => { dismiss(); setTimeout(() => { committed = select.value; sync(); }, 0); });
    sync(); find('[data-catalog-controls]').hidden = false; select.hidden = true; root.dataset.catalogReady = 'true';
  }
  const init = () => document.querySelectorAll('[data-cosmetic-catalog]').forEach(enhance);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
