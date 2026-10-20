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
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
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

  var submittedTabKey = 'bonfire-workshop-submitted-tab';
  var submittedTab = window.sessionStorage.getItem(submittedTabKey);
  window.sessionStorage.removeItem(submittedTabKey);
  var initialUrl = new URL(window.location.href);
  if (!initialUrl.searchParams.has('tab') && initialUrl.searchParams.has('status') && submittedTab &&
      tabs.some(function (tab) { return tab.dataset.workshopTab === submittedTab; })) {
    initialUrl.searchParams.set('tab', submittedTab);
    window.history.replaceState(null, '', initialUrl);
  }

  shell.addEventListener('submit', function (event) {
    var form = event.target;
    if (form.method.toLowerCase() !== 'post') return;
    var panel = form.closest('[data-workshop-panel]');
    if (!panel) return;
    var name = panel.dataset.workshopPanel;
    var input = form.querySelector('input[name="tab"]');
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'tab';
      form.appendChild(input);
    }
    input.value = name;
    window.sessionStorage.setItem(submittedTabKey, name);
  });

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
    tab.addEventListener('keydown', function (event) {
      var index = tabs.indexOf(tab);
      var next = event.key === 'ArrowRight' ? (index + 1) % tabs.length :
        event.key === 'ArrowLeft' ? (index - 1 + tabs.length) % tabs.length :
        event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
      if (next < 0) return;
      event.preventDefault();
      tabs[next].focus();
      tabs[next].click();
    });
  });
  window.addEventListener('popstate', function () { show(urlTab()); });
  show(urlTab());
}());
