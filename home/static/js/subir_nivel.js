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

  var lote = [];       // [{tipo, payload, key, label, card, fixed}]
  var seq = 0;
  var multiclassPayload = JSON.parse(document.getElementById('sn-multiclass').textContent || 'null');
  var mode = multiclassPayload ? 'mc' : 'subir';
  var previewTimer = null, okTimer = null;
  var current = 0;
  var talentoPicks = {};
  var confirmation = null;
  var choicePickers = [];
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
    }).then(function (r) {
      return r.text().then(function (body) {
        var j = null;
        try { j = JSON.parse(body); } catch (_e) { /* HTTP errors can return HTML. */ }
        return { status: r.status, json: j, redirected: r.redirected };
      });
    });
  }

  function confirmationErrors(res) {
    if (res.redirected || res.status === 401) return ['Sua sessão expirou. Entre novamente e recarregue a ficha.'];
    if (res.json && Array.isArray(res.json.erros) && res.json.erros.length) return res.json.erros;
    if (res.status === 403) return ['Confirmação recusada (HTTP 403). Recarregue a página e verifique sua permissão.'];
    if (res.status >= 500) return ['O servidor não conseguiu confirmar (HTTP ' + res.status + '). Recarregue a ficha antes de tentar novamente.'];
    return ['Resposta inválida ao confirmar (HTTP ' + res.status + '). Recarregue a ficha para verificar o estado atual.'];
  }

  // A nova classe usa as mesmas etapas de escolha do avancar normal.
  function activeSteps() {
    return allSteps.filter(function (s) {
      var slug = s.dataset.step;
      // passo de magias prospectivo só entra no fluxo quando destravado pela prévia ao vivo
      if (slug === 'magias' && magiasProspectiva && !magiasUnlocked) return false;
      return true;
    });
  }

  // ================= mutações do lote =================
  function addAction(a) { if (a.key && inLote(a.key)) return; lote.push(a); sync(); }
  function addOrReplace(a) { lote = lote.filter(function (x) { return x.key !== a.key; }); lote.push(a); sync(); }
  function removeKey(key, resetAllocation) {
    var a = lote.filter(function (x) { return x.key === key; })[0];
    if (a && a.fixed) return;                 // ação-âncora não sai do lote
    lote = lote.filter(function (x) { return x.key !== key; });
    if (resetAllocation && a && a.tipo === 'asi' && a.payload.modo !== 'talento' && a.card && a.card.resetAsiAllocation) a.card.resetAsiAllocation();
    sync();
  }
  function seedAncora() {
    lote = lote.filter(function (a) { return !a.fixed; });
    if (mode === 'mc') {
      lote.unshift({ tipo: 'adicionar_classe', payload: multiclassPayload,
        key: 'adicionar_classe', label: 'Multiclasse', card: null, fixed: true });
      return;
    }
    if (SN.podeSubir) {
      var pay = {}; if (SN.classeId != null) pay.classe = SN.classeId;
      lote.unshift({ tipo: 'subir_nivel', payload: pay, key: 'subir_nivel',
        label: 'Avançar de nível', card: null, fixed: true });
    }
  }

  function sync() { renderCards(); choicePickers.forEach(function (refresh) { refresh(); }); renderStepper(); renderReview(); schedulePreview(); }

  function showChoiceDescription(card, option) {
    var host = card && card.querySelector('[data-lvl-desc]');
    if (!host) return;
    host.replaceChildren();
    host.hidden = !option || !option.value;
    if (host.hidden) return;
    var heading = document.createElement('h3');
    heading.textContent = option.text.trim();
    var body = document.createElement('div');
    var raw = option.dataset.desc || '';
    if (typeof renderBonfireMarkdownElement === 'function') {
      renderBonfireMarkdownElement(body, raw);
    } else body.textContent = raw;
    host.append(heading, body);
  }

  // Preserve native values/events and server validation; only replace the presentation.
  function initChoicePickers() {
    main.querySelectorAll('select[data-lvl-auto-queue], select[data-lvl-describe], [data-lvl-card="marco"] select[data-lvl-field="talento"], [data-lvl-card="trocar_opcao"] select[data-lvl-field="val"]').forEach(function (field) {
      var card = field.closest('[data-lvl-card]');
      var picker = document.createElement('details');
      picker.className = 'sn-choice-picker';
      var summary = document.createElement('summary');
      var caption = field.getAttribute('aria-label') || optText(field);
      summary.textContent = caption;
      var search = document.createElement('input');
      search.type = 'search'; search.placeholder = 'Buscar';
      search.setAttribute('aria-label', 'Buscar: ' + caption);
      // Searching is not a mechanical choice (ASI cards listen for bubbled changes).
      search.addEventListener('change', function (event) { event.stopPropagation(); });
      var results = document.createElement('div');
      results.className = 'sn-choice-results';
      var status = document.createElement('p');
      status.className = 'sn-choice-status'; status.setAttribute('role', 'status');
      var entries = [];
      [].forEach.call(field.options, function (option) {
        if (!option.value) return;
        var button = document.createElement('button');
        button.type = 'button'; button.textContent = option.text.trim();
        button.title = option.title;
        button.addEventListener('click', function () {
          if (option.disabled || field.disabled) return;
          field.value = option.value;
          showChoiceDescription(card, option);
          field.dispatchEvent(new Event('change', { bubbles: true }));
          picker.open = false;
          summary.focus();
        });
        results.appendChild(button);
        entries.push({ option: option, button: button });
      });
      function normalize(value) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
      function refresh() {
        var query = normalize(search.value.trim()), shown = 0, selected = [];
        entries.forEach(function (entry) {
          var option = entry.option, button = entry.button;
          var chosen = field.value === option.value || lote.some(function (action) {
            return action.card === card && String(action.payload[field.dataset.lvlField]) === option.value;
          });
          button.hidden = !normalize(option.text).includes(query);
          button.disabled = field.disabled || option.disabled;
          button.setAttribute('aria-pressed', String(chosen));
          if (!button.hidden) shown++;
          if (chosen) selected.push(option.text.trim());
        });
        summary.textContent = selected.length ? selected.join(' / ') : caption;
        status.textContent = shown ? shown + ' opções' : 'Nenhuma opção encontrada';
      }
      search.addEventListener('input', refresh);
      picker.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') { picker.open = false; summary.focus(); }
      });
      field.addEventListener('change', refresh);
      picker.append(summary, search, status, results);
      field.before(picker); field.hidden = true;
      choicePickers.push(refresh); refresh();
    });
  }

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
      if (type === 'subclasse' || type === 'talento_racial' || type === 'marco') {
        setBadge(badge, 1 - mine.length);
      } else if (type === 'asi' || type === 'opcao') {
        var need = +card.dataset.need || 0;
        var rem = need - mine.length;
        if (badge && need) setBadge(badge, rem);
        if (addBtn) addBtn.disabled = rem <= 0;
      } else if (type === 'aprender_magias') {
        renderMagias(card, badge);
      } else if (type === 'magias_concedidas') {
        setBadge(badge, (+card.dataset.need || 0) - enforceGroup(
          card, 'concedidas', +card.dataset.need || 0));
      } else if (type === 'trocar_opcao') {
        if (addBtn) addBtn.disabled = mine.length > 0;
      } else if (type === 'trocar_magia') {
        var quota = +card.dataset.swapRestantes || 0;
        var usadosRem = {}, usadosAdd = {};
        mine.forEach(function (a) {
          usadosRem[a.payload.remover] = true;
          usadosAdd[a.payload.adicionar] = true;
        });
        var remSel = fieldOf(card, 'remover'), addSel = fieldOf(card, 'adicionar');
        if (remSel) [].forEach.call(remSel.options, function (op) {
          op.dataset.queued = usadosRem[op.value] ? '1' : '0';
          if (op.value) op.disabled = !!usadosRem[op.value];
        });
        if (addSel) [].forEach.call(addSel.options, function (op) {
          op.dataset.queued = usadosAdd[op.value] ? '1' : '0';
          if (op.value && usadosAdd[op.value]) op.disabled = true;
        });
        if (remSel && remSel.options[remSel.selectedIndex] && remSel.options[remSel.selectedIndex].disabled) remSel.value = '';
        if (addSel && addSel.options[addSel.selectedIndex] && addSel.options[addSel.selectedIndex].disabled) addSel.value = '';
        if (addBtn) addBtn.disabled = mine.length >= quota;
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
      var hunter = scl.options[scl.selectedIndex].dataset.hunter === '1';
      var ability = fieldOf(card, 'hunter_ability');
      if (hunter && (!ability || !ability.value)) { flash(ability); return; }
      var target = new URL(SN.pageUrl, window.location.href);
      target.searchParams.set('multiclasse', scl.value);
      if (hunter) target.searchParams.set('hunter_ability', ability.value);
      window.location.href = target.href;
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
    if (tipo === 'trocar_opcao') {
      var antiga = fieldOf(card, 'escolha'), nova = fieldOf(card, 'val');
      if (!antiga || !antiga.value) { flash(antiga); return; }
      if (!nova || !nova.value) { flash(nova); return; }
      addOrReplace({ tipo: 'trocar_opcao',
        payload: { classe: card.dataset.classe, escolha: antiga.value, val: nova.value },
        key: 'trocar_opcao#' + card.dataset.classe + '#' + card.dataset.swapKey,
        label: 'Troca: ' + optText(antiga) + ' → ' + optText(nova), card: card });
      return;
    }
    if (tipo === 'trocar_magia') {
      var rem = fieldOf(card, 'remover'), add = fieldOf(card, 'adicionar');
      if (!rem || !rem.value) { flash(rem); return; }
      if (!add || !add.value) { flash(add); return; }
      var swaps = lote.filter(function (a) { return a.card === card && a.tipo === 'trocar_magia'; });
      var quota = +card.dataset.swapRestantes || 0;
      if (swaps.length >= quota) { flash(btn); return; }
      if (swaps.some(function (a) { return a.payload.remover === rem.value || a.payload.adicionar === add.value; })) {
        flash(rem); flash(add); return;
      }
      addAction({ tipo: 'trocar_magia', payload: { classe: SN.classeId, remover: rem.value, adicionar: add.value },
        key: 'trocar_magia#' + rem.value, label: 'Troca: ' + optText(rem) + ' → ' + optText(add), card: card });
      rem.value = ''; add.value = '';
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
      if (!a1.value || !a2.value) { if (inLote(key)) removeKey(key); return; }
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
          option.value = o.val;
          option.textContent = o.nome + (o.ja_proficiente ? ' — já proficiente' : '');
          option.disabled = !!o.ja_proficiente;
          sel.appendChild(option);
        });
        label.appendChild(sel);
        host.appendChild(label);
      }
    });
    host.hidden = !grupos.length;
  }

  // uma ação pertence a um cartão de escolha do nível? (p/ limpar ao multiclassar)
  function rebuildMagias(card) {
    var t = [].map.call(card.querySelectorAll('[data-lvl-group="truques"] input:checked'), function (i) { return i.value; });
    var m = [].map.call(card.querySelectorAll('[data-lvl-group="magias"] input:checked'), function (i) { return i.value; });
    if (t.length || m.length) addOrReplace({ tipo: 'aprender_magias', payload: { classe: SN.classeId, truques: t, magias: m }, key: 'aprender_magias', label: 'Magias: ' + (t.length + m.length), card: card });
    else removeKey('aprender_magias');
  }

  function rebuildMagiasConcedidas(card) {
    var escolhidas = [].map.call(
      card.querySelectorAll('[data-lvl-group="concedidas"] input:checked'),
      function (input) { return input.value; });
    var key = 'magias_concedidas#' + card.dataset.fonte + '#' + card.dataset.slot;
    if (escolhidas.length) {
      addOrReplace({
        tipo: 'magias_concedidas',
        payload: { fonte: card.dataset.fonte, slot: +card.dataset.slot, magias: escolhidas },
        key: key,
        label: card.dataset.fonte + ': ' + escolhidas.length + ' magia(s)',
        card: card
      });
    } else removeKey(key);
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
    if (!lote.length) {
      list.innerHTML = '<span class="cf-prev-empty">' +
        (SN.podeSubir ? 'Nenhuma escolha adicional — só o avanço de nível.' : 'Nenhuma escolha pendente selecionada.') +
        '</span>';
      return;
    }
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
    (pv.atributos || []).forEach(function (attribute) {
      main.querySelectorAll('[data-asi-score="' + attribute.sig + '"]').forEach(function (output) {
        output.textContent = attribute.valor;
      });
    });
  }
  function pendItems(pend) {
    var items = [];
    if (!pend) return items;
    if (pend.subclasse) items.push('subclasse');
    if (pend.asi_pendentes) items.push(pend.asi_pendentes + ' ASI');
    if (pend.marcos_pendentes && pend.marcos_pendentes.length) items.push(pend.marcos_pendentes.length + ' marco(s)');
    (pend.talento_racial_niveis || []).forEach(function (n) { items.push('talento racial N' + n); });
    if (pend.opcoes_pendentes) items.push(pend.opcoes_pendentes + ' opção(ões)');
    if (pend.cantrips_pend) items.push(pend.cantrips_pend + ' truque(s)');
    if (pend.known_pend) items.push(pend.known_pend + ' magia(s)');
    if (pend.magias_concedidas_pend) items.push(pend.magias_concedidas_pend + ' magia(s) concedida(s)');
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
      if (!j || !j.ready || !j.preview) {
        if (statusEl) statusEl.textContent = 'prévia indisponível';
        if (j && j.erros && j.erros.length) showErr(j.erros, true);
        return;
      }
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
    if (!SN.podeSubir && !lote.length) {
      showErr(['Selecione ao menos uma das escolhas pendentes antes de confirmar.'], false);
      return;
    }
    confirmBtn.disabled = true; if (prevBtn) prevBtn.disabled = true;
    if (statusEl) { statusEl.textContent = 'aplicando…'; statusEl.classList.add('is-live'); }
    var actions = acoesPayload(), serialized = JSON.stringify(actions);
    if (!confirmation || confirmation.actions !== serialized) {
      confirmation = {
        actions: serialized,
        id: window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() :
          Date.now().toString(36) + '-' + Math.random().toString(36).slice(2)
      };
    }
    post(SN.aplicarUrl, { acoes: actions, request_id: confirmation.id }).then(function (res) {
      if (res.status === 200 && !res.redirected && res.json && res.json.ok === true) {
        if (res.json.continuar) {
          var temPendencias = !!res.json.continuar_pendencias;
          if (feedbackEl) {
            feedbackEl.dataset.kind = 'ok';
            feedbackEl.innerHTML =
              '<div class="lvl-ok"><strong>' + (temPendencias ? 'Escolhas salvas.' : 'Nível concluído.') + '</strong> ' +
              (temPendencias ? 'A escolha abriu novas decisões que ainda precisam ser concluídas.' : 'Você ainda tem aventuras para avançar novamente.') +
              '<div style="margin-top:.7rem;display:flex;gap:.55rem;flex-wrap:wrap">' +
              '<a class="cf-btn cf-btn-primary" href="' + esc(SN.pageUrl + (SN.classeId != null ? '?classe=' + encodeURIComponent(SN.classeId) : '')) + '">' +
              (temPendencias ? 'Resolver escolhas restantes' : ('Continuar para o nível ' + esc(res.json.proximo_nivel))) + '</a>' +
              '<a class="cf-btn" href="' + esc(SN.fichaUrl + '?levelup=ok') + '">Voltar à ficha</a></div></div>';
            feedbackEl.hidden = false;
          }
          confirmBtn.hidden = true;
          if (prevBtn) prevBtn.hidden = true;
          if (nextBtn) nextBtn.hidden = true;
          if (statusEl) {
            statusEl.classList.remove('is-live');
            statusEl.textContent = temPendencias ? 'escolhas pendentes' : 'nível concluído';
          }
        } else {
          window.location.href = SN.fichaUrl + '?levelup=ok';
        }
      } else {
        showErr(confirmationErrors(res), false);
        confirmBtn.disabled = false; if (prevBtn) prevBtn.disabled = current === 0;
        if (statusEl) statusEl.classList.remove('is-live');
      }
    }, function () {
      showErr(['Falha de rede ao confirmar. Verifique a conexão e tente novamente com as mesmas escolhas.'], false);
      confirmBtn.disabled = false; if (prevBtn) prevBtn.disabled = current === 0;
      if (statusEl) statusEl.classList.remove('is-live');
    });
  }

  // ================= wiring =================
  function initCards() {
    main.querySelectorAll('[data-lvl-card="multiclasse"]').forEach(function (card) {
      var chosen = fieldOf(card, 'classe'), label = card.querySelector('[data-hunter-choice]');
      if (!chosen || !label) return;
      var syncHunter = function () {
        label.hidden = chosen.options[chosen.selectedIndex].dataset.hunter !== '1';
      };
      chosen.addEventListener('change', syncHunter); syncHunter();
    });
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
        showChoiceDescription(card, option);
        handleQueue(field);
        field.value = '';
      });
    });
    main.querySelectorAll('[data-lvl-describe]').forEach(function (field) {
      field.addEventListener('change', function () {
        var option = field.options[field.selectedIndex];
        var card = field.closest('[data-lvl-card]');
        showChoiceDescription(card, option);
      });
    });
    // Um cartão por aprimoramento pendente: alternância atributo↔talento, atributos que o
    // talento permite e ENFILEIRAMENTO na própria seleção (sem botão "Escolher").
    main.querySelectorAll('[data-lvl-card="asi"], [data-lvl-card="marco"]').forEach(function (asi) {
      var attrsBlock = asi.querySelector('[data-lvl-asi-attrs]'), talBlock = asi.querySelector('[data-lvl-asi-tal]');
      if (attrsBlock) {
        var allocated = [];
        asi.resetAsiAllocation = function () { allocated = []; updateAllocation(); };
        function updateAllocation() {
          fieldOf(asi, 'asi_attr_1').value = allocated[0] || '';
          fieldOf(asi, 'asi_attr_2').value = allocated[1] || '';
          var remaining = 2 - allocated.length;
          attrsBlock.querySelector('[data-asi-budget]').textContent =
            remaining + (remaining === 1 ? ' ponto disponível' : ' pontos disponíveis');
          attrsBlock.querySelectorAll('[data-asi-attribute]').forEach(function (row) {
            var amount = allocated.filter(function (sig) { return sig === row.dataset.asiAttribute; }).length;
            row.querySelector('[data-asi-delta]').textContent = '+' + amount;
            row.querySelector('[data-asi-minus]').disabled = !amount;
            row.querySelector('[data-asi-plus]').disabled = allocated.length >= 2;
          });
          queueAsi(asi);
        }
        attrsBlock.querySelectorAll('[data-asi-attribute]').forEach(function (row) {
          row.querySelector('[data-asi-plus]').addEventListener('click', function () {
            if (allocated.length >= 2) return;
            allocated.push(row.dataset.asiAttribute); updateAllocation();
          });
          row.querySelector('[data-asi-minus]').addEventListener('click', function () {
            var index = allocated.indexOf(row.dataset.asiAttribute);
            if (index < 0) return;
            allocated.splice(index, 1); updateAllocation();
          });
        });
      }
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
      asi.addEventListener('change', function () {
        if (asi.dataset.lvlCard !== 'marco') { queueAsi(asi); return; }
        var key = 'marco#' + asi.dataset.marco;
        var picks = {}, incomplete = !talSel.value;
        asi.querySelectorAll('[data-talento-pick]').forEach(function (sel) {
          if (!sel.value) incomplete = true;
          var k = sel.dataset.pickKey;
          if (!picks[k]) picks[k] = [];
          if (sel.value) picks[k].push(sel.value);
        });
        showChoiceDescription(asi, talSel.options[talSel.selectedIndex]);
        if (incomplete) { if (inLote(key)) removeKey(key); return; }
        addOrReplace({ tipo: 'marco', key: key, card: asi, label: optText(talSel) + ' — ' + attrSel.value,
          payload: { marco: asi.dataset.marco, talento: talSel.value,
            talento_attr: attrSel.value, talento_picks: picks } });
      });
    });
    main.querySelectorAll('[data-lvl-card="aprender_magias"]').forEach(function (card) {
      card.addEventListener('change', function (e) { if (e.target && e.target.type === 'checkbox') rebuildMagias(card); });
    });
    main.querySelectorAll('[data-lvl-card="magias_concedidas"]').forEach(function (card) {
      card.addEventListener('change', function (e) {
        if (e.target && e.target.type === 'checkbox') rebuildMagiasConcedidas(card);
      });
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
          var naturezaDiferente = (t !== '' && t != null) && op.getAttribute('data-truque') !== t;
          op.disabled = naturezaDiferente || op.dataset.queued === '1';
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
    if (x) { e.preventDefault(); removeKey(x.dataset.key, true); }
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
  initChoicePickers();
  renderCards();
  showCurrent();
  renderReview();
  runPreview();
})();
