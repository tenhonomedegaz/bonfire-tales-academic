(function () {
  'use strict';
  var root = document.querySelector('[data-shop-root]');
  if (!root || root.dataset.marketGameReady) return;
  root.dataset.marketGameReady = '1';
  document.querySelectorAll('[data-market-select]').forEach(function (button) {
    button.addEventListener('click', function () {
      var target = button.getAttribute('data-market-select');
      var row = Array.from(root.querySelectorAll('[data-mkt-row]')).find(function (item) {
        return item.getAttribute('data-target') === target;
      });
      if (!row) return;
      var buyTab = root.querySelector('[data-shop-tab="comprar"]');
      if (buyTab) buyTab.click();
      var search = root.querySelector('[data-shop-search]');
      var group = root.querySelector('[data-shop-group]');
      var favorites = root.querySelector('[data-shop-favorites]');
      if (search) { search.value = ''; search.dispatchEvent(new Event('input', { bubbles: true })); }
      if (group) { group.value = 'todas'; group.dispatchEvent(new Event('change', { bubbles: true })); }
      if (favorites && favorites.checked) {
        favorites.checked = false;
        favorites.dispatchEvent(new Event('change', { bubbles: true }));
      }
      row.click();
    });
  });
  root.addEventListener('click', function (event) {
    var row = event.target.closest('[data-target], .mkt-row');
    if (!row || !root.contains(row)) return;
    root.querySelectorAll('.mkt-row.is-selected').forEach(function (item) { item.classList.remove('is-selected'); });
    row.classList.add('is-selected');
  });
}());
