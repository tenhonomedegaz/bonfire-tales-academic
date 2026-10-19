(function () {
  const page = document.querySelector('.glo-page');
  if (!page) return;
  const index = page.querySelector('.glo-index-panel');
  const input = page.querySelector('[data-reference-query]');
  const links = Array.from(page.querySelectorAll('.glo-index a[data-reference-link]'));
  const mobile = window.matchMedia('(max-width:900px)');
  if (!index) return;

  function adaptIndex() {
    index.open = !mobile.matches;
  }

  function markCurrent() {
    links.forEach(function (link) {
      if (link.getAttribute('href') === window.location.hash) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }

  function openExactRuleFromSearch() {
    if (window.location.hash) {
      let current = null;
      try { current = document.getElementById(decodeURIComponent(window.location.hash.slice(1))); }
      catch { return; }
      if (current?.matches('.glo-item[data-reference-item]') && !current.classList.contains('hidden')) {
        window.requestAnimationFrame(() => {
          current.focus({preventScroll: true});
          current.scrollIntoView({block: 'start'});
        });
      }
      return;
    }
    const query = new URL(window.location.href).searchParams.get('q')?.trim();
    if (!query) return;
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const match = Array.from(page.querySelectorAll('.glo-rule[data-reference-item]')).find(item => {
      const name = item.querySelector('h3')?.firstChild?.textContent.trim() || '';
      return normalize(name) === normalize(query) && !item.classList.contains('hidden');
    });
    if (!match) return;
    const url = new URL(window.location.href);
    url.hash = match.id;
    history.replaceState(null, '', url.href);
    markCurrent();
    window.requestAnimationFrame(() => {
      match.focus({preventScroll: true});
      match.scrollIntoView({block: 'start'});
    });
  }

  adaptIndex();
  mobile.addEventListener('change', adaptIndex);
  window.addEventListener('hashchange', markCurrent);
  links.forEach(function (link) {
    link.addEventListener('click', function () {
      if (mobile.matches) index.open = false;
      const target = document.getElementById(link.getAttribute('href').slice(1));
      if (target) window.requestAnimationFrame(function () { target.focus({preventScroll:true}); });
      window.requestAnimationFrame(markCurrent);
    });
  });
  if (input) input.addEventListener('input', function () {
    // A filtered page may shrink beneath the current scroll position.
    // Return to the search and first matches while the field keeps focus.
    if (window.location.hash) {
      const url = new URL(window.location.href);
      url.hash = '';
      history.replaceState(null, '', url.href);
      markCurrent();
    }
    window.scrollTo({top:0,behavior:'instant'});
  });
  markCurrent();
  openExactRuleFromSearch();
  window.addEventListener('popstate', () => window.requestAnimationFrame(openExactRuleFromSearch));
})();
