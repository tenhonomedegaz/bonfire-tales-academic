/* Loja da ficha (Mercado) — formato catálogo: alterna Mundano/Mágico, busca por nome,
 * chips de filtro (categoria/raridade/loja) e compra via fetch SEM reload. Os forms de
 * compra funcionam como POST clássico quando o JS não roda (fallback progressivo);
 * aqui interceptamos o submit e atualizamos carteira + inventário na página. */
(function () {
  var root = document.querySelector('[data-loja-root]');
  if (!root || root.dataset.lojaInit === '1') return;
  root.dataset.lojaInit = '1';

  function toArr(nl) { return Array.prototype.slice.call(nl || []); }
  function norm(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }

  var busca = root.querySelector('#loja-busca');
  var countEl = root.querySelector('#loja-count');
  var walletEl = document.getElementById('loja-carteira');
  var feedback = document.getElementById('loja-feedback');
  // A lista de itens saiu desta página na onda B (vive na aba Mochila da ficha); se um dia
  // a loja for embutida ao lado de uma mochila, o container reaparece e volta a atualizar.
  var invContainer = document.querySelector('[data-mochila-lista]');
  var tabs = toArr(root.querySelectorAll('[data-loja-tab]'));
  var chipsets = {
    mundano: root.querySelector('[data-loja-chipset="mundano"]'),
    magico: root.querySelector('[data-loja-chipset="magico"]')
  };
  var lists = {
    mundano: root.querySelector('[data-loja-list="mundano"]'),
    magico: root.querySelector('[data-loja-list="magico"]')
  };

  var state = { shop: 'mundano', cat: 'todos', rarity: 'todos', loja: 'todas' };

  function applyFilters() {
    var q = norm(busca ? busca.value.trim() : '');
    var list = lists[state.shop];
    if (!list) return;
    var cards = toArr(list.querySelectorAll('.loja-card'));
    var shown = 0;
    cards.forEach(function (c) {
      var ok;
      if (state.shop === 'mundano') {
        ok = (state.cat === 'todos' || c.getAttribute('data-cat') === state.cat);
      } else {
        var r = c.getAttribute('data-rarity') || '';
        var lo = c.getAttribute('data-loja') || '';
        ok = (state.rarity === 'todos' || r === state.rarity) &&
             (state.loja === 'todas' || lo === state.loja);
      }
      if (ok && q) ok = norm(c.getAttribute('data-search')).indexOf(q) !== -1;
      c.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    if (countEl) countEl.textContent = shown;
    var nores = list.querySelector('[data-loja-noresult]');
    if (nores) nores.hidden = shown !== 0 || cards.length === 0;
  }

  function switchShop(shop) {
    state.shop = shop;
    tabs.forEach(function (t) {
      var on = t.getAttribute('data-loja-tab') === shop;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    ['mundano', 'magico'].forEach(function (s) {
      if (chipsets[s]) chipsets[s].hidden = s !== shop;
      if (lists[s]) lists[s].hidden = s !== shop;
    });
    applyFilters();
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () { switchShop(t.getAttribute('data-loja-tab')); });
  });

  function wireChips(chipset) {
    if (!chipset) return;
    chipset.addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      var attr = btn.hasAttribute('data-cat') ? 'data-cat'
        : btn.hasAttribute('data-rarity') ? 'data-rarity'
        : btn.hasAttribute('data-loja') ? 'data-loja' : null;
      if (!attr) return;
      var key = attr === 'data-cat' ? 'cat' : attr === 'data-rarity' ? 'rarity' : 'loja';
      state[key] = btn.getAttribute(attr);
      toArr(chipset.querySelectorAll('[' + attr + ']')).forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
      applyFilters();
    });
  }
  wireChips(chipsets.mundano);
  wireChips(chipsets.magico);

  if (busca) busca.addEventListener('input', applyFilters);

  function showFeedback(msg, ok) {
    if (!feedback) return;
    feedback.textContent = msg;
    feedback.hidden = false;
    feedback.classList.toggle('is-ok', !!ok);
    feedback.classList.toggle('is-err', !ok);
  }

  // Compra via fetch (intercepta o submit dos forms de compra)
  root.addEventListener('submit', function (e) {
    var form = e.target.closest('form[data-loja-form]');
    if (!form) return;
    e.preventDefault();
    var btn = form.querySelector('.loja-buy-btn');
    var nome = btn ? (btn.getAttribute('data-nome') || 'item') : 'item';
    if (btn) btn.disabled = true;
    var fd = new FormData(form);
    var csrf = fd.get('csrfmiddlewaretoken') || '';
    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf },
      body: fd,
      credentials: 'same-origin'
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, msg: 'erro' }; });
    }).then(function (data) {
      if (btn) btn.disabled = false;
      if (data && data.ok) {
        if (walletEl && data.carteira_display) walletEl.textContent = data.carteira_display;
        if (invContainer && typeof data.inventario_html === 'string') {
          invContainer.innerHTML = data.inventario_html;
        }
        showFeedback('Comprado: ' + nome + '. Carteira: ' + (data.carteira_display || ''), true);
      } else {
        var m = data && data.msg;
        showFeedback(
          m === 'saldo' ? 'Saldo insuficiente para ' + nome + '.'
          : m === 'invalido' ? 'Item indisponível para compra.'
          : 'Não foi possível concluir a compra.', false);
      }
    }).catch(function () {
      if (btn) btn.disabled = false;
      showFeedback('Falha de rede na compra.', false);
    });
  });

  switchShop('mundano');
})();
