(function () {
  document.querySelectorAll('[data-reference-search-root]').forEach(function (root) {
    const input = root.querySelector('[data-reference-query]');
    const items = Array.from(root.querySelectorAll('[data-reference-item]'));
    const links = Array.from(root.querySelectorAll('[data-reference-link]'));
    const groups = Array.from(root.querySelectorAll('[data-reference-group]'));
    const count = root.querySelector('[data-reference-count]');
    const empty = root.querySelector('[data-reference-empty]');
    if (!input) return;
    let editingSearch = false;

    function normalize(value) {
      return (value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    function filter() {
      const query = normalize(input.value.trim());
      const visibleIds = new Set();
      let visible = 0;
      items.forEach(function (item) {
        const matches = !query || normalize((item.dataset.busca || '') + ' ' + item.textContent).includes(query);
        item.classList.toggle('hidden', !matches);
        if (matches) {
          visible += 1;
          visibleIds.add(item.id);
        }
      });
      links.forEach(function (link) {
        const target = link.getAttribute('href')?.slice(1);
        link.classList.toggle('hidden', !visibleIds.has(target));
      });
      groups.forEach(function (group) {
        group.classList.toggle('hidden', !Array.from(group.querySelectorAll('[data-reference-item]')).some(
          item => !item.classList.contains('hidden')
        ));
      });
      if (count) count.textContent = String(visible);
      if (empty) empty.classList.toggle('hidden', visible !== 0);
    }

    function restoreFromUrl() {
      editingSearch = false;
      input.value = new URLSearchParams(window.location.search).get('q') || '';
      filter();
    }

    input.addEventListener('input', function () {
      filter();
      const url = new URL(window.location.href);
      const query = input.value.trim();
      if (query) url.searchParams.set('q', query);
      else url.searchParams.delete('q');
      if (url.href !== window.location.href) {
        history[editingSearch ? 'replaceState' : 'pushState'](null, '', url.href);
        editingSearch = true;
      }
    });
    input.addEventListener('blur', function () { editingSearch = false; });
    window.addEventListener('popstate', restoreFromUrl);
    restoreFromUrl();
  });
})();
