/* Mercado — loja MASTER-DETAIL.
 *
 * Uma folha só serve as duas vitrines (mundana e mágica). O que este arquivo faz:
 *   1. filtra a LISTA (busca + loja/categoria + raridade) e mantém a contagem;
 *   2. seleciona uma linha e clona a prévia server-side (<template>) no PAINEL DE
 *      DESTAQUE, renderizando o markdown da descrição;
 *   3. navega a lista pelas setas ↑↓ (Home/End/Enter também);
 *   4. intercepta compra e venda por fetch e atualiza carteira + painel de venda.
 *
 * A MECÂNICA não vive aqui: os endpoints são os mesmos de sempre e devolvem o payload
 * canônico ({ok, msg, carteira_display, venda_html, ...}). Os forms continuam POST
 * clássico quando o JS não roda (fallback progressivo, com `next` de volta à vitrine).
 */
(function () {
  'use strict';

  var root = document.querySelector('[data-shop-root]');
  if (!root || root.dataset.shopInit === '1') return;
  root.dataset.shopInit = '1';

  function toArr(nl) { return Array.prototype.slice.call(nl || []); }
  function norm(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function mobile() { return window.matchMedia('(max-width: 1023px)').matches; }

  var busca = root.querySelector('[data-shop-search]');
  var selGrupo = root.querySelector('[data-shop-group]');
  var selRaridade = root.querySelector('[data-shop-rarity]');
  var selSintonizacao = root.querySelector('[data-shop-attunement]');
  var selOrdem = root.querySelector('[data-shop-sort]');
  var countEl = root.querySelector('[data-shop-count]');
  var noResult = root.querySelector('[data-shop-noresult]');
  var detalhe = root.querySelector('[data-shop-detail]');
  var carteira = root.querySelector('[data-shop-carteira]');
  var feedback = root.querySelector('[data-shop-feedback]');
  var vendaBox = root.querySelector('[data-shop-venda]');

  var aba = 'comprar';

  function paneDe(nome) { return root.querySelector('[data-shop-pane="' + nome + '"]'); }
  function linhasDe(pane) { return pane ? toArr(pane.querySelectorAll('[data-mkt-row]')) : []; }
  function linhaAtiva() { return (paneDe(aba) || root).querySelector('[data-mkt-row].is-selected'); }
  function visiveis() {
    return linhasDe(paneDe(aba)).filter(function (r) { return !r.closest('li').hidden; });
  }

  /* ─────────────────────── PAINEL DE DESTAQUE ─────────────────────── */
  function renderMarkdown(node) {
    toArr(node.querySelectorAll('[data-markdown-source]')).forEach(function (el) {
      if (el.dataset.rendered === '1') return;
      var fonte = el.textContent || '';
      if (typeof renderBonfireMarkdown === 'function') el.innerHTML = renderBonfireMarkdown(fonte);
      else if (window.marked && window.marked.parse) el.innerHTML = window.marked.parse(fonte, { gfm: true, breaks: true });
      el.dataset.rendered = '1';
    });
  }

  function abrirFolha(on) { root.classList.toggle('is-sheet-open', !!on); }

  /* Seleciona uma linha e mostra a prévia. `silencioso` = seleção automática (primeiro
     item, ou o item que sobrou depois de um filtro/venda): não rouba foco nem abre a
     folha do mobile — o painel só nunca fica vazio. */
  function selecionar(row, silencioso) {
    if (!row || !detalhe) return;
    var tpl = document.getElementById(row.getAttribute('data-target') + '-tpl');
    if (!tpl) return;
    linhasDe(paneDe(aba)).forEach(function (r) {
      var on = r === row;
      r.classList.toggle('is-selected', on);
      r.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    detalhe.innerHTML = '';
    detalhe.appendChild(tpl.content.cloneNode(true));
    renderMarkdown(detalhe);
    detalhe.scrollTop = 0;
    if (!silencioso) {
      if (mobile()) abrirFolha(true);
      row.focus({ preventScroll: true });
    }
  }

  /* Garante que o painel nunca fique vazio: se ninguém está selecionado (ou o
     selecionado saiu do filtro), pega a primeira linha visível. */
  function garantirSelecao() {
    var atual = linhaAtiva();
    if (atual && !atual.closest('li').hidden) return;
    var primeira = visiveis()[0];
    if (primeira) { selecionar(primeira, true); return; }
    if (atual) atual.classList.remove('is-selected');
    if (detalhe) {
      detalhe.innerHTML = '<p class="mkt-preview-empty">' + (aba === 'vender'
        ? 'Nada na mochila para vender no balcão.'
        : 'Nenhum item encontrado com esse filtro.') + '</p>';
    }
  }

  /* ─────────────────────────── FILTROS ─────────────────────────── */
  function aplicarFiltros() {
    var pane = paneDe('comprar');
    if (!pane) return;
    var q = norm((busca && busca.value || '').trim());
    var grupo = selGrupo ? selGrupo.value : 'todas';
    var raridade = selRaridade ? selRaridade.value : 'todas';
    var sintonizacao = selSintonizacao ? selSintonizacao.value : 'todas';
    var total = 0;
    linhasDe(pane).forEach(function (row) {
      var ok = true;
      if (grupo !== 'todas') ok = row.getAttribute('data-group') === grupo;
      if (ok && raridade !== 'todas') ok = row.getAttribute('data-rarity') === raridade;
      if (ok && sintonizacao !== 'todas') ok = row.getAttribute('data-attunement') === sintonizacao;
      if (ok && q) ok = norm(row.getAttribute('data-search')).indexOf(q) !== -1;
      row.closest('li').hidden = !ok;
      if (ok) total++;
    });
    if (selOrdem) {
      var list = pane.querySelector('[data-shop-list]');
      var ordem = selOrdem.value || 'nome-asc';
      linhasDe(pane).sort(function (a, b) {
        var av, bv;
        if (ordem.indexOf('preco-') === 0) {
          av = Number(a.getAttribute('data-price') || 0);
          bv = Number(b.getAttribute('data-price') || 0);
        } else if (ordem.indexOf('raridade-') === 0) {
          av = Number(a.getAttribute('data-rarity-rank') || 0);
          bv = Number(b.getAttribute('data-rarity-rank') || 0);
        } else {
          av = norm(a.getAttribute('data-name'));
          bv = norm(b.getAttribute('data-name'));
        }
        var cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return ordem.slice(-4) === 'desc' ? -cmp : cmp;
      }).forEach(function (row) { if (list) list.appendChild(row.closest('li')); });
    }
    if (countEl) countEl.textContent = total;
    if (noResult) noResult.hidden = total !== 0;
    if (aba === 'comprar') garantirSelecao();
  }

  if (busca) busca.addEventListener('input', aplicarFiltros);
  if (selGrupo) selGrupo.addEventListener('change', aplicarFiltros);
  if (selRaridade) selRaridade.addEventListener('change', aplicarFiltros);
  if (selSintonizacao) selSintonizacao.addEventListener('change', aplicarFiltros);
  if (selOrdem) selOrdem.addEventListener('change', aplicarFiltros);

  /* ─────────────────────── abas Comprar / Vender ─────────────────────── */
  function abrirAba(nome) {
    aba = nome;
    toArr(root.querySelectorAll('[data-shop-tab]')).forEach(function (t) {
      var on = t.getAttribute('data-shop-tab') === nome;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    toArr(root.querySelectorAll('[data-shop-pane]')).forEach(function (p) {
      p.hidden = p.getAttribute('data-shop-pane') !== nome;
    });
    abrirFolha(false);
    garantirSelecao();
  }

  /* ─────────────────────────── cliques ─────────────────────────── */
  root.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-shop-tab], [data-mkt-row], [data-shop-sheet-close]');
    if (!t) return;
    if (t.hasAttribute('data-shop-sheet-close')) { abrirFolha(false); return; }
    if (t.hasAttribute('data-shop-tab')) { abrirAba(t.getAttribute('data-shop-tab')); return; }
    selecionar(t, false);
  });

  /* ───────────── teclado: ↑↓ andam na lista, Esc fecha a folha ───────────── */
  root.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { abrirFolha(false); return; }
    var passo = ev.key === 'ArrowDown' ? 1 : ev.key === 'ArrowUp' ? -1 : 0;
    var extremo = ev.key === 'Home' ? 'first' : ev.key === 'End' ? 'last' : '';
    if (!passo && !extremo) return;
    // Dentro da busca as setas navegam a lista; dentro de outro campo (quantidade,
    // selects) elas continuam sendo do campo.
    var dentroDeCampo = ev.target.closest('input, select, textarea');
    if (dentroDeCampo && dentroDeCampo !== busca) return;
    var lista = visiveis();
    if (!lista.length) return;
    ev.preventDefault();
    var alvo;
    if (extremo) alvo = extremo === 'first' ? lista[0] : lista[lista.length - 1];
    else {
      var i = lista.indexOf(linhaAtiva());
      alvo = lista[Math.max(0, Math.min(lista.length - 1, i + passo))];
    }
    selecionar(alvo, false);
    alvo.scrollIntoView({ block: 'nearest' });
  });

  /* ─────────────────── troca de personagem ativo ─────────────────── */
  var seletor = root.querySelector('[data-shop-personagem]');
  if (seletor) {
    seletor.addEventListener('change', function () {
      var form = seletor.closest('form');
      if (form) form.submit();
    });
  }

  /* ─────────────────── compra e venda por fetch ─────────────────── */
  var MSG = {
    saldo: 'Saldo insuficiente para esta compra.',
    invalido: 'Mercadoria indisponível para negócio.',
    sem_preco: 'Este item não tem preço de catálogo — não dá para vender.',
    magico_venda: 'Item mágico se anuncia no Mercado da Comunidade, pela Mochila.'
  };

  function avisar(texto, ok) {
    if (!feedback) return;
    feedback.textContent = texto;
    feedback.hidden = false;
    feedback.classList.toggle('is-ok', !!ok);
    feedback.classList.toggle('is-err', !ok);
  }

  root.addEventListener('submit', function (ev) {
    var form = ev.target.closest('form[data-shop-buy], form[data-shop-sell]');
    if (!form) return;
    ev.preventDefault();
    var vendendo = form.hasAttribute('data-shop-sell');
    var btn = form.querySelector('button[type="submit"]');
    var nome = btn ? (btn.getAttribute('data-nome') || 'mercadoria') : 'mercadoria';
    if (btn) btn.disabled = true;
    var fd = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': fd.get('csrfmiddlewaretoken') || '' },
      body: fd,
      credentials: 'same-origin'
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, msg: 'erro' }; });
    }).then(function (data) {
      if (btn && document.body.contains(btn)) btn.disabled = false;
      if (!data || !data.ok) {
        avisar(MSG[data && data.msg] || 'Não foi possível concluir o negócio.', false);
        return;
      }
      if (carteira && data.carteira_display) carteira.textContent = data.carteira_display;
      if (vendaBox && typeof data.venda_html === 'string') {
        // O painel VENDER volta re-renderizado (linhas + templates da prévia): a linha
        // vendida sumiu, então o destaque precisa reassumir o que sobrou.
        vendaBox.innerHTML = data.venda_html;
        if (vendendo) garantirSelecao();
      }
      avisar(vendendo
        ? 'Vendido: ' + nome + ' por ' + (data.credito_display || '') + '. Carteira: ' + (data.carteira_display || '')
        : 'Comprado: ' + nome + '. Carteira: ' + (data.carteira_display || ''), true);
    }).catch(function () {
      if (btn) btn.disabled = false;
      avisar('Falha de rede — o negócio não foi concluído.', false);
    });
  });

  aplicarFiltros();          // conta a vitrine e já destaca o primeiro item
})();
