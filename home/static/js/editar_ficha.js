/* Mutações rápidas da edição da ficha. Mantém POST clássico como fallback e usa
 * fetch quando JS está disponível, começando pelo ledger de aventuras da staff. */
(function () {
  'use strict';

  function setText(selector, value) {
    var el = document.querySelector(selector);
    if (el && value !== undefined && value !== null) el.textContent = value;
  }

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('form[data-aventura-form], form[data-aventura-reverter]');
    if (!form || event.defaultPrevented) return;
    event.preventDefault();
    var button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    var data = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': data.get('csrfmiddlewaretoken') || ''
      },
      body: data,
      credentials: 'same-origin'
    }).then(function (response) {
      return response.json().then(function (json) {
        return { ok: response.ok, json: json };
      });
    }).then(function (result) {
      var payload = result.json || {};
      if (typeof payload.staffbox_html === 'string') {
        var box = document.getElementById('lvl-aventuras-staffbox');
        if (box) box.outerHTML = payload.staffbox_html;
      }
      if (payload.progressao) {
        setText('[data-ficha-aventuras]', payload.progressao.aventuras);
        setText('[data-ficha-teto]', payload.progressao.nivel_label);
        setText('[data-ficha-braseiros]', payload.progressao.braseiros);
      }
      setText('#loja-carteira', payload.carteira_display);
      if (!result.ok && button) button.disabled = false;
    }).catch(function () {
      if (button) button.disabled = false;
    });
  });
})();
