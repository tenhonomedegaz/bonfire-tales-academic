(function () {
  'use strict';
  var shell = document.querySelector('.workshop-shell');
  if (!shell) return;
  var tabs = Array.from(shell.querySelectorAll('[data-workshop-tab]'));
  var panels = shell.querySelectorAll('[data-workshop-panel]');
  var picker = shell.querySelector('[data-shop-picker]');
  var pickerTab;
  if (picker) {
    pickerTab = document.createElement('input');
    pickerTab.type = 'hidden';
    pickerTab.name = 'tab';
    picker.appendChild(pickerTab);
  }

  function show(name) {
    if (!tabs.some(function (tab) { return tab.dataset.workshopTab === name; })) name = 'scrolls';
    tabs.forEach(function (tab) {
      var active = tab.dataset.workshopTab === name;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    panels.forEach(function (panel) {
      var active = panel.dataset.workshopPanel === name;
      panel.hidden = !active;
      panel.classList.toggle('is-active', active);
    });
    if (pickerTab) pickerTab.value = name;
  }

  function urlTab() {
    return new URL(window.location.href).searchParams.get('tab') || 'scrolls';
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      var name = tab.dataset.workshopTab;
      show(name);
      var url = new URL(window.location.href);
      if (url.searchParams.get('tab') !== name) {
        url.searchParams.set('tab', name);
        window.history.pushState(null, '', url);
      }
    });
  });
  window.addEventListener('popstate', function () { show(urlTab()); });
  show(urlTab());
}());
