/* Mutações rápidas do PAINEL DA STAFF (aventuras + concessão de item). Mantém POST
 * clássico como fallback e usa fetch quando JS está disponível.
 * Onda C: recursos, magias preparadas e a LOJA saíram desta página — o que sobrou aqui
 * mexe só no ledger de aventuras, nas concessões e nos derivados que elas alteram. */
(function () {
  'use strict';

  function setText(selector, value) {
    var el = document.querySelector(selector);
    if (el && value !== undefined && value !== null) el.textContent = value;
  }

  function submitForm(form) {
    var data = new FormData(form);
    return fetch(form.action, {
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
    });
  }

  function setFeedback(id, message, ok) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = message || '';
    el.hidden = !message;
    el.classList.toggle('is-ok', !!ok);
    el.classList.toggle('is-err', !ok);
  }

  function applyInventory(payload) {
    // O inventário saiu daqui na onda B (vive na aba Mochila da ficha); esta página só
    // precisa refletir carteira e os derivados que a concessão mexe.
    setText('[data-carteira-display]', payload.carteira_display);
    if (payload.ficha) {
      setText('[data-ficha-ca]', payload.ficha.ca);
      setText('[data-ficha-pv]', payload.ficha.pv_maximo);
    }
  }

  // Quais <details> de missão estão ABERTOS agora (por id de lançamento). O staffbox volta
  // do servidor inteiro e fechado; sem isto, corrigir/consumir fechava o bloco na cara da
  // staff no meio do trabalho.
  function missoesAbertas() {
    return Array.prototype.filter.call(
      document.querySelectorAll('[data-missao-details]'), function (d) { return d.open; }
    ).map(function (d) { return d.getAttribute('data-missao-details'); });
  }

  function reabrirMissoes(ids) {
    (ids || []).forEach(function (id) {
      var el = document.querySelector('[data-missao-details="' + id + '"]');
      if (el) el.open = true;
    });
  }

  // Todo formulário do staffbox de missões (lançar, reverter, corrigir, consumo) devolve
  // o MESMO fragmento re-renderizado — um handler só cobre os quatro.
  document.addEventListener('submit', function (event) {
    var form = event.target.closest(
      'form[data-aventura-form], form[data-aventura-reverter],' +
      'form[data-aventura-editar], form[data-aventura-consumo]'
    );
    if (!form || event.defaultPrevented) return;
    event.preventDefault();
    var button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    // A linha EDITADA reabre mesmo que estivesse fechada (o staff acabou de agir nela).
    var editada = form.closest('[data-missao-details]');
    var abertas = missoesAbertas();
    if (editada) {
      var idEditada = editada.getAttribute('data-missao-details');
      if (abertas.indexOf(idEditada) === -1) abertas.push(idEditada);
    }
    submitForm(form).then(function (result) {
      var payload = result.json || {};
      if (typeof payload.staffbox_html === 'string') {
        var box = document.getElementById('lvl-aventuras-staffbox');
        if (box) box.outerHTML = payload.staffbox_html;
        reabrirMissoes(abertas);
      }
      if (payload.progressao) {
        setText('[data-ficha-aventuras]', payload.progressao.aventuras);
        setText('[data-ficha-teto]', payload.progressao.nivel_label);
        setText('[data-ficha-braseiros]', payload.progressao.braseiros);
      }
      setText('[data-carteira-display]', payload.carteira_display);
      if (!result.ok && button) button.disabled = false;
    }).catch(function () {
      if (button) button.disabled = false;
    });
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest(
      'form[data-conceder-form], form[data-concessao-reverter]'
    );
    if (!form || event.defaultPrevented) return;
    event.preventDefault();
    var button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;

    submitForm(form).then(function (result) {
      var payload = result.json || {};
      if (typeof payload.inventario_html === 'string') applyInventory(payload);
      if (typeof payload.concessoes_html === 'string') {
        var ledger = document.getElementById('ficha-concessoes-dinamico');
        if (ledger) ledger.outerHTML = payload.concessoes_html;
      }
      if (button && document.body.contains(button)) button.disabled = false;
    }).catch(function () {
      if (button) button.disabled = false;
    });
  });
})();
