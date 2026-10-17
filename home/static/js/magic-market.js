(function () {
  'use strict';
  var root = document.querySelector('.bft-magic-market');
  if (!root || root.dataset.magicMarketReady) return;
  root.dataset.magicMarketReady = '1';
  var buttons = root.querySelectorAll('[data-magic-shop]');
  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      buttons.forEach(function (item) { item.setAttribute('aria-pressed', item === button ? 'true' : 'false'); });
    });
  });
}());
