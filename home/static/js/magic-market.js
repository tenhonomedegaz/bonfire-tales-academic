(function () {
  'use strict';
  var page = document.querySelector('.bft-magic-market');
  var shop = page && page.querySelector('[data-shop-kind="magico"]');
  if (!shop || shop.dataset.magicMarketReady) return;
  shop.dataset.magicMarketReady = '1';
  var group = shop.querySelector('[data-shop-group]');
  var stock = shop.querySelector('[data-shop-stock]');
  var search = shop.querySelector('[data-shop-search]');
  var buttons = page.querySelectorAll('[data-magic-shop]');
  if (!group || !stock || !search) return;

  function syncButtons() {
    buttons.forEach(function (button) {
      button.setAttribute('aria-pressed', String(group.value === button.dataset.magicShop));
    });
  }
  function applyFilters() {
    group.dispatchEvent(new Event('change', { bubbles: true }));
    syncButtons();
  }
  function resetFilters() {
    search.value = '';
    group.value = 'todas';
    stock.value = 'disponivel';
    [['[data-shop-rarity]', 'todas'], ['[data-shop-attunement]', 'todas'], ['[data-shop-sort]', 'nome-asc']].forEach(function (entry) {
      var field = shop.querySelector(entry[0]);
      if (field) field.value = entry[1];
    });
    var favorites = shop.querySelector('[data-shop-favorites]');
    if (favorites) favorites.checked = false;
  }
  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      shop.querySelector('[data-shop-tab="comprar"]')?.click();
      search.value = '';
      group.value = button.dataset.magicShop;
      applyFilters();
      shop.scrollIntoView({ block: 'start' });
    });
  });
  page.querySelector('[data-magic-caravan]')?.addEventListener('click', function () {
    resetFilters();
    stock.value = 'caravana';
    applyFilters();
    shop.scrollIntoView({ block: 'start' });
  });
  shop.querySelector('[data-market-reset]')?.addEventListener('click', function () {
    resetFilters();
    applyFilters();
    search.focus();
  });
  // Links do pacote usam o slug; o controlador compartilhado usa data-target na URL.
  var requestedItem = new URLSearchParams(window.location.search).get('item');
  if (requestedItem) {
    var linkedRow = Array.from(shop.querySelectorAll('[data-magic-slug]')).find(function (row) {
      return row.dataset.magicSlug === requestedItem;
    });
    if (linkedRow) {
      if (linkedRow.dataset.available !== 'true') stock.value = 'catalogo';
      applyFilters();
      linkedRow.click();
    }
  }
  var selectionStatus = shop.querySelector('[data-market-selection-status]');
  if (selectionStatus) {
    function announceSelection() {
      var selected = shop.querySelector('[data-shop-pane="comprar"] [data-mkt-row].is-selected');
      var name = selected?.querySelector('.mkt-row-name')?.textContent.trim();
      var message = name ? 'Selecionado: ' + name + '.' : 'Nenhum item neste filtro.';
      if (selectionStatus.textContent !== message) selectionStatus.textContent = message;
    }
    new MutationObserver(announceSelection).observe(shop, {
      subtree: true,
      attributes: true,
      attributeFilter: ['aria-selected', 'hidden']
    });
    announceSelection();
  }
  group.addEventListener('change', syncButtons);
  window.addEventListener('popstate', function () { setTimeout(syncButtons, 0); });
  syncButtons();
}());
