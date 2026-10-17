(function () {
  'use strict';
  document.querySelectorAll('[data-shop-search]').forEach(function (input) {
    input.addEventListener('input', function () {
      var query = input.value.trim().toLocaleLowerCase();
      var root = input.closest('[data-shop-root]');
      if (!root) return;
      root.querySelectorAll('[data-search]').forEach(function (row) {
        row.hidden = Boolean(query) && !row.dataset.search.toLocaleLowerCase().includes(query);
      });
    });
  });
}());
