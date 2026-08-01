/* Experiência DEDICADA de level-up (BG3-like). Um passo por vez, prévia ao vivo e um
   único "Confirmar" que aplica o LOTE (personagem_levelup_aplicar). Reaproveita o contrato
   de cartões do level-up em lote (data-lvl-card / data-lvl-queue / data-lvl-field) e o
   resumo de prévia do criador (data-prev-*). Zero reload entre passos: navegação e prévia
   são 100% client-side + fetch; só o "seletor de classe que avança" recarrega (raro).

   A ação `subir_nivel` (ou `adicionar_classe`, se multiclassar) é semeada e fixa no lote —
   é a razão de ser da página. As demais escolhas se acumulam e podem ser removidas. */
(function () {
  'use strict';
  var SN = window.SN || {};
  var main = document.getElementById('sn-main');
  if (!main || !SN.previewUrl) return;

  var CHOICE_STEPS = ['subclasse', 'asi', 'talento_racial', 'opcoes', 'magias', 'troca_magia'];
  var lote = [];       // [{tipo, payload, key, label, card, fixed}]
  var seq = 0;
  var mode = 'subir';  // 'subir' (nível na classe) | 'mc' (multiclassar)
  var previewTimer = null, okTimer = null;
  var current = 0;
  var talentoPicks = {};
  var talentoPicksEl = document.getElementById('sn-talento-picks');
  if (talentoPicksEl) {
    try { talentoPicks = JSON.parse(talentoPicksEl.textContent || '{}'); } catch (_e) { talentoPicks = {}; }
  }

  // ---- refs ----
  var stepperEl = document.getElementById('sn-stepper');
  var prevBtn = main.querySelector('[data-sn-prev]');
  var nextBtn = main.querySelector('[data-sn-next]');
  var confirmBtn = main.querySelector('[data-sn-confirm]');
  var hintEl = main.querySelector('[data-sn-hint]');
  var feedbackEl = document.getElementById('sn-feedback');
  var statusEl = document.getElementById('sn-prev-status');
  var allSteps = Array.prototype.slice.call(main.querySelectorAll('.cf-step[data-step]'));

  // Passo de MAGIAS prospectivo (third-caster: Cavaleiro/Trapaceiro Arcano). A conjuração vem
  // da subclasse escolhida NESTE passo, então o passo já é renderizado com o pool, mas fica
  // FORA do fluxo até a prévia ao vivo (subclasse no lote) confirmar truques/conhecidas > 0.
  var magiasStep = main.querySelector('.cf-step[data-step="magias"]');
  var magiasProspectiva = !!(magiasStep && magiasStep.dataset.prospectiva === '1');
  var magiasUnlocked = !magiasProspectiva;   // passo não-prospectivo já nasce ativo

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
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': SN.csrf },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json().then(function (j) { return { status: r.status, json: j }; }); });
  }

  // steps visíveis conforme o modo (multiclassar oculta as escolhas do nível)
  function activeSteps() {
    return allSteps.filter(function (s) {
      var slug = s.dataset.step;
      if (mode === 'mc' && CHOICE_STEPS.indexOf(slug) !== -1) return false;
      // passo de magias prospectivo só entra no fluxo quando destravado pela prévia ao vivo
      if (slug === 'magias' && magiasProspectiva && !magiasUnlocked) return false;
      return true;
    });
  }

  // ================= mutações do lote =================
  function addAction(a) { if (a.key && inLote(a.key)) return; lote.push(a); sync(); }
  function addOrReplace(a) { lote = lote.filter(function (x) { return x.key !== a.key; }); lote.push(a); sync(); }
  function removeKey(key) {
    var a = lote.filter(function (x) { return x.key === key; })[0];
    if (a && a.fixed) return;                 // ação-âncora não sai do lote
    lote = lote.filter(function (x) { return x.key !== key; });
    sync();
  }
  function seedAncora() {
    lote = lote.filter(function (a) { return !a.fixed; });
    if (mode === 'mc') return; // a âncora de mc é adicionada pelo botão do cartão
    if (SN.podeSubir) {
      var pay = {}; if (SN.classeId != null) pay.classe = SN.classeId;
      lote.unshift({ tipo: 'subir_nivel', payload: pay, key: 'subir_nivel',
        label: 'Avançar de nível', card: null, fixed: true });
    }
  }

  function sync() { renderCards(); renderStepper(); renderReview(); schedulePreview(); }

  // ================= render dos cartões (contrato do level-up em lote) =================
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
      } else if (type === 'multiclasse') {
        if (addBtn) {
          if (mode === 'mc') { addBtn.classList.add('is-queued-btn'); addBtn.textContent = '✓ multiclassando (cancelar)'; }
          else { addBtn.classList.remove('is-queued-btn'); addBtn.textContent = '+ Multiclassar'; }
        }
      }
    });
  }

  // ================= construção de ações por cartão =================
  function handleQueue(btn) {
    var tipo = btn.dataset.lvlQueue || btn.dataset.lvlAutoQueue;
    var card = btn.closest('[data-lvl-card]');
    if (!card) return;

    if (tipo === 'adicionar_classe') {
      if (mode === 'mc') { // cancela multiclasse -> volta ao avanço normal
        mode = 'subir'; seedAncora(); rebuildStepper(); goTo(0); sync();
        return;
      }
      var scl = fieldOf(card, 'classe');
      if (!scl || !scl.value) { flash(scl); return; }
      mode = 'mc';
      lote = lote.filter(function (a) { return !a.fixed; });         // tira o subir_nivel
      lote = lote.filter(function (a) { return CHOICE_STEP_CARDS(a) === false; }); // limpa escolhas do nível
      lote.unshift({ tipo: 'adicionar_classe', payload: { classe: parseInt(scl.value, 10) },
        key: 'adicionar_classe', label: 'Multiclasse: ' + optText(scl), card: card, fixed: true });
      rebuildStepper(); goTo(activeSteps().length - 1); sync();
      return;
    }

    if (tipo === 'subclasse') {
      var ss = fieldOf(card, 'subclasse');
      if (!ss.value) { flash(ss); return; }
      addOrReplace({ tipo: tipo, payload: { classe: SN.classeId, subclasse: ss.value }, key: 'subclasse', label: 'Subclasse: ' + optText(ss), card: card });
      return;
    }
    if (tipo === 'talento_racial') {
      var nivel = card.dataset.nivel;
      var ts = fieldOf(card, 'talento');
      if (!ts.value) { flash(ts); return; }
      addOrReplace({ tipo: tipo, payload: { nivel: parseInt(nivel, 10), talento: ts.value }, key: 'talento_racial#' + nivel, label: 'Talento N' + nivel + ': ' + optText(ts), card: card });
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
    if (tipo === 'trocar_magia') {
      var rem = fieldOf(card, 'remover'), add = fieldOf(card, 'adicionar');
      if (!rem || !rem.value) { flash(rem); return; }
      if (!add || !add.value) { flash(add); return; }
      addOrReplace({ tipo: 'trocar_magia', payload: { classe: SN.classeId, remover: rem.value, adicionar: add.value },
        key: 'trocar_magia', label: 'Troca: ' + optText(rem) + ' → ' + optText(add), card: card });
      return;
    }
  }

  // ASI/Talento SEM botão "Escolher" (leva 4, item 7): cada cartão vale UM aprimoramento e
  // mexer em qualquer controle dele já enfileira — reajustar substitui, nunca duplica.
  // Cartão ainda incompleto (modo talento sem talento escolhido) simplesmente sai do lote,
  // sem piscar erro: quem está no meio da escolha não levou clique nenhum para chegar aqui.
  function queueAsi(card) {
    var key = 'asi#' + (card.dataset.slot || '0');
    var modoEl = card.querySelector('input[type="radio"]:checked');
    var payload, label;
    if (modoEl && modoEl.value === 'talento') {
      var tal = fieldOf(card, 'talento'), tat = fieldOf(card, 'talento_attr');
      if (!tal || !tal.value) { if (inLote(key)) removeKey(key); return; }
      var picks = {}, incompleto = false;
      card.querySelectorAll('[data-talento-pick]').forEach(function (sel) {
        if (!sel.value) incompleto = true;
        var k = sel.dataset.pickKey;
        if (!picks[k]) picks[k] = [];
        if (sel.value) picks[k].push(sel.value);
      });
      if (incompleto) { if (inLote(key)) removeKey(key); return; }
      payload = { modo: 'talento', talento: tal.value, talento_attr: tat.value, talento_picks: picks };
      label = optText(tal) + ' (+1 ' + tat.value + ')';
    } else {
      var a1 = fieldOf(card, 'asi_attr_1'), a2 = fieldOf(card, 'asi_attr_2');
      payload = { asi_attr_1: a1.value, asi_attr_2: a2.value };
      label = a1.value === a2.value ? ('+2 ' + a1.value) : ('+1 ' + a1.value + ' / +1 ' + a2.value);
    }
    addOrReplace({ tipo: 'asi', payload: payload, key: key, label: label, card: card });
  }

  function renderTalentoPicks(card, talentoId) {
    var host = card.querySelector('[data-lvl-talento-picks]');
    if (!host) return;
    host.innerHTML = '';
    var grupos = talentoPicks[String(talentoId || '')] || [];
    grupos.forEach(function (g) {
      for (var i = 0; i < (+g.n || 0); i++) {
        var label = document.createElement('label');
        label.className = 'lvl-card__row';
        label.textContent = g.label + ((+g.n || 0) > 1 ? ' ' + (i + 1) : '') + ' ';
        var sel = document.createElement('select');
        sel.className = 'lvl-field lvl-field--grow';
        sel.dataset.talentoPick = '1';
        sel.dataset.pickKey = g.key;
        var empty = document.createElement('option');
        empty.value = ''; empty.textContent = '— Escolha —'; sel.appendChild(empty);
        (g.options || []).forEach(function (o) {
          var option = document.createElement('option');
          option.value = o.val; option.textContent = o.nome; sel.appendChild(option);
        });
        label.appendChild(sel);
        host.appendChild(label);
      }
    });
    host.hidden = !grupos.length;
  }

  // uma ação pertence a um cartão de escolha do nível? (p/ limpar ao multiclassar)
  function CHOICE_STEP_CARDS(a) {
    if (!a.card) return true;   // âncoras já removidas antes
    return ['subclasse', 'talento_racial', 'asi', 'opcao', 'aprender_magias', 'trocar_magia'].indexOf(a.card.dataset.lvlCard) === -1;
  }

  function rebuildMagias(card) {
    var t = [].map.call(card.querySelectorAll('[data-lvl-group="truques"] input:checked'), function (i) { return i.value; });
    var m = [].map.call(card.querySelectorAll('[data-lvl-group="magias"] input:checked'), function (i) { return i.value; });
    if (t.length || m.length) addOrReplace({ tipo: 'aprender_magias', payload: { classe: SN.classeId, truques: t, magias: m }, key: 'aprender_magias', label: 'Magias: ' + (t.length + m.length), card: card });
    else removeKey('aprender_magias');
  }

  // ================= stepper =================
  function stepComplete(stepEl) {
    var badges = stepEl.querySelectorAll('[data-lvl-badge]');
    if (!badges.length) return stepEl.dataset.step !== 'revisar';
    for (var i = 0; i < badges.length; i++) { if (!badges[i].classList.contains('is-ok')) return false; }
    return true;
  }
  function rebuildStepper() {
    var steps = activeSteps();
    if (current >= steps.length) current = steps.length - 1;
    renderStepper();
    showCurrent();
  }
  function renderStepper() {
    var steps = activeSteps();
    stepperEl.innerHTML = steps.map(function (s, i) {
      var done = i < current && stepComplete(s);
      var cls = 'cf-step-tab' + (i === current ? ' is-current' : '') + (done ? ' is-complete' : '');
      return '<li class="' + cls + '" data-sn-tab="' + i + '" role="button" tabindex="0">' +
        '<span class="cf-step-badge"><span>' + (i + 1) + '</span></span>' +
        '<span class="cf-step-name">' + esc(s.dataset.stepName || s.dataset.step) + '</span></li>';
    }).join('');
  }
  function showCurrent() {
    var steps = activeSteps();
    allSteps.forEach(function (s) { s.hidden = true; });
    if (!steps.length) return;
    if (current < 0) current = 0; if (current >= steps.length) current = steps.length - 1;
    steps[current].hidden = false;
    var last = current === steps.length - 1;
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.hidden = last;
    if (confirmBtn) confirmBtn.hidden = !last;
    if (hintEl) {
      var s = steps[current];
      hintEl.textContent = (s.dataset.step === 'revisar')
        ? (lote.length + ' escolha(s) no lote')
        : (stepComplete(s) ? '' : (s.dataset.stepRequired ? 'escolha para continuar (ou avance e volte depois)' : 'opcional'));
    }
    renderStepper();
    try { main.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (e) {}
  }
  function goTo(i) { current = i; showCurrent(); }
  function goNext() { if (current < activeSteps().length - 1) goTo(current + 1); }
  function goPrev() { if (current > 0) goTo(current - 1); }

  // ================= revisão =================
  function renderReview() {
    var list = document.getElementById('sn-review-list');
    if (!list) return;
    if (!lote.length) { list.innerHTML = '<span class="cf-prev-empty">Nenhuma escolha adicional — só o avanço de nível.</span>'; return; }
    list.innerHTML = lote.map(function (a) {
      if (a.fixed) return '<span class="lvl-chip is-anchor">' + esc(a.label) + '</span>';
      return '<span class="lvl-chip">' + esc(a.label) +
        ' <button type="button" class="lvl-chip__x" data-key="' + esc(a.key) + '" aria-label="Remover">×</button></span>';
    }).join('');
  }

  // ================= prévia ao vivo (resumo do criador) =================
  function chips(arr) {
    if (!arr || !arr.length) return '<span class="cf-prev-empty">—</span>';
    return '<div class="cf-prev-chips">' + arr.map(function (x) { return '<span class="cf-chip">' + esc(x) + '</span>'; }).join('') + '</div>';
  }
  function buildExtra(pv) {
    var h = '';
    var pers = (pv.pericias || []).map(function (p) { return p.nome + (p.expertise ? ' ◆' : ''); });
    h += '<div class="cf-prev-sec"><div class="h">Perícias proficientes</div>' + chips(pers) + '</div>';
    if ((pv.prof_arma || []).length) h += '<div class="cf-prev-sec"><div class="h">Armas</div>' + chips(pv.prof_arma) + '</div>';
    if ((pv.idiomas || []).length) h += '<div class="cf-prev-sec"><div class="h">Idiomas</div>' + chips(pv.idiomas) + '</div>';
    var extras = [];
    if (pv.n_magias) extras.push(pv.n_magias + ' magia(s)');
    if (pv.n_features) extras.push(pv.n_features + ' traço(s)/feature(s)');
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
  function pendItems(pend) {
    var items = [];
    if (!pend) return items;
    if (pend.subclasse) items.push('subclasse');
    if (pend.asi_pendentes) items.push(pend.asi_pendentes + ' ASI');
    (pend.talento_racial_niveis || []).forEach(function (n) { items.push('talento racial N' + n); });
    if (pend.opcoes_pendentes) items.push(pend.opcoes_pendentes + ' opção(ões)');
    if (pend.cantrips_pend) items.push(pend.cantrips_pend + ' truque(s)');
    if (pend.known_pend) items.push(pend.known_pend + ' magia(s)');
    return items;
  }
  // Destrava/atualiza o passo de magias prospectivo conforme a prévia ao vivo (que já aplicou
  // a subclasse escolhida no lote). Sem subclasse conjuradora, cantrips/known voltam a 0 e o
  // passo some do fluxo — a seleção pendente é limpa p/ não vazar no lote.
  function syncMagiasProspectiva(pend) {
    if (!magiasProspectiva || !magiasStep) return;
    var card = magiasStep.querySelector('[data-lvl-card="aprender_magias"]');
    var cant = pend ? (+pend.cantrips_pend || 0) : 0;
    var known = pend ? (+pend.known_pend || 0) : 0;
    if (card) { card.dataset.cantrips = cant; card.dataset.known = known; }
    var unlock = cant > 0 || known > 0;
    if (unlock !== magiasUnlocked) {
      magiasUnlocked = unlock;
      if (!unlock) {  // trocou p/ subclasse não-conjuradora: limpa seleção e tira do lote
        if (card) [].forEach.call(card.querySelectorAll('input[type="checkbox"]:checked'),
          function (b) { b.checked = false; });
        lote = lote.filter(function (a) { return a.key !== 'aprender_magias'; });
        renderReview();
      }
      if (current >= activeSteps().length) current = activeSteps().length - 1;
      renderStepper(); showCurrent();
    }
    renderCards();  // re-enforça contagens/badge com os novos data-cantrips/known
  }

  function applyPend(pend) {
    syncMagiasProspectiva(pend);
    var secEl = document.querySelector('[data-prev-pend-sec]'), box = document.querySelector('[data-prev-pend]');
    var items = pendItems(pend);
    if (box) box.innerHTML = items.length ? items.map(function (x) { return '<span class="lvl-badge">' + esc(x) + '</span>'; }).join('') : '<span class="lvl-prev-ok">Sem pendências ✓</span>';
    if (secEl) secEl.hidden = false;
    // espelha na etapa de revisão
    var rp = document.getElementById('sn-review-pend'), rl = document.getElementById('sn-review-pend-list');
    if (rp && rl) { rp.hidden = items.length === 0; rl.innerHTML = items.map(function (x) { return '<span class="lvl-badge">' + esc(x) + '</span>'; }).join(''); }
  }

  function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(runPreview, 280); }
  function runPreview() {
    var mySeq = ++seq;
    if (statusEl) { statusEl.textContent = 'atualizando…'; statusEl.classList.add('is-live'); }
    post(SN.previewUrl, { acoes: acoesPayload() }).then(function (res) {
      if (mySeq !== seq) return;
      var j = res.json;
      if (statusEl) statusEl.classList.remove('is-live');
      if (!j || !j.ready || !j.preview) { if (statusEl) statusEl.textContent = 'estado atual'; return; }
      applyPreview(j.preview);
      applyPend(j.pendencias);
      if (statusEl) statusEl.textContent = 'nível ' + j.preview.nivel + (lote.length > 1 ? (' · ' + (lote.length) + ' no lote') : '');
      if (j.erros && j.erros.length) showErr(j.erros, true);
      else if (feedbackEl && feedbackEl.dataset.kind === 'warn') hideFeedback();
    }).catch(function () {
      if (mySeq !== seq) return;
      if (statusEl) { statusEl.classList.remove('is-live'); statusEl.textContent = 'estado atual'; }
    });
  }

  // ================= feedback =================
  function hideFeedback() { if (feedbackEl) { feedbackEl.hidden = true; feedbackEl.innerHTML = ''; feedbackEl.removeAttribute('data-kind'); } }
  function showErr(erros, soft) {
    if (!feedbackEl) return;
    feedbackEl.dataset.kind = soft ? 'warn' : 'err';
    var listHtml = (erros || []).map(function (e) { return '<li>' + esc(e) + '</li>'; }).join('');
    var title = soft ? 'Algumas escolhas ainda não se aplicam:' : 'Não foi possível confirmar:';
    feedbackEl.innerHTML = '<div class="lvl-err"><strong>' + title + '</strong><ul>' + listHtml + '</ul></div>';
    feedbackEl.hidden = false;
  }

  // ================= confirmar =================
  function doConfirm() {
    if (confirmBtn.disabled) return;
    confirmBtn.disabled = true; if (prevBtn) prevBtn.disabled = true;
    if (statusEl) { statusEl.textContent = 'aplicando…'; statusEl.classList.add('is-live'); }
    post(SN.aplicarUrl, { acoes: acoesPayload() }).then(function (res) {
      if (res.status === 200 && res.json && res.json.ok) {
        if (res.json.continuar) {
          if (feedbackEl) {
            feedbackEl.dataset.kind = 'ok';
            feedbackEl.innerHTML =
              '<div class="lvl-ok"><strong>Nível concluído.</strong> Você ainda tem aventuras ' +
              'para avançar novamente.<div style="margin-top:.7rem;display:flex;gap:.55rem;flex-wrap:wrap">' +
              '<a class="cf-btn cf-btn-primary" href="' + esc(SN.pageUrl + (SN.classeId != null ? '?classe=' + encodeURIComponent(SN.classeId) : '')) + '">Continuar para o nível ' +
              esc(res.json.proximo_nivel) + '</a>' +
              '<a class="cf-btn" href="' + esc(SN.fichaUrl + '?levelup=ok') + '">Voltar à ficha</a></div></div>';
            feedbackEl.hidden = false;
          }
          confirmBtn.hidden = true;
          if (prevBtn) prevBtn.hidden = true;
          if (nextBtn) nextBtn.hidden = true;
          if (statusEl) {
            statusEl.classList.remove('is-live');
            statusEl.textContent = 'nível concluído';
          }
        } else {
          window.location.href = SN.fichaUrl + '?levelup=ok';
        }
      } else {
        showErr((res.json && res.json.erros) || ['Erro desconhecido.'], false);
        confirmBtn.disabled = false; if (prevBtn) prevBtn.disabled = current === 0;
        if (statusEl) statusEl.classList.remove('is-live');
      }
    }).catch(function () {
      showErr(['Falha de rede ao confirmar. Tente novamente.'], false);
      confirmBtn.disabled = false; if (prevBtn) prevBtn.disabled = current === 0;
      if (statusEl) statusEl.classList.remove('is-live');
    });
  }

  // ================= wiring =================
  function initCards() {
    main.querySelectorAll('[data-lvl-queue]').forEach(function (btn) {
      btn.addEventListener('click', function () { handleQueue(btn); });
    });
    // Menus simples enfileiram na própria seleção, sem um segundo clique "Escolher".
    // Mantém a descrição integral visível e limpa o menu para grupos com mais de um slot.
    main.querySelectorAll('select[data-lvl-auto-queue]').forEach(function (field) {
      field.addEventListener('change', function () {
        if (!field.value) return;
        var option = field.options[field.selectedIndex];
        var card = field.closest('[data-lvl-card]');
        var desc = card && card.querySelector('[data-lvl-desc]');
        if (desc) {
          var body = option.dataset.desc || '';
          desc.textContent = option.text.trim() + (body ? (' — ' + body) : '');
          desc.hidden = false;
        }
        handleQueue(field);
        field.value = '';
      });
    });
    main.querySelectorAll('[data-lvl-describe]').forEach(function (field) {
      field.addEventListener('change', function () {
        var option = field.options[field.selectedIndex];
        var card = field.closest('[data-lvl-card]');
        var desc = card && card.querySelector('[data-lvl-desc]');
        if (!desc) return;
        desc.textContent = (option && option.dataset.desc) || '';
        desc.hidden = !desc.textContent;
      });
    });
    // Um cartão por aprimoramento pendente: alternância atributo↔talento, atributos que o
    // talento permite e ENFILEIRAMENTO na própria seleção (sem botão "Escolher").
    main.querySelectorAll('[data-lvl-card="asi"]').forEach(function (asi) {
      var attrsBlock = asi.querySelector('[data-lvl-asi-attrs]'), talBlock = asi.querySelector('[data-lvl-asi-tal]');
      asi.querySelectorAll('input[type="radio"]').forEach(function (r) {
        r.addEventListener('change', function () {
          var talMode = r.value === 'talento' && r.checked;
          if (attrsBlock) attrsBlock.hidden = talMode;
          if (talBlock) talBlock.hidden = !talMode;
        });
      });
      var talSel = fieldOf(asi, 'talento'), attrSel = fieldOf(asi, 'talento_attr');
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
        talSel.addEventListener('change', function () { renderTalentoPicks(asi, talSel.value); });
        renderTalentoPicks(asi, talSel.value);
      }
      // Depois dos ajustes acima (o listener do cartão roda por último na fase de bolha).
      asi.addEventListener('change', function () { queueAsi(asi); });
    });
    main.querySelectorAll('[data-lvl-card="aprender_magias"]').forEach(function (card) {
      card.addEventListener('change', function (e) { if (e.target && e.target.type === 'checkbox') rebuildMagias(card); });
    });
    // TROCA DE MAGIA: espelha o gate do backend (truque↔truque, conhecida↔conhecida). Ao escolher
    // a magia que SAI, restringe o pool que ENTRA à mesma natureza (truque vs. conhecida).
    main.querySelectorAll('[data-lvl-card="trocar_magia"]').forEach(function (card) {
      var rem = fieldOf(card, 'remover'), add = fieldOf(card, 'adicionar');
      if (!rem || !add) return;
      var filtrar = function () {
        var o = rem.options[rem.selectedIndex];
        var t = o ? o.getAttribute('data-truque') : '';
        [].forEach.call(add.options, function (op) {
          if (!op.value) return;
          op.disabled = (t !== '' && t != null) && op.getAttribute('data-truque') !== t;
        });
        var cur = add.options[add.selectedIndex];
        if (cur && cur.disabled) add.value = '';
      };
      rem.addEventListener('change', filtrar); filtrar();
    });
    // Etapas opcionais: botão "Pular" só avança sem semear ação.
    main.querySelectorAll('[data-sn-skip]').forEach(function (b) {
      b.addEventListener('click', function () { goNext(); });
    });
  }

  // remover chip do lote (delegação — cobre cards e a revisão)
  document.addEventListener('click', function (e) {
    var x = e.target.closest('.lvl-chip__x[data-key]');
    if (x) { e.preventDefault(); removeKey(x.dataset.key); }
  });
  // navegação do stepper
  stepperEl.addEventListener('click', function (e) {
    var t = e.target.closest('[data-sn-tab]'); if (t) goTo(parseInt(t.getAttribute('data-sn-tab'), 10));
  });
  stepperEl.addEventListener('keydown', function (e) {
    var t = e.target.closest('[data-sn-tab]');
    if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); goTo(parseInt(t.getAttribute('data-sn-tab'), 10)); }
  });
  if (nextBtn) nextBtn.addEventListener('click', goNext);
  if (prevBtn) prevBtn.addEventListener('click', goPrev);
  if (confirmBtn) confirmBtn.addEventListener('click', doConfirm);

  // seletor de classe que avança -> recarrega (raro; recomputa ganhos/pendências do alvo)
  var classePick = document.getElementById('sn-classe-pick');
  if (classePick) classePick.addEventListener('change', function () {
    window.location.href = SN.pageUrl + '?classe=' + encodeURIComponent(classePick.value);
  });

  // ================= start =================
  seedAncora();
  initCards();
  renderCards();
  showCurrent();
  renderReview();
  runPreview();
})();
