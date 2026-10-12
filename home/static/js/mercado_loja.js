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
  var soFavoritos = root.querySelector('[data-shop-favorites]');
  var countEl = root.querySelector('[data-shop-count]');
  var noResult = root.querySelector('[data-shop-noresult]');
  var detalhe = root.querySelector('[data-shop-detail]');
  var carteira = root.querySelector('[data-shop-carteira]');
  var feedback = root.querySelector('[data-shop-feedback]');
  var vendaBox = root.querySelector('[data-shop-venda]');

  var aba = 'comprar';
  var buscaEmEdicao = false;
  var filtrosUrl = [
    ['busca', busca, ''], ['grupo', selGrupo, 'todas'],
    ['raridade', selRaridade, 'todas'], ['sintonizacao', selSintonizacao, 'todas'],
    ['ordem', selOrdem, 'nome-asc']
  ];

  function salvarNavegacao(criarEntrada) {
    var url = new URL(window.location.href);
    filtrosUrl.forEach(function (filtro) {
      var valor = filtro[1] ? filtro[1].value.trim() : filtro[2];
      if (valor && valor !== filtro[2]) url.searchParams.set(filtro[0], valor);
      else url.searchParams.delete(filtro[0]);
    });
    if (soFavoritos && soFavoritos.checked) url.searchParams.set('favoritos', '1');
    else url.searchParams.delete('favoritos');
    var selecionado = aba === 'comprar' ? linhaAtiva() : null;
    if (selecionado) url.searchParams.set('item', selecionado.getAttribute('data-target'));
    else url.searchParams.delete('item');
    if (url.href !== window.location.href) {
      history[criarEntrada ? 'pushState' : 'replaceState'](history.state, '', url.href);
    }
  }

  function restaurarNavegacao() {
    var params = new URL(window.location.href).searchParams;
    filtrosUrl.forEach(function (filtro) {
      var campo = filtro[1];
      if (!campo) return;
      var valor = params.get(filtro[0]) || filtro[2];
      if (campo.tagName === 'SELECT' && !toArr(campo.options).some(function (opcao) { return opcao.value === valor; })) {
        valor = filtro[2];
      }
      campo.value = valor;
    });
    if (soFavoritos) soFavoritos.checked = params.get('favoritos') === '1';
    linhasDe(paneDe('comprar')).forEach(function (r) {
      r.classList.remove('is-selected');
      r.setAttribute('aria-selected', 'false');
    });
    aplicarFiltros();
    var alvo = params.get('item');
    var row = alvo && linhasDe(paneDe('comprar')).find(function (r) {
      return r.getAttribute('data-target') === alvo && !r.closest('li').hidden;
    });
    if (row) selecionar(row, true);
  }

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
      if (typeof renderBonfireMarkdownElement === 'function') {
        renderBonfireMarkdownElement(el, fonte);
      } else {
        // Sem o renderizador seguro, manter o texto literal em vez de inserir HTML.
        el.textContent = fonte;
      }
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
      if (aba === 'comprar') salvarNavegacao(true);
    }
  }

  /* Garante que o painel nunca fique vazio: se ninguém está selecionado (ou o
     selecionado saiu do filtro), pega a primeira linha visível. */
  function garantirSelecao() {
    var atual = linhaAtiva();
    if (atual && !atual.closest('li').hidden) return;
    var primeira = visiveis()[0];
    if (primeira) { selecionar(primeira, true); return; }
    if (atual) {
      atual.classList.remove('is-selected');
      atual.setAttribute('aria-selected', 'false');
    }
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
      if (ok && soFavoritos && soFavoritos.checked) ok = row.getAttribute('data-favorite') === 'true';
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

  function mudouFiltro(criarEntrada) {
    aplicarFiltros();
    salvarNavegacao(criarEntrada);
  }
  if (busca) {
    busca.addEventListener('input', function () {
      mudouFiltro(!buscaEmEdicao);
      buscaEmEdicao = true;
    });
    busca.addEventListener('blur', function () { buscaEmEdicao = false; });
  }
  [selGrupo, selRaridade, selSintonizacao, selOrdem, soFavoritos].forEach(function (campo) {
    if (campo) campo.addEventListener('change', function () { mudouFiltro(true); });
  });
  window.addEventListener('popstate', function () {
    buscaEmEdicao = false;
    restaurarNavegacao();
  });

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
    var editor = ev.target.closest('.mkt-inline-editor');
    if (editor && ev.target.closest('[data-item-editor-cancel]')) {
      var editForm = editor.querySelector('[data-item-editor]');
      if (editForm && editForm.getAttribute('aria-busy') !== 'true') {
        editForm.reset();
        var status = editForm.querySelector('[data-item-editor-status]');
        status.textContent = '';
        status.hidden = true;
        editor.open = false;
        editor.querySelector('summary').focus();
      }
      return;
    }
    if (editor && ev.target.closest('summary') && editor.querySelector('[data-item-editor][aria-busy="true"]')) {
      ev.preventDefault();
      return;
    }
    var t = ev.target.closest('[data-shop-tab], [data-mkt-row], [data-shop-sheet-close]');
    if (!t) return;
    if (t.hasAttribute('data-shop-sheet-close')) { abrirFolha(false); return; }
    if (t.hasAttribute('data-shop-tab')) { abrirAba(t.getAttribute('data-shop-tab')); return; }
    selecionar(t, false);
  });

  /* ───────────── teclado: ↑↓ andam na lista, Esc fecha a folha ───────────── */
  root.addEventListener('keydown', function (ev) {
    var editor = ev.target.closest('.mkt-inline-editor');
    if (ev.key === 'Escape' && editor && editor.open) {
      ev.preventDefault();
      var editForm = editor.querySelector('[data-item-editor]');
      if (editForm.getAttribute('aria-busy') !== 'true') {
        editor.querySelector('[data-item-editor-cancel]').click();
      }
      return;
    }
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
    var personagemAtivo = seletor.value;
    var trocaSequencia = 0;
    var trocaPendente = false;
    history.replaceState(Object.assign({}, history.state, { mercadoPersonagem: personagemAtivo }), '');

    function travarNegocios(travar) {
      toArr(root.querySelectorAll('[data-shop-buy] button[type="submit"], [data-shop-sell] button[type="submit"]'))
        .forEach(function (button) { button.disabled = travar; });
    }

    function trocarPersonagem(id, registrarHistorico) {
      var sequencia = ++trocaSequencia;
      trocaPendente = true;
      travarNegocios(true);
      var url = new URL(window.location.href);
      url.searchParams.set('personagem', id);
      fetch(url.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
        .then(function (response) {
          if (!response.ok) throw new Error('Falha ao carregar o personagem.');
          return response.text();
        }).then(function (html) {
          if (sequencia !== trocaSequencia) return;
          var pagina = new DOMParser().parseFromString(html, 'text/html');
          var novaLoja = pagina.querySelector('[data-shop-root]');
          var novoSeletor = novaLoja && novaLoja.querySelector('[data-shop-personagem]');
          var novaCarteira = novaLoja && novaLoja.querySelector('[data-shop-carteira]');
          var novaVenda = novaLoja && novaLoja.querySelector('[data-shop-venda]');
          var novaStore = novaLoja && novaLoja.querySelector('.mkt-store');
          var store = root.querySelector('.mkt-store');
          if (!novoSeletor || !novaCarteira || !novaVenda || !novaStore || !store || !carteira || !vendaBox) {
            throw new Error('Balcão indisponível.');
          }
          personagemAtivo = novoSeletor.value;
          seletor.value = personagemAtivo;
          carteira.textContent = novaCarteira.textContent;
          vendaBox.innerHTML = novaVenda.innerHTML;
          store.innerHTML = novaStore.innerHTML;
          var atual = linhaAtiva();
          if (atual) selecionar(atual, true);
          else garantirSelecao();
          if (registrarHistorico) {
            url.searchParams.set('personagem', personagemAtivo);
            history.pushState(Object.assign({}, history.state, { mercadoPersonagem: personagemAtivo }), '', url.href);
          }
          trocaPendente = false;
          travarNegocios(false);
          avisar('Personagem ativo: ' + novoSeletor.selectedOptions[0].textContent + '.', true);
        }).catch(function () {
          if (sequencia !== trocaSequencia) return;
          seletor.value = personagemAtivo;
          trocaPendente = false;
          travarNegocios(false);
          avisar('Não foi possível trocar o personagem. Tente novamente.', false);
        });
    }

    seletor.addEventListener('change', function () {
      trocarPersonagem(seletor.value, true);
    });
    var pickerForm = seletor.closest('form');
    if (pickerForm) pickerForm.addEventListener('submit', function (event) {
      event.preventDefault();
      if (seletor.value !== personagemAtivo && !trocaPendente) trocarPersonagem(seletor.value, true);
    });
    window.addEventListener('popstate', function (event) {
      var anterior = event.state && event.state.mercadoPersonagem;
      if (anterior && anterior !== personagemAtivo) trocarPersonagem(anterior, false);
    });
  }

  /* ─────────────────── compra e venda por fetch ─────────────────── */
  var MSG = {
    saldo: 'Saldo insuficiente para esta compra.',
    invalido: 'Mercadoria indisponível para negócio.',
    sem_preco: 'Este item não tem preço de catálogo — não dá para vender.',
    base_item: 'Escolha o item-base antes de comprar esta variante.'
  };

  function avisar(texto, ok) {
    if (!feedback) return;
    feedback.textContent = texto;
    feedback.hidden = false;
    feedback.classList.toggle('is-ok', !!ok);
    feedback.classList.toggle('is-err', !ok);
  }

  root.addEventListener('submit', function (ev) {
    var form = ev.target.closest('form[data-item-editor]');
    if (!form) return;
    ev.preventDefault();
    if (form.getAttribute('aria-busy') === 'true') return;
    var status = form.querySelector('[data-item-editor-status]');
    var controls = toArr(form.querySelectorAll('input, select, textarea, button'));
    var body = new FormData(form);
    status.setAttribute('role', 'status');
    status.textContent = 'Salvando...';
    status.hidden = false;
    form.setAttribute('aria-busy', 'true');
    controls.forEach(function (control) { control.disabled = true; });
    fetch(form.action, { method: 'POST', body: body, credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) return response.text().then(function (message) {
          throw new Error(message || 'Não foi possível salvar o item.');
        });
        window.location.assign(response.url);
      })
      .catch(function (error) {
        status.setAttribute('role', 'alert');
        status.textContent = error.message || 'Não foi possível salvar o item.';
        status.focus();
      })
      .finally(function () {
        form.removeAttribute('aria-busy');
        controls.forEach(function (control) { control.disabled = false; });
      });
  });

  root.addEventListener('submit', function (ev) {
    var favoriteForm = ev.target.closest('form[data-shop-favorite]');
    if (favoriteForm) {
      ev.preventDefault();
      if (favoriteForm.getAttribute('aria-busy') === 'true') return;
      var favoriteButton = favoriteForm.querySelector('button[type="submit"]');
      var favoriteInput = favoriteForm.querySelector('input[name="favorite"]');
      var favoriteBody = new FormData(favoriteForm);
      favoriteForm.setAttribute('aria-busy', 'true');
      favoriteButton.disabled = true;
      fetch(favoriteForm.action, {
        method: 'POST', body: favoriteBody, credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': favoriteBody.get('csrfmiddlewaretoken') || '' }
      }).then(function (response) {
        if (!response.ok) throw new Error('Não foi possível salvar o favorito.');
        return response.json();
      }).then(function (data) {
        if (!data.ok) throw new Error('Não foi possível salvar o favorito.');
        var saved = !!data.favorite;
        var target = favoriteForm.getAttribute('data-target');
        var row = root.querySelector('[data-mkt-row][data-target="' + target + '"]');
        if (row) row.setAttribute('data-favorite', saved ? 'true' : 'false');
        var template = document.getElementById(target + '-tpl');
        if (template) {
          var storedButton = template.content.querySelector('[data-shop-favorite] button');
          var storedInput = template.content.querySelector('[data-shop-favorite] input[name="favorite"]');
          if (storedButton) {
            storedButton.textContent = saved ? '★ Favorito' : '☆ Salvar favorito';
            storedButton.setAttribute('aria-pressed', saved ? 'true' : 'false');
          }
          if (storedInput) storedInput.value = saved ? 'false' : 'true';
        }
        favoriteButton.textContent = saved ? '★ Favorito' : '☆ Salvar favorito';
        favoriteButton.setAttribute('aria-pressed', saved ? 'true' : 'false');
        favoriteInput.value = saved ? 'false' : 'true';
        aplicarFiltros();
        avisar(saved ? 'Item salvo nos favoritos.' : 'Item removido dos favoritos.', true);
      }).catch(function (error) {
        avisar(error.message || 'Falha de rede ao salvar favorito.', false);
      }).finally(function () {
        favoriteForm.removeAttribute('aria-busy');
        favoriteButton.disabled = false;
      });
      return;
    }
    var form = ev.target.closest('form[data-shop-buy], form[data-shop-sell]');
    if (!form) return;
    ev.preventDefault();
    if (trocaPendente) return;
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

  restaurarNavegacao();      // recupera filtros e destaque de URLs compartilhadas
})();
