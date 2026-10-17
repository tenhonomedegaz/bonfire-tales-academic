/* Prévia dos mercados. O servidor mantém a autoridade sobre preço final e compra. */
(function () {
  'use strict';

  var shop = document.querySelector('[data-shop-kind="mundano"], [data-shop-kind="magico"]');
  if (!shop) return;
  var detail = shop.querySelector('[data-shop-detail]');
  var wallet = shop.querySelector('[data-shop-carteira]');
  var picker = shop.querySelector('[data-shop-personagem]');
  var sheetLink = shop.querySelector('[data-market-sheet-link]');
  var feedback = shop.querySelector('[data-shop-feedback]');
  var mirror = shop.querySelector('[data-market-mobile-feedback]');
  var filterLabel = shop.querySelector('[data-market-filter-label]');

  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function parseCoins(value) {
    var found = false;
    var amount = 0;
    String(value || '').toUpperCase().replace(/(\d+)\s*(PO|PP|PC)\b/g, function (_, count, unit) {
      found = true;
      amount += Number(count) * { PO: 100, PP: 10, PC: 1 }[unit];
      return _;
    });
    return found ? (/^\s*[-−]/.test(value) ? -amount : amount) : null;
  }

  function displayCoins(copper) {
    var remaining = Math.abs(copper);
    var parts = [];
    [[100, 'PO'], [10, 'PP'], [1, 'PC']].forEach(function (unit) {
      var count = Math.floor(remaining / unit[0]);
      remaining %= unit[0];
      if (count) parts.push(count + ' ' + unit[1]);
    });
    return (copper < 0 ? '-' : '') + (parts.length ? parts.join(' ') : '0 PO');
  }

  function update() {
    if (filterLabel) {
      var active = 0;
      ['[data-shop-group]', '[data-shop-rarity]', '[data-shop-attunement]', '[data-shop-sort]'].forEach(function (selector) {
        var field = shop.querySelector(selector);
        if (field && field.value !== (selector === '[data-shop-sort]' ? 'nome-asc' : 'todas')) active++;
      });
      if (shop.querySelector('[data-shop-favorites]:checked')) active++;
      setText(filterLabel, 'Mais filtros' + (active ? ' · ' + active + ' ativo' + (active > 1 ? 's' : '') : ''));
    }
    if (sheetLink && picker) {
      var pattern = sheetLink.getAttribute('data-market-sheet-pattern');
      if (pattern) sheetLink.href = pattern.replace('/0/', '/' + encodeURIComponent(picker.value) + '/') + '?aba=mochila';
    }
    if (!detail || !wallet) return;
    var form = detail.querySelector('[data-shop-buy]:not([data-backend-unavailable])');
    if (!form) return;
    var card = form.closest('.mkt-card');
    var price = card && card.querySelector('.mkt-price');
    var totalNode = card && card.querySelector('[data-market-total]');
    var afterNode = card && card.querySelector('[data-market-after]');
    if (!totalNode || !afterNode) return;
    var base = form.querySelector('[name="base_item"]');
    var quantity = form.querySelector('[name="qtd"]');
    var count = quantity ? Number(quantity.value) : 1;
    var unit = price ? parseCoins(price.textContent) : null;
    var balance = parseCoins(wallet.textContent);
    if (base && !base.value) {
      setText(totalNode, '—');
      setText(afterNode, 'Escolha um item-base antes de comprar.');
    } else if (form.dataset.magicSurcharge === 'true') {
      setText(totalNode, '—');
      setText(afterNode, 'O total inclui o item-base e será calculado pelo servidor.');
    } else if (!Number.isInteger(count) || count < 1 || count > 99 || unit === null || balance === null) {
      setText(totalNode, '—');
      setText(afterNode, 'Informe uma quantidade de 1 a 99.');
    } else {
      var total = unit * count;
      setText(totalNode, displayCoins(total));
      setText(afterNode, total <= balance
        ? 'Saldo após compra: ' + displayCoins(balance - total)
        : 'Saldo insuficiente para esta quantidade.');
    }
  }

  shop.addEventListener('input', function (event) {
    if (event.target.matches('[name="qtd"]')) update();
  });
  shop.addEventListener('change', update);
  if (detail) new MutationObserver(update).observe(detail, { childList: true, subtree: true, characterData: true });
  if (wallet) new MutationObserver(update).observe(wallet, { childList: true, characterData: true });
  if (feedback && mirror) new MutationObserver(function () {
    var message = feedback.hidden ? '' : feedback.textContent;
    setText(mirror, message);
    mirror.hidden = !message;
    mirror.classList.toggle('is-err', feedback.classList.contains('is-err'));
  }).observe(feedback, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['hidden', 'class'] });
  update();
}());
