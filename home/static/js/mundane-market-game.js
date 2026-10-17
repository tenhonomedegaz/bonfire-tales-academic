(function () {
  'use strict';
  var root = document.querySelector('[data-shop-root]');
  if (!root || root.dataset.marketGameReady) return;
  root.dataset.marketGameReady = '1';
  root.addEventListener('click', function (event) {
    var row = event.target.closest('[data-target], .mkt-row');
    if (!row || !root.contains(row)) return;
    root.querySelectorAll('.mkt-row.is-selected').forEach(function (item) { item.classList.remove('is-selected'); });
    row.classList.add('is-selected');
  });
}());
