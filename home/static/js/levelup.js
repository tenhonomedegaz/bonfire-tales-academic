/* Level-up em LOTE (editar-ficha). As escolhas de progressão (subir de nível,
   multiclasse, subclasse, ASI/talento, talento racial, opções/perícias de pick e
   novas magias) NÃO gravam na hora: acumulam num lote local com feedback imediato
   (badge "falta X" + chips por cartão). A prévia lateral chama
   personagem_levelup_preview (debounced) e mostra a ficha resultante. "Aplicar" manda
   o lote pra personagem_levelup_aplicar e re-renderiza a área de edição a partir do
   servidor SEM full reload. "Descartar" limpa o lote.

   Compra/venda, inventário, descanso, preparar magias e trocar magia continuam sendo
   POST-redirect normais (grava na hora) — esta fase não os toca. */
(function () {
  'use strict';
  var LVL = window.LVL || {};
  var main = document.getElementById('lvl-main');
  if (!main || !LVL.previewUrl) return;

  var lote = [];        // [{tipo, payload, key, label, card}]
  var uid = 0;          // id incremental p/ ações empilháveis (ASI)
  var seq = 0;          // guarda de corrida da prévia
  var previewTimer = null;
  var okTimer = null;

  // ---- refs recriadas a cada init (ficam dentro de #lvl-main) ----
  var bar, countEl, aplicarBtn, descartarBtn, feedbackEl, statusEl;

  // ================= helpers =================
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
  function optText(sel) { var o = sel && sel.options[sel.selectedIndex]; return o ? o.text.trim() : (sel ? sel.value : ''); }
  function fieldOf(card, name) { return card.querySelector('[data-lvl-field="' + name + '"]'); }
  function inLote(key) { return lote.some(function (a) { return a.key === key; }); }
  function acoesPayload() { return lote.map(function (a) { return { tipo: a.tipo, payload: a.payload }; }); }
  function flash(el) { if (!el) return; el.classList.add('field-invalid'); setTimeout(function () { el.classList.remove('field-invalid'); }, 900); }
  function setText(sel, v) { var e = document.querySelector(sel); if (e) e.textContent = v; }

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': LVL.csrf },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json().then(function (j) { return { status: r.status, json: j }; }); });
  }

  // ================= mutações do lote =================
  function addAction(a) { if (a.key && inLote(a.key)) return; lote.push(a); sync(); }
  function addOrReplace(a) { lote = lote.filter(function (x) { return x.key !== a.key; }); lote.push(a); sync(); }
  function removeKey(key) { lote = lote.filter(function (a) { return a.key !== key; }); sync(); }
  function clearLote() {
    lote = [];
    // desmarca checkboxes de magias (a ação delas deriva do estado marcado)
    main.querySelectorAll('[data-lvl-card="aprender_magias"] input[type="checkbox"]').forEach(function (c) { c.checked = false; });
    sync();
  }

  function sync() { renderCards(); renderBar(); schedulePreview(); }

  // ================= render dos cartões =================
  function chipHtml(a) {
    return '<span class="lvl-chip">' + esc(a.label) +
      ' <button type="button" class="lvl-chip__x" data-key="' + esc(a.key) + '" aria-label="Remover ' + esc(a.label) + '">×</button></span>';
  }
  function setBadge(el, remaining) {
    if (!el) return;
    if (remaining > 0) { el.textContent = 'falta ' + remaining; el.classList.remove('is-ok'); }
    else { el.textContent = 'completo ✓'; el.classList.add('is-ok'); }
  }
  function enforceGroup(card, group, max) {
    var boxes = card.querySelectorAll('[data-lvl-group="' + group + '"] input[type="checkbox"]');
    var n = 0; boxes.forEach(function (b) { if (b.checked) n++; });
    boxes.forEach(function (b) { b.disabled = !b.checked && n >= max; });
    return n;
  }
  function renderMagias(card, badge) {
    var needT = +card.dataset.cantrips || 0, needK = +card.dataset.known || 0;
    var selT = enforceGroup(card, 'truques', needT);
    var selK = enforceGroup(card, 'magias', needK);
    var rem = (needT - selT) + (needK - selK);
    if (badge) {
      var parts = [];
      if (needT) parts.push((needT - selT) + ' truque(s)');
      if (needK) parts.push((needK - selK) + ' magia(s)');
      badge.textContent = rem > 0 ? ('falta ' + parts.join(' · ')) : 'completo ✓';
      badge.classList.toggle('is-ok', rem <= 0);
    }
  }

  function renderCards() {
    main.querySelectorAll('[data-lvl-card]').forEach(function (card) {
      var type = card.dataset.lvlCard;
      var mine = lote.filter(function (a) { return a.card === card; });
      card.classList.toggle('is-queued', mine.length > 0);

      var chipsBox = card.querySelector('[data-lvl-chips]');
      if (chipsBox) {
        if (mine.length) { chipsBox.hidden = false; chipsBox.innerHTML = mine.map(chipHtml).join(''); }
        else { chipsBox.hidden = true; chipsBox.innerHTML = ''; }
      }
      var badge = card.querySelector('[data-lvl-badge]');
      var addBtn = card.querySelector('[data-lvl-queue]');

      if (type === 'subclasse' || type === 'talento_racial') {
        setBadge(badge, 1 - mine.length);
      } else if (type === 'asi' || type === 'opcao') {
        var need = +card.dataset.need || 0;
        var rem = need - mine.length;
        if (badge && need) setBadge(badge, rem);
        if (addBtn) addBtn.disabled = rem <= 0;
      } else if (type === 'aprender_magias') {
        renderMagias(card, badge);
      } else if (type === 'subir' || type === 'multiclasse') {
        var t = type === 'subir' ? 'subir_nivel' : 'adicionar_classe';
        if (addBtn) {
          if (!addBtn.dataset.orig) addBtn.dataset.orig = addBtn.textContent;
          if (inLote(t)) { addBtn.classList.add('is-queued-btn'); addBtn.textContent = '✓ no lote (cancelar)'; }
          else { addBtn.classList.remove('is-queued-btn'); addBtn.textContent = addBtn.dataset.orig; }
        }
      }
    });
  }

  function renderBar() {
    if (!bar) return;
    var n = lote.length;
    if (countEl) countEl.textContent = n;
    bar.hidden = n === 0;
    if (aplicarBtn) aplicarBtn.disabled = n === 0;
  }

  // ================= construção de ações por cartão =================
  function handleQueue(btn) {
    var tipo = btn.dataset.lvlQueue;
    var card = btn.closest('[data-lvl-card]');
    if (!card) return;

    if (tipo === 'subir_nivel' || tipo === 'adicionar_classe') {
      if (inLote(tipo)) { removeKey(tipo); return; }           // toggle
      var scl = fieldOf(card, 'classe');
      var pay = {};
      if (scl) { if (tipo === 'adicionar_classe' && !scl.value) { flash(scl); return; } if (scl.value) pay.classe = parseInt(scl.value, 10); }
      var lbl = (btn.dataset.label || 'Progressão') + (scl && scl.value ? (': ' + optText(scl)) : '');
      addAction({ tipo: tipo, payload: pay, key: tipo, label: lbl, card: card });
      return;
    }

    if (tipo === 'subclasse') {
      var ss = fieldOf(card, 'subclasse');
      if (!ss.value) { flash(ss); return; }
      addOrReplace({ tipo: tipo, payload: { subclasse: ss.value }, key: 'subclasse', label: 'Subclasse: ' + optText(ss), card: card });
      return;
    }

    if (tipo === 'talento_racial') {
      var nivel = card.dataset.nivel;
      var ts = fieldOf(card, 'talento');
      if (!ts.value) { flash(ts); return; }
      addOrReplace({ tipo: tipo, payload: { nivel: parseInt(nivel, 10), talento: ts.value }, key: 'talento_racial#' + nivel, label: 'Talento racial N' + nivel + ': ' + optText(ts), card: card });
      return;
    }

    if (tipo === 'asi') {
      var modoEl = card.querySelector('input[name="lvl-asi-modo"]:checked');
      var modo = modoEl ? modoEl.value : 'asi';
      var payload, label;
      if (modo === 'talento') {
        var tal = fieldOf(card, 'talento'), tat = fieldOf(card, 'talento_attr');
        if (!tal.value) { flash(tal); return; }
        payload = { modo: 'talento', talento: tal.value, talento_attr: tat.value };
        label = optText(tal) + ' (+1 ' + tat.value + ')';
      } else {
        var a1 = fieldOf(card, 'asi_attr_1'), a2 = fieldOf(card, 'asi_attr_2');
        payload = { asi_attr_1: a1.value, asi_attr_2: a2.value };
        label = a1.value === a2.value ? ('+2 ' + a1.value) : ('+1 ' + a1.value + ' / +1 ' + a2.value);
      }
      addAction({ tipo: 'asi', payload: payload, key: 'asi#' + (++uid), label: label, card: card });
      return;
    }

    if (tipo === 'opcao') {
      var vs = fieldOf(card, 'val');
      if (!vs.value) { flash(vs); return; }
      var key = 'opcao#' + card.dataset.slug + '#' + vs.value;
      if (inLote(key)) return;
      addAction({ tipo: 'opcao', payload: { classe: card.dataset.classe, slug: card.dataset.slug, val: vs.value }, key: key, label: optText(vs), card: card });
      return;
    }
  }

  function rebuildMagias(card) {
    var t = [].map.call(card.querySelectorAll('[data-lvl-group="truques"] input:checked'), function (i) { return i.value; });
    var m = [].map.call(card.querySelectorAll('[data-lvl-group="magias"] input:checked'), function (i) { return i.value; });
    if (t.length || m.length) {
      addOrReplace({ tipo: 'aprender_magias', payload: { truques: t, magias: m }, key: 'aprender_magias', label: 'Magias: ' + (t.length + m.length), card: card });
    } else { removeKey('aprender_magias'); }
  }

  // ================= wiring dos cartões (re-executável) =================
  function initCards() {
    main.querySelectorAll('[data-lvl-queue]').forEach(function (btn) {
      btn.addEventListener('click', function () { handleQueue(btn); });
    });

    // ASI: mostrar/ocultar blocos por modo + filtrar atributos válidos do talento
    var asi = document.getElementById('lvl-asi-card');
    if (asi) {
      var attrsBlock = asi.querySelector('[data-lvl-asi-attrs]');
      var talBlock = asi.querySelector('[data-lvl-asi-tal]');
      asi.querySelectorAll('input[name="lvl-asi-modo"]').forEach(function (r) {
        r.addEventListener('change', function () {
          var talMode = r.value === 'talento' && r.checked;
          if (attrsBlock) attrsBlock.hidden = talMode;
          if (talBlock) talBlock.hidden = !talMode;
        });
      });
      var talSel = document.getElementById('lvl-asi-talento'), attrSel = document.getElementById('lvl-asi-talento-attr');
      if (talSel && attrSel) {
        var syncAttr = function () {
          var o = talSel.options[talSel.selectedIndex];
          var allowed = ((o && o.getAttribute('data-attrs')) || '').split(',').filter(Boolean);
          [].forEach.call(attrSel.options, function (op) { op.disabled = allowed.length && allowed.indexOf(op.value) === -1; });
          if (attrSel.options[attrSel.selectedIndex] && attrSel.options[attrSel.selectedIndex].disabled) {
            for (var i = 0; i < attrSel.options.length; i++) { if (!attrSel.options[i].disabled) { attrSel.value = attrSel.options[i].value; break; } }
          }
        };
        talSel.addEventListener('change', syncAttr); syncAttr();
      }
    }

    // Magias: cada mudança de checkbox reconstrói a ação agregada
    main.querySelectorAll('[data-lvl-card="aprender_magias"]').forEach(function (card) {
      card.addEventListener('change', function (e) { if (e.target && e.target.type === 'checkbox') rebuildMagias(card); });
    });

    renderCards();
  }

  // ================= prévia ao vivo =================
  function chips(arr) {
    if (!arr || !arr.length) return '<span class="cf-prev-empty">—</span>';
    return '<div class="cf-prev-chips">' + arr.map(function (x) { return '<span class="cf-chip">' + esc(x) + '</span>'; }).join('') + '</div>';
  }
  function buildExtra(pv) {
    var h = '';
    var pers = (pv.pericias || []).map(function (p) { return p.nome + (p.expertise ? ' ◆' : ''); });
    h += '<div class="cf-prev-sec"><div class="h">Perícias proficientes</div>' + chips(pers) + '</div>';
    if ((pv.prof_arma || []).length) h += '<div class="cf-prev-sec"><div class="h">Armas</div>' + chips(pv.prof_arma) + '</div>';
    if ((pv.prof_armadura || []).length) h += '<div class="cf-prev-sec"><div class="h">Armaduras</div>' + chips(pv.prof_armadura) + '</div>';
    if ((pv.idiomas || []).length) h += '<div class="cf-prev-sec"><div class="h">Idiomas</div>' + chips(pv.idiomas) + '</div>';
    if ((pv.ferramentas || []).length) h += '<div class="cf-prev-sec"><div class="h">Ferramentas</div>' + chips(pv.ferramentas) + '</div>';
    var extras = [];
    if (pv.n_magias) extras.push(pv.n_magias + ' magia(s)');
    if (pv.n_features) extras.push(pv.n_features + ' traço(s)/feature(s)');
    if (pv.iniciativa != null) extras.push('Iniciativa ' + (pv.iniciativa >= 0 ? '+' : '') + pv.iniciativa);
    if (pv.velocidade) extras.push(pv.velocidade + ' de deslocamento');
    if (extras.length) h += '<div class="cf-prev-sec"><div class="h">Resumo</div>' + chips(extras) + '</div>';
    return h;
  }
  function applyPreview(pv) {
    if (!pv) return;
    setText('[data-prev-nivel]', pv.nivel);
    setText('[data-prev-pv]', pv.pv == null ? '—' : pv.pv);
    setText('[data-prev-ca]', pv.ca == null ? '—' : pv.ca);
    setText('[data-prev-pb]', (pv.pb >= 0 ? '+' : '') + pv.pb);
    var attrs = document.querySelector('[data-prev-attrs]');
    if (attrs) attrs.innerHTML = (pv.atributos || []).map(function (a) {
      return '<div class="cf-attr' + (a.save_prof ? ' save-prof' : '') + '"><span class="s">' + a.sig +
        '</span><span class="m">' + (a.mod >= 0 ? '+' : '') + a.mod + '</span><span class="t">' + a.valor + '</span></div>';
    }).join('');
    var extra = document.querySelector('[data-prev-extra]');
    if (extra) extra.innerHTML = buildExtra(pv);
  }
  function applyPend(pend) {
    var secEl = document.querySelector('[data-prev-pend-sec]'), box = document.querySelector('[data-prev-pend]');
    if (!secEl || !box || !pend) return;
    var items = [];
    if (pend.subclasse) items.push('subclasse');
    if (pend.asi_pendentes) items.push(pend.asi_pendentes + ' ASI');
    (pend.talento_racial_niveis || []).forEach(function (n) { items.push('talento racial N' + n); });
    if (pend.opcoes_pendentes) items.push(pend.opcoes_pendentes + ' opção(ões)');
    if (pend.cantrips_pend) items.push(pend.cantrips_pend + ' truque(s)');
    if (pend.known_pend) items.push(pend.known_pend + ' magia(s)');
    box.innerHTML = items.length
      ? items.map(function (x) { return '<span class="lvl-badge">' + esc(x) + '</span>'; }).join('')
      : '<span class="lvl-prev-ok">Sem pendências ✓</span>';
    secEl.hidden = false;
  }

  function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(runPreview, 300); }
  function runPreview() {
    var mySeq = ++seq;
    if (statusEl) { statusEl.textContent = 'atualizando…'; statusEl.classList.add('is-live'); }
    post(LVL.previewUrl, { acoes: acoesPayload() }).then(function (res) {
      if (mySeq !== seq) return;
      var j = res.json;
      if (statusEl) statusEl.classList.remove('is-live');
      if (!j || !j.ready || !j.preview) { if (statusEl) statusEl.textContent = 'estado atual'; return; }
      applyPreview(j.preview);
      applyPend(j.pendencias);
      if (statusEl) statusEl.textContent = lote.length ? ('prévia de ' + lote.length + ' escolha(s)') : 'estado atual';
      if (j.erros && j.erros.length) showErr(j.erros, true);
      else if (feedbackEl && feedbackEl.dataset.kind === 'warn') hideFeedback();
    }).catch(function () {
      if (mySeq !== seq) return;
      if (statusEl) { statusEl.classList.remove('is-live'); statusEl.textContent = 'estado atual'; }
    });
  }

  // ================= feedback =================
  function hideFeedback() { if (feedbackEl) { feedbackEl.hidden = true; feedbackEl.innerHTML = ''; feedbackEl.removeAttribute('data-kind'); } }
  function showOk(msg) {
    if (!feedbackEl) return;
    clearTimeout(okTimer);
    feedbackEl.dataset.kind = 'ok';
    feedbackEl.innerHTML = '<div class="lvl-ok">' + esc(msg) + '</div>';
    feedbackEl.hidden = false;
    okTimer = setTimeout(hideFeedback, 6000);
  }
  function showErr(erros, soft) {
    if (!feedbackEl) return;
    feedbackEl.dataset.kind = soft ? 'warn' : 'err';
    var list = (erros || []).map(function (e) { return '<li>' + esc(e) + '</li>'; }).join('');
    var title = soft ? 'Algumas escolhas do lote não se aplicam ainda:' : 'Não foi possível aplicar:';
    feedbackEl.innerHTML = '<div class="lvl-err"><strong>' + title + '</strong><ul>' + list + '</ul></div>';
    feedbackEl.hidden = false;
  }

  // ================= aplicar =================
  function refreshFromServer(msg) {
    fetch(LVL.pageUrl, { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var fresh = doc.getElementById('lvl-main');
        if (!fresh) { window.location.href = LVL.pageUrl; return; }
        main.innerHTML = fresh.innerHTML;
        runScripts(main);   // re-executa scripts inline (ex.: limite de magias preparadas)
        init();             // re-cacheia refs + re-wire cartões
        runPreview();       // atualiza a prévia lateral a partir do novo estado
        if (msg) showOk(msg);
      })
      .catch(function () { window.location.href = LVL.pageUrl; });
  }
  function runScripts(container) {
    container.querySelectorAll('script').forEach(function (old) {
      var s = document.createElement('script');
      if (old.src) s.src = old.src; else s.textContent = old.textContent;
      old.parentNode.replaceChild(s, old);
    });
  }

  function doAplicar() {
    if (!lote.length || aplicarBtn.disabled) return;
    aplicarBtn.disabled = true; if (descartarBtn) descartarBtn.disabled = true;
    if (statusEl) { statusEl.textContent = 'aplicando…'; statusEl.classList.add('is-live'); }
    post(LVL.aplicarUrl, { acoes: acoesPayload() }).then(function (res) {
      if (res.status === 200 && res.json && res.json.ok) {
        lote = [];
        refreshFromServer('Escolhas aplicadas ✓');
      } else {
        showErr((res.json && res.json.erros) || ['Erro desconhecido.'], false);
        aplicarBtn.disabled = false; if (descartarBtn) descartarBtn.disabled = false;
        if (statusEl) statusEl.classList.remove('is-live');
      }
    }).catch(function () {
      showErr(['Falha de rede ao aplicar. Tente novamente.'], false);
      aplicarBtn.disabled = false; if (descartarBtn) descartarBtn.disabled = false;
      if (statusEl) statusEl.classList.remove('is-live');
    });
  }

  // ================= init / re-init =================
  function cacheEls() {
    bar = document.getElementById('lvl-actionbar');
    countEl = document.getElementById('lvl-count');
    aplicarBtn = document.getElementById('lvl-aplicar');
    descartarBtn = document.getElementById('lvl-descartar');
    feedbackEl = document.getElementById('lvl-feedback');
    statusEl = document.getElementById('lvl-prev-status');
    if (aplicarBtn) aplicarBtn.addEventListener('click', doAplicar);
    if (descartarBtn) descartarBtn.addEventListener('click', function () { clearLote(); hideFeedback(); });
  }
  function init() { cacheEls(); initCards(); renderBar(); }

  // remoção de chip do lote (delegação — sobrevive a re-render de #lvl-main)
  main.addEventListener('click', function (e) {
    var x = e.target.closest('.lvl-chip__x[data-key]');
    if (x) { e.preventDefault(); removeKey(x.dataset.key); }
  });

  init();
  runPreview();  // preenche a prévia com o estado atual (lote vazio)
})();
