/* Aba MOCHILA da ficha (Ficha v2, onda B).
 *
 * Equipar/desequipar/sintonizar vão por fetch nos MESMOS endpoints de sempre — a UI
 * mudou de lugar, a lógica não. Cada resposta traz os partials já renderizados pelo
 * servidor (grade de slots, lista da mochila e os dois blocos da aba Ficha), então aqui
 * só se troca HTML: zero regra de slot duplicada no cliente.
 *
 * Sem JS, os mesmos forms continuam funcionando por POST + redirect.
 */
(function () {
  'use strict';

  var MENSAGENS = {
    equipado: 'Item equipado.',
    desequipado: 'Item desequipado.',
    sintonizado: 'Item sintonizado.',
    dessintonizado: 'Item dessintonizado.',
    slot_ocupado: 'Este slot já está ocupado.',
    limite_sintonizacao: 'Limite de itens sintonizados atingido.',
    nao_equipavel: 'Este item não é equipável.',
    item_invalido: 'Item indisponível.'
  };

  function setHtml(selector, html) {
    var el = document.querySelector(selector);
    if (el && typeof html === 'string') el.innerHTML = html;
  }

  function setText(selector, value) {
    var el = document.querySelector(selector);
    if (el && value !== undefined && value !== null) el.textContent = value;
  }

  function feedback(mensagem, ok) {
    var el = document.querySelector('[data-mochila-feedback]');
    if (!el) return;
    el.textContent = mensagem || '';
    el.hidden = !mensagem;
    el.classList.toggle('is-ok', !!ok);
    el.classList.toggle('is-err', !ok);
  }

  function aplicar(payload) {
    setHtml('[data-mochila-lista]', payload.inventario_html);
    // A grade e os blocos da aba Ficha vêm inteiros — o wrapper é substituído.
    var grade = document.querySelector('[data-slots-grid]');
    if (grade && typeof payload.slots_html === 'string') grade.outerHTML = payload.slots_html;
    var attuned = document.querySelector('[data-attuned-block]');
    if (attuned && typeof payload.sintonizados_html === 'string') attuned.outerHTML = payload.sintonizados_html;
    var equipados = document.querySelector('[data-equipados-block]');
    if (equipados && typeof payload.equipados_html === 'string') equipados.outerHTML = payload.equipados_html;

    // Carteira: três caixinhas PO | PP | PC. Quem decompõe é o servidor (home/moeda.py) —
    // o JS só escreve os números que vieram em `carteira_moedas`.
    var moedas = payload.carteira_moedas;
    if (moedas) {
      setText('[data-carteira-po]', moedas.po);
      setText('[data-carteira-pp]', moedas.pp);
      setText('[data-carteira-pc]', moedas.pc);
      var carteira = document.querySelector('[data-carteira]');
      if (carteira && payload.carteira_display) carteira.title = payload.carteira_display;
    }
    setText('[data-mochila-total]', payload.total_display);
    setText('[data-mochila-peso]', payload.peso_total);
    if (payload.sintonizacao_maxima) {
      setText('[data-sintonizados-count]',
        String(payload.sintonizados_usados || 0) + '/' + payload.sintonizacao_maxima);
    }
    if (payload.ficha) {
      setText('[data-ficha-ca]', payload.ficha.ca);
      setText('[data-ficha-pv]', payload.ficha.pv_maximo);
    }
    var livres = document.querySelector('[data-slots-livres]');
    if (livres) {
      var n = document.querySelectorAll('[data-slots-grid] .slot-cell.is-free').length;
      livres.textContent = n + (n === 1 ? ' livre' : ' livres');
    }
  }

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('form[data-mochila-form]');
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
      return response.json().then(function (payload) {
        aplicar(payload);
        // `detalhe` nomeia o slot e o item que já está nele; o genérico é o fallback.
        feedback(payload.detalhe || MENSAGENS[payload.msg]
          || (response.ok ? 'Mochila atualizada.' : 'Não foi possível atualizar o item.'),
          response.ok && payload.ok !== false);
      });
    }).catch(function () {
      feedback('Falha de rede ao atualizar a mochila.', false);
    }).then(function () {
      if (button && document.body.contains(button)) button.disabled = false;
    });
  });
})();
