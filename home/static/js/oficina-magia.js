(function () {
  'use strict';
  document.querySelectorAll('[data-workshop-tab]').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var shell = tab.closest('.workshop-shell');
      if (!shell) return;
      var name = tab.dataset.workshopTab;
      shell.querySelectorAll('[data-workshop-panel]').forEach(function (panel) {
        panel.hidden = panel.dataset.workshopPanel !== name;
      });
      shell.querySelectorAll('[data-workshop-tab]').forEach(function (item) {
        item.classList.toggle('is-active', item === tab);
        item.setAttribute('aria-selected', item === tab ? 'true' : 'false');
      });
    });
  });
}());
