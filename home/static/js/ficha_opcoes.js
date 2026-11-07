/* Seção OPÇÕES DE CLASSE da ficha (Ficha v2, onda D — aba "Magias & Opções").
 *
 * Duas coisas, as duas por DELEGAÇÃO no documento (a seção é substituída inteira pelo
 * HTML que o servidor devolve, então nada pode depender de listeners presos aos nós):
 *
 *   1. Expandir a descrição completa de uma opção — mesmo padrão da descrição de magia:
 *      o texto cru já veio no HTML e é renderizado como markdown na primeira abertura.
 *   2. Trocar uma opção TROCÁVEL por fetch no endpoint genérico. A resposta traz a seção
 *      re-renderizada pelo servidor — zero regra de trocabilidade duplicada no cliente.
 *   3. Filtrar o seletor de DOIS NÍVEIS: escolher o pai deixa visível só o grupo de
 *      sub-opções dele. Quem sabe quais pares existem é o servidor (os <optgroup> já vêm
 *      prontos e marcados com o pai); o cliente só esconde os outros.
 *
 * Sem JS, o mesmo <form> posta normalmente e o PRG devolve para a aba — e o select filho,
 * que já traz todos os pares agrupados por pai, continua dando conta da troca sozinho.
 */
(function () {
  'use strict';

  function raiz() { return document.querySelector('[data-opcoes-slot]'); }

  function feedback(mensagem, ok) {
    var el = document.querySelector('[data-opcoes-feedback]');
    if (!el) return;
    el.textContent = mensagem || '';
    el.hidden = !mensagem;
    el.classList.toggle('is-ok', !!ok);
    el.classList.toggle('is-err', !ok);
  }

  function renderMarkdown(el) {
    if (el.dataset.renderizado === '1') return;
    var bruto = el.textContent || '';
    if (typeof window.renderBonfireMarkdown === 'function') {
      el.innerHTML = '<div class="bonfire-markdown">' + window.renderBonfireMarkdown(bruto) + '</div>';
    } else {
      el.innerHTML = '<p>' + bruto
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br>') + '</p>';
    }
    el.dataset.renderizado = '1';
  }

  // ---- 1. descrição expansível ----------------------------------------------------
  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest ? ev.target.closest('[data-opcao-toggle]') : null;
    if (!btn) return;
    var chave = btn.getAttribute('data-opcao-toggle');
    var corpo = document.querySelector('[data-opcao-body="' + chave + '"]');
    if (!corpo) return;
    var abrir = corpo.hidden;
    if (abrir) renderMarkdown(corpo);
    corpo.hidden = !abrir;
    btn.setAttribute('aria-expanded', abrir ? 'true' : 'false');
    btn.classList.toggle('open', abrir);
  });

  // ---- 2. seletor de dois níveis (pai → sub-opção) ---------------------------------
  function filtrarFilho(pai, forcarPrimeiro) {
    var form = pai.closest ? pai.closest('form') : null;
    var filho = form ? form.querySelector('[data-opcao-filho]') : null;
    if (!filho) return;
    var grupos = filho.querySelectorAll('optgroup[data-opcao-de]');
    var primeiro = null;
    for (var i = 0; i < grupos.length; i++) {
      var casa = grupos[i].getAttribute('data-opcao-de') === pai.value;
      grupos[i].hidden = !casa;
      grupos[i].disabled = !casa;
      if (casa && !primeiro) primeiro = grupos[i].querySelector('option');
    }
    var atual = filho.options[filho.selectedIndex];
    if (primeiro && (forcarPrimeiro || !atual || atual.parentNode.hidden)) {
      filho.value = primeiro.value;
    }
  }

  function sincronizarDoisNiveis(escopo) {
    var pais = (escopo || document).querySelectorAll('[data-opcao-pai]');
    for (var i = 0; i < pais.length; i++) filtrarFilho(pais[i], false);
  }

  document.addEventListener('change', function (ev) {
    var pai = ev.target.closest ? ev.target.closest('[data-opcao-pai]') : null;
    if (pai) filtrarFilho(pai, true);
  });

  // ---- 3. troca por fetch ---------------------------------------------------------
  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form || !form.matches || !form.matches('[data-opcao-form]')) return;
    ev.preventDefault();
    var slot = raiz();
    if (!slot) return;
    var botao = form.querySelector('button[type="submit"]');
    if (botao) botao.disabled = true;
    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    }).then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, data: data }; });
    }).then(function (res) {
      var data = res.data || {};
      if (data.opcoes_html) {
        slot.innerHTML = data.opcoes_html;
        sincronizarDoisNiveis(slot);      // a seção é nova: refaz o filtro pai→filho
      }
      feedback(data.detalhe || (res.ok ? 'Opção trocada.' : 'Não foi possível trocar.'),
               res.ok && data.ok !== false);
    }).catch(function () {
      feedback('Falha de rede — tente de novo.', false);
      if (botao) botao.disabled = false;
    });
  });

  // estado inicial (o script é `defer`, então o HTML da seção já está no documento)
  sincronizarDoisNiveis(document);
})();
