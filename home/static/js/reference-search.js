(function () {
  document.querySelectorAll('[data-reference-search-root]').forEach(function (root) {
    const input = root.querySelector('[data-reference-query]');
    const items = Array.from(root.querySelectorAll('[data-reference-item]'));
    const links = Array.from(root.querySelectorAll('[data-reference-link]'));
    const groups = Array.from(root.querySelectorAll('[data-reference-group]'));
    const count = root.querySelector('[data-reference-count]');
    const empty = root.querySelector('[data-reference-empty]');
    if (!input) return;

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

    input.addEventListener('input', filter);
    filter();
  });
})();
