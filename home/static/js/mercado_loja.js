/* Mercado — vitrine de loja (Ficha v2, onda C).
 *
 * Uma folha só serve as duas vitrines (mundana e mágica): busca + chips de prateleira/
 * raridade, detalhe da mercadoria no balcão, compra e venda por fetch. Os forms continuam
 * POST clássico quando o JS não roda (fallback progressivo, com `next` de volta à vitrine);
 * aqui interceptamos o submit e atualizamos carteira + painel de venda sem reload.
 *
 * A MECÂNICA não vive aqui: os endpoints são os mesmos de sempre e devolvem o payload
 * canônico ({ok, msg, carteira_display, venda_html, ...}).
 */
(function () {
  'use strict';

  var root = document.querySelector('[data-shop-root]');
  if (!root || root.dataset.shopInit === '1') return;
  root.dataset.shopInit = '1';

  function toArr(nl) { return Array.prototype.slice.call(nl || []); }
  function norm(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }

  var busca = root.querySelector('[data-shop-search]');
  var chips = root.querySelector('[data-shop-chips]');
  var countEl = root.querySelector('[data-shop-count]');
  var noResult = root.querySelector('[data-shop-noresult]');
  var detalhe = root.querySelector('[data-shop-detail]');
  var carteira = root.querySelector('[data-shop-carteira]');
  var feedback = root.querySelector('[data-shop-feedback]');
  var vendaBox = root.querySelector('[data-shop-venda]');
  var prateleiras = toArr(root.querySelectorAll('[data-shelf]'));

  var estado = { shelf: 'todas', rarity: 'todas', q: '' };

  /* ─────────────────────── filtros da vitrine ─────────────────────── */
  function aplicarFiltros() {
    var q = norm(estado.q.trim());
    var total = 0;
    prateleiras.forEach(function (shelf) {
      var id = shelf.getAttribute('data-shelf');
      var shelfOk = estado.shelf === 'todas' || estado.shelf === id;
      var visiveis = 0;
      toArr(shelf.querySelectorAll('[data-goods]')).forEach(function (card) {
        var ok = shelfOk;
        if (ok && estado.rarity !== 'todas') ok = card.getAttribute('data-rarity') === estado.rarity;
        if (ok && q) ok = norm(card.getAttribute('data-search')).indexOf(q) !== -1;
        card.hidden = !ok;
        if (ok) visiveis++;
      });
      // Prateleira sem nenhuma mercadoria no filtro atual sai da vitrine inteira.
      shelf.hidden = visiveis === 0;
      var vazio = shelf.querySelector('[data-shelf-empty]');
      if (vazio) vazio.hidden = visiveis !== 0;
      total += visiveis;
    });
    if (countEl) countEl.textContent = total;
    if (noResult) noResult.hidden = total !== 0;
  }

  if (busca) {
    busca.addEventListener('input', function () { estado.q = busca.value; aplicarFiltros(); });
  }

  if (chips) {
    chips.addEventListener('click', function (ev) {
      var btn = ev.target.closest('button[data-shelf-filter], button[data-rarity-filter]');
      if (!btn) return;
      var attr = btn.hasAttribute('data-shelf-filter') ? 'data-shelf-filter' : 'data-rarity-filter';
      estado[attr === 'data-shelf-filter' ? 'shelf' : 'rarity'] = btn.getAttribute(attr);
      toArr(chips.querySelectorAll('button[' + attr + ']')).forEach(function (b) {
        b.classList.toggle('is-active', b === btn);
      });
      aplicarFiltros();
    });
  }

  /* ─────────────────── detalhe da mercadoria no balcão ─────────────────── */
  function renderMarkdown(node) {
    toArr(node.querySelectorAll('[data-markdown-source]')).forEach(function (el) {
      if (el.dataset.rendered === '1') return;
      var fonte = el.textContent || '';
      if (typeof renderBonfireMarkdown === 'function') el.innerHTML = renderBonfireMarkdown(fonte);
      else if (window.marked && window.marked.parse) el.innerHTML = window.marked.parse(fonte, { gfm: true, breaks: true });
      el.dataset.rendered = '1';
    });
  }

  function abrirAba(nome) {
    toArr(root.querySelectorAll('[data-shop-tab]')).forEach(function (t) {
      var on = t.getAttribute('data-shop-tab') === nome;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    toArr(root.querySelectorAll('[data-shop-pane]')).forEach(function (p) {
      p.hidden = p.getAttribute('data-shop-pane') !== nome;
    });
  }

  root.addEventListener('click', function (ev) {
    var aba = ev.target.closest('[data-shop-tab]');
    if (aba) { abrirAba(aba.getAttribute('data-shop-tab')); return; }

    var face = ev.target.closest('[data-goods-open]');
    if (!face || !detalhe) return;
    var tpl = document.getElementById(face.getAttribute('data-goods-open') + '-tpl');
    if (!tpl) return;
    toArr(root.querySelectorAll('[data-goods]')).forEach(function (c) {
      c.classList.toggle('is-selected', c.contains(face));
    });
    detalhe.innerHTML = '';
    detalhe.appendChild(tpl.content.cloneNode(true));
    renderMarkdown(detalhe);
    abrirAba('comprar');
    if (window.matchMedia('(max-width: 1099px)').matches) {
      detalhe.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
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
      if (vendaBox && typeof data.venda_html === 'string') vendaBox.innerHTML = data.venda_html;
      avisar(vendendo
        ? 'Vendido: ' + nome + ' por ' + (data.credito_display || '') + '. Carteira: ' + (data.carteira_display || '')
        : 'Comprado: ' + nome + '. Carteira: ' + (data.carteira_display || ''), true);
    }).catch(function () {
      if (btn) btn.disabled = false;
      avisar('Falha de rede — o negócio não foi concluído.', false);
    });
  });

  aplicarFiltros();
})();
