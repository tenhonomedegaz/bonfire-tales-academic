/* Language catalogue and the existing deterministic transcription, without requests. */
(function () {
  'use strict';
  const languages = JSON.parse(document.getElementById('language-data').textContent || '[]');
  const bySlug = Object.assign(Object.create(null), Object.fromEntries(languages.map(item => [item.slug, item])));
  const source = document.getElementById('languageSource');
  const target = document.getElementById('languageTarget');
  const result = document.getElementById('languageResult');
  const writing = document.getElementById('languageWriting');
  const search = document.getElementById('languageSearch');
  const category = document.getElementById('languageCategory');
  const list = document.getElementById('languageList');
  const rows = Array.from(list.querySelectorAll('.language-row'));
  const details = Array.from(document.querySelectorAll('[data-language-detail]'));
  const sidebar = document.getElementById('languageSidebar');
  const menuButton = document.getElementById('languageMobileMenu');
  const backdrop = document.getElementById('languageBackdrop');
  const copy = document.getElementById('copyTranslation');
  const copyLabel = document.getElementById('languageCopyLabel');
  const copyStatus = document.getElementById('languageCopyStatus');
  const clearText = document.getElementById('languageClearText');
  const mobileLayout = window.matchMedia('(max-width: 1100px)');
  const outsideInert = new Map();
  let selectedSlug = '';
  let copyTimer = null;
  let copying = false;

  // Kept verbatim from the previous page: generated words and rules do not change.
  const vowels = ['a', 'e', 'i', 'o', 'u'];
  const syllables = ['ka','ra','th','el','or','is','va','en','ul','dra','mir','sa','lo','ven','ae','um','tor','shi','na','yr'];

  function hash(value){
    let number = 2166136261;
    for(let i=0;i<value.length;i++) number = Math.imul(number ^ value.charCodeAt(i), 16777619);
    return number >>> 0;
  }

  function transformWord(word, language){
    if(!word || language.slug === 'comum' || /^\d+$/.test(word)) return word;
    const seed = hash(language.slug + ':' + word.toLocaleLowerCase('pt-BR'));
    const count = Math.max(1, Math.min(5, Math.ceil(word.length / 3)));
    let output = '';
    for(let index=0; index<count; index++){
      const shift = (seed >>> ((index % 4) * 7)) + index * 13;
      output += syllables[shift % syllables.length];
      if(index === 0 && word.length > 7) output += vowels[(shift >>> 3) % vowels.length];
    }
    if(word[0] === word[0].toLocaleUpperCase('pt-BR')) output = output[0].toLocaleUpperCase('pt-BR') + output.slice(1);
    return output;
  }

  function translate() {
    const language = bySlug[target.value] || languages[0];
    const text = source.value || '';
    result.textContent = language ? text.replace(/[\p{L}\p{M}\d]+/gu, word => transformWord(word, language)) : '';
    document.getElementById('languageResultPlaceholder').hidden = Boolean(result.textContent);
    writing.textContent = language ? ('Escrita: ' + (language.transcricao || 'oral')) : '';
    document.getElementById('languageResultLabel').textContent = language ? 'Transcrição em ' + language.nome : 'Transcrição';
    document.getElementById('languageCharacterCount').textContent = text.length.toLocaleString('pt-BR') + ' / 1.200';
    clearText.disabled = !text;
    copy.disabled = copying || !result.textContent;
    copyLabel.textContent = 'Copiar';
    copyStatus.textContent = '';
    if (copyTimer) clearTimeout(copyTimer);
  }

  function normalize(value) {
    return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  }

  function filter() {
    const query = normalize(search.value.trim());
    let visible = 0;
    rows.forEach(row => {
      const show = (!query || normalize(row.dataset.search).includes(query)) && (!category.value || row.dataset.category === category.value);
      row.hidden = !show;
      if (show) visible++;
    });
    list.querySelectorAll('[data-language-group]').forEach(heading => {
      heading.hidden = !rows.some(row => !row.hidden && row.dataset.category === heading.dataset.languageGroup);
    });
    document.getElementById('languageResultCount').textContent = visible + ' de ' + languages.length + ' idiomas';
    document.getElementById('languageEmpty').hidden = visible !== 0;
    document.getElementById('languageResetFilters').hidden = !query && !category.value;
    const url = new URL(window.location.href);
    if (search.value.trim()) url.searchParams.set('q', search.value.trim());
    else url.searchParams.delete('q');
    if (url.href !== window.location.href) history.replaceState(null, '', url);
  }

  function resetFilters() {
    search.value = '';
    category.value = '';
    filter();
  }

  function setMenuOpen(isOpen) {
    const open = mobileLayout.matches && isOpen;
    const wasOpen = document.body.classList.contains('language-menu-open');
    const hadSidebarFocus = sidebar.contains(document.activeElement);
    document.body.classList.toggle('language-menu-open', open);
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', open ? 'Fechar lista de idiomas' : 'Abrir lista de idiomas');
    sidebar.inert = mobileLayout.matches && !open;
    if (sidebar.inert) sidebar.setAttribute('aria-hidden', 'true');
    else sidebar.removeAttribute('aria-hidden');
    backdrop.hidden = !open;
    if (open) {
      document.querySelectorAll('.bft-header, .bft-footer, .language-masthead, .language-reading').forEach(element => {
        if (!outsideInert.has(element)) outsideInert.set(element, element.inert);
        element.inert = true;
      });
      search.focus();
    } else {
      outsideInert.forEach((inert, element) => { element.inert = inert; });
      outsideInert.clear();
      if ((wasOpen || hadSidebarFocus) && mobileLayout.matches) menuButton.focus();
    }
  }

  function selectLanguage(slug, {historyMode = 'push', focusDetail = false, closeDrawer = true} = {}) {
    const language = bySlug[slug];
    if (!language) return;
    selectedSlug = slug;
    target.value = slug;
    details.forEach(article => { article.hidden = article.dataset.languageDetail !== slug; });
    rows.forEach(row => {
      if (row.dataset.languageSlug === slug) row.setAttribute('aria-current', 'true');
      else row.removeAttribute('aria-current');
    });
    if (historyMode !== 'none') {
      const url = new URL(window.location.href);
      url.hash = encodeURIComponent(slug);
      if (url.href !== window.location.href) history[historyMode === 'replace' ? 'replaceState' : 'pushState'](null, '', url);
    }
    if (closeDrawer) setMenuOpen(false);
    translate();
    if (focusDetail) {
      const article = details.find(item => item.dataset.languageDetail === slug);
      article.querySelector('h2').focus({preventScroll: true});
      const top = article.getBoundingClientRect().top;
      if (top < 80 || top > window.innerHeight - 120) article.scrollIntoView({block: 'start'});
    }
  }

  function restoreFromHash() {
    search.value = new URL(window.location.href).searchParams.get('q') || '';
    filter();
    let slug = '';
    try { slug = decodeURIComponent(window.location.hash.replace(/^#(?:idioma-)?/, '')); }
    catch { /* Malformed links must not interrupt the transcriber. */ }
    const visibleRows = rows.filter(row => !row.hidden);
    const exactMatch = search.value.trim() && visibleRows.find(row => normalize(bySlug[row.dataset.languageSlug]?.nome) === normalize(search.value.trim()))?.dataset.languageSlug;
    const firstVisible = visibleRows[0]?.dataset.languageSlug;
    selectLanguage(bySlug[slug] ? slug : exactMatch || firstVisible || selectedSlug || languages[0]?.slug,
      {historyMode: 'none', focusDetail: Boolean(slug || exactMatch)});
  }

  source.addEventListener('input', translate);
  target.addEventListener('change', () => selectLanguage(target.value));
  rows.forEach(row => row.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    selectLanguage(row.dataset.languageSlug, {focusDetail: true});
  }));
  search.addEventListener('input', filter);
  category.addEventListener('change', filter);
  document.getElementById('languageResetFilters').addEventListener('click', resetFilters);
  document.getElementById('languageEmptyReset').addEventListener('click', () => { resetFilters(); search.focus(); });
  clearText.addEventListener('click', () => { source.value = ''; translate(); source.focus(); });
  copy.addEventListener('click', async () => {
    if (!result.textContent || copying) return;
    copying = true;
    copy.disabled = true;
    try {
      await navigator.clipboard.writeText(result.textContent);
      copyLabel.textContent = 'Copiado';
      copyStatus.textContent = 'Transcrição copiada.';
      copyTimer = setTimeout(() => { copyLabel.textContent = 'Copiar'; }, 1200);
    } catch {
      copyStatus.textContent = 'Não foi possível copiar. Selecione a transcrição e copie manualmente.';
    } finally {
      copying = false;
      copy.disabled = !result.textContent;
    }
  });
  menuButton.addEventListener('click', () => setMenuOpen(!document.body.classList.contains('language-menu-open')));
  document.getElementById('languageCloseMenu').addEventListener('click', () => setMenuOpen(false));
  backdrop.addEventListener('click', () => setMenuOpen(false));
  mobileLayout.addEventListener('change', () => setMenuOpen(false));
  window.addEventListener('popstate', restoreFromHash);
  window.addEventListener('hashchange', restoreFromHash);
  document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('language-menu-open')) return;
    if (event.key === 'Escape') { event.preventDefault(); setMenuOpen(false); }
    if (event.key === 'Tab') {
      const focusable = [...sidebar.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]')].filter(element => element.getClientRects().length);
      focusable.push(menuButton);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !focusable.includes(document.activeElement))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !focusable.includes(document.activeElement))) { event.preventDefault(); first?.focus(); }
    }
  });

  document.body.classList.add('language-enhanced');
  target.disabled = !languages.length;
  source.disabled = !languages.length;
  restoreFromHash();
  setMenuOpen(false);
  translate();
})();
