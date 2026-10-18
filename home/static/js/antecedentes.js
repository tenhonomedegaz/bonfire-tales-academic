/* Local catalogue enhancement. The server-rendered origins remain readable without JS. */
(() => {
  'use strict';
  const data = document.getElementById('background-data');
  if (!data) return;
  let items;
  try { items = JSON.parse(data.textContent); } catch { return; }
  const search = document.getElementById('catalogSearch');
  const type = document.getElementById('catalogType');
  const sidebar = document.getElementById('catalogSidebar');
  const trigger = document.getElementById('catalogMobileMenuButton');
  const backdrop = document.getElementById('catalogMobileBackdrop');
  const count = document.getElementById('backgroundResultCount');
  const clear = document.getElementById('backgroundClearFilters');
  const empty = document.getElementById('backgroundDetailEmpty');
  const mobile = window.matchMedia('(max-width: 1100px)');
  const links = Array.from(document.querySelectorAll('.background-index-item'));
  const articles = new Map(Array.from(document.querySelectorAll('[data-background]')).map(el => [el.dataset.background, el]));
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  const textIndex = new Map(items.map(item => [item.slug, normalize([
    item.nome, item.tipo, item.resumo, item.descricao, ...(item.tags || []), ...Object.values(item.meta || {})
  ].join(' '))]));
  const types = [...new Set(items.map(item => item.tipo).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  for (const value of types) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    type.appendChild(option);
  }
  let activeSlug = '';
  let menuOpen = false;
  const outsideDialog = Array.from(document.querySelectorAll('.bft-header, .bft-footer, .bft-skip, .background-header, .background-mobile-bar, .background-reading, aside[aria-label^="Publicidade"]'));
  const originalInert = new Map(outsideDialog.map(el => [el, el.inert]));

  function filtered() {
    const query = normalize(search.value.trim());
    return items.filter(item => (!type.value || item.tipo === type.value) && (!query || textIndex.get(item.slug).includes(query)));
  }

  function prepareCopy(item, article) {
    const copy = article.querySelector('.background-copy');
    if (copy.dataset.prepared === 'true') return;
    if (item.descricao && typeof window.renderBonfireMarkdownElement === 'function') {
      window.renderBonfireMarkdownElement(copy, item.descricao);
      // A visual grouping only: preserve every heading, paragraph, link and rule.
      const heading = Array.from(copy.querySelectorAll('h2, h3, h4')).find(el => normalize(el.textContent.trim()) === 'habilidade do antecedente');
      if (heading) {
        const section = document.createElement('section');
        section.className = 'background-ability';
        const level = Number(heading.tagName.slice(1));
        heading.before(section);
        let node = heading;
        while (node) {
          if (node !== heading && /^H[1-6]$/.test(node.nodeName) && Number(node.nodeName.slice(1)) <= level) break;
          const next = node.nextSibling;
          section.appendChild(node);
          node = next;
        }
      }
    }
    copy.dataset.prepared = 'true';
  }

  function render() {
    const visible = filtered();
    const slugs = new Set(visible.map(item => item.slug));
    if (!slugs.has(activeSlug)) activeSlug = visible[0]?.slug || '';
    for (const link of links) {
      link.hidden = !slugs.has(link.dataset.slug);
      if (link.dataset.slug === activeSlug) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    }
    for (const [slug, article] of articles) article.hidden = slug !== activeSlug;
    const selected = visible.find(item => item.slug === activeSlug);
    if (selected) prepareCopy(selected, articles.get(selected.slug));
    empty.hidden = visible.length > 0 || items.length === 0;
    document.getElementById('backgroundListEmpty').hidden = visible.length > 0;
    count.textContent = `${visible.length} ${visible.length === 1 ? 'antecedente' : 'antecedentes'}`;
    clear.hidden = !search.value && !type.value;
    document.getElementById('backgroundMobileName').textContent = selected?.nome || 'Nenhum resultado';
  }

  function syncUrl(mode) {
    const url = new URL(window.location.href);
    const query = search.value.trim();
    if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
    if (type.value) url.searchParams.set('tipo', type.value); else url.searchParams.delete('tipo');
    if (activeSlug) url.hash = encodeURIComponent(activeSlug);
    if (url.href !== window.location.href) history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url);
  }

  function restoreUrl() {
    const url = new URL(window.location.href);
    search.value = url.searchParams.get('q') || '';
    type.value = types.includes(url.searchParams.get('tipo')) ? url.searchParams.get('tipo') : '';
    try { activeSlug = decodeURIComponent(url.hash.slice(1)); } catch { activeSlug = ''; }
    if (!activeSlug && search.value.trim()) {
      activeSlug = filtered().find(item => normalize(item.nome) === normalize(search.value.trim()))?.slug || '';
    }
    render();
  }

  function setMenu(open, returnFocus = true) {
    menuOpen = mobile.matches && open;
    document.body.classList.toggle('background-menu-open', menuOpen);
    trigger.setAttribute('aria-expanded', String(menuOpen));
    backdrop.hidden = !menuOpen;
    for (const el of outsideDialog) el.inert = menuOpen || originalInert.get(el);
    if (!menuOpen && mobile.matches && returnFocus && sidebar.contains(document.activeElement)) trigger.focus();
    sidebar.inert = mobile.matches && !menuOpen;
    if (sidebar.inert) sidebar.setAttribute('aria-hidden', 'true'); else sidebar.removeAttribute('aria-hidden');
    if (menuOpen) {
      sidebar.setAttribute('role', 'dialog');
      sidebar.setAttribute('aria-modal', 'true');
      search.focus();
    } else {
      sidebar.removeAttribute('role');
      sidebar.removeAttribute('aria-modal');
    }
  }

  function resetFilters() {
    search.value = '';
    type.value = '';
    render();
    syncUrl('push');
    if (!mobile.matches || menuOpen) search.focus();
    else articles.get(activeSlug)?.querySelector('.detail-title').focus({ preventScroll: true });
  }

  for (const link of links) link.addEventListener('click', event => {
    // Keep normal browser link actions (new tab, copy link, etc.) available.
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    activeSlug = link.dataset.slug;
    render();
    syncUrl('push');
    setMenu(false, false);
    const heading = articles.get(activeSlug)?.querySelector('.detail-title');
    heading?.focus({ preventScroll: true });
    const article = articles.get(activeSlug);
    if (article && article.getBoundingClientRect().top < 55) article.scrollIntoView({ block: 'start' });
  });
  search.addEventListener('input', () => { render(); syncUrl('replace'); });
  type.addEventListener('change', () => { render(); syncUrl('push'); });
  clear.addEventListener('click', resetFilters);
  document.getElementById('backgroundResetSearch').addEventListener('click', resetFilters);
  trigger.addEventListener('click', () => setMenu(!menuOpen));
  backdrop.addEventListener('click', () => setMenu(false));
  document.getElementById('backgroundCloseMenu').addEventListener('click', () => setMenu(false));
  mobile.addEventListener('change', () => setMenu(false));
  document.addEventListener('keydown', event => {
    if (!menuOpen) return;
    if (event.key === 'Escape') { event.preventDefault(); setMenu(false); }
    if (event.key === 'Tab') {
      const focusable = Array.from(sidebar.querySelectorAll('a[href], button, input, select')).filter(el => !el.hidden && !el.closest('[hidden]') && !el.disabled);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      else if (!sidebar.contains(document.activeElement)) { event.preventDefault(); first?.focus(); }
    }
  });
  window.addEventListener('popstate', () => { restoreUrl(); setMenu(false); });
  window.addEventListener('hashchange', restoreUrl);
  document.body.classList.add('background-enhanced');
  restoreUrl();
  setMenu(false, false);
})();
