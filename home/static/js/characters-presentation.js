/* Progressive visual/accessibility helpers. Existing sheet actions own all state. */
(function () {
  'use strict';
  document.querySelectorAll('.banner-rank-visual img').forEach(function (image) {
    function fallback() { image.hidden = true; }
    image.addEventListener('error', fallback);
    if (image.complete && !image.naturalWidth) fallback();
  });
  // This notice exists only in the isolated design runner, never in production.
  var localFeedback = document.querySelector('[data-character-preview-feedback]');
  if (localFeedback) {
    document.querySelector('[data-character-preview-close]').addEventListener('click', function () { localFeedback.hidden = true; });
    document.addEventListener('submit', function (event) {
      var form = event.target;
      if (!form.closest('.ficha')) return;
      var path = new URL(form.action, location.href).pathname;
      if (/\/(notas|personalidade|info)\/$/.test(path)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      localFeedback.querySelector('[data-character-preview-message]').textContent = 'Esta aÃ§Ã£o depende dos serviÃ§os oficiais. A ficha de demonstraÃ§Ã£o nÃ£o foi alterada.';
      localFeedback.hidden = false;
    }, true);
  }
  var tabs = Array.from(document.querySelectorAll('.ficha-tabs [role=tab]'));
  tabs.forEach(function (tab, index) {
    var name = tab.dataset.tab;
    var panel = document.querySelector('[data-tabpanel="' + name + '"]');
    if (!panel) return;
    tab.id = 'character-tab-' + name;
    panel.id = 'character-panel-' + name;
    tab.setAttribute('aria-controls', panel.id);
    panel.setAttribute('aria-labelledby', tab.id);
    tab.addEventListener('keydown', function (event) {
      var target = event.key === 'ArrowRight' ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft' ? (index - 1 + tabs.length) % tabs.length
        : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
      if (target < 0) return;
      event.preventDefault();
      tabs[target].focus();
      tabs[target].click();
    });
  });
})();

