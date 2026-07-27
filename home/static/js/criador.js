/* Criador de personagem — monta as seções dependentes a partir do catálogo
   (#cf-catalogos json_script) e envia o POST de criação. Depende de point_buy.js
   (window.PointBuy.scores()). */
(function () {
    'use strict';

    function init() {
        var dataEl = document.getElementById('cf-catalogos');
        var form = document.getElementById('criador-form');
        if (!dataEl || !form) return;
        var CAT = JSON.parse(dataEl.textContent);

        var SIG = [['FOR', 'Força'], ['DES', 'Destreza'], ['CON', 'Constituição'],
                   ['INT', 'Inteligência'], ['SAB', 'Sabedoria'], ['CAR', 'Carisma']];

        function el(id) { return document.getElementById(id); }
        function opt(value, label) { var o = document.createElement('option'); o.value = value; o.textContent = label; return o; }
        function checkedVals(wrap) {
            return Array.prototype.slice.call(wrap.querySelectorAll('input[type=checkbox]:checked')).map(function (i) { return i.value; });
        }
        function checkbox(value, label) {
            var lab = document.createElement('label');
            lab.className = 'flex cursor-pointer items-center gap-2 rounded border border-[var(--stroke)] bg-[var(--bg0)] px-2 py-1 text-sm hover:border-[var(--ember)]';
            var inp = document.createElement('input');
            inp.type = 'checkbox'; inp.value = value;
            var span = document.createElement('span'); span.className = 'text-[var(--text)]'; span.textContent = label;
            lab.appendChild(inp); lab.appendChild(span);
            return lab;
        }
        function limitValue(n) { return (typeof n === 'function') ? n() : n; }
        function enforceLimit(wrap, n, counterEl) {
            var boxes = Array.prototype.slice.call(wrap.querySelectorAll('input[type=checkbox]'));
            function upd() {
                var lim = limitValue(n);
                var chosen = boxes.filter(function (b) { return b.checked; }).length;
                boxes.forEach(function (b) { b.disabled = !b.checked && chosen >= lim; });
                if (counterEl) counterEl.textContent = '(' + chosen + '/' + lim + ')';
            }
            boxes.forEach(function (b) { b.addEventListener('change', upd); });
            upd();
            return upd;
        }
        // Limite compartilhado por varios containers, vindo do catalogo/tag.
        function enforceLimitGroup(wraps, n, counterEl) {
            var boxes = [];
            wraps.forEach(function (w) {
                boxes = boxes.concat(Array.prototype.slice.call(w.querySelectorAll('input[type=checkbox]')));
            });
            function upd() {
                var lim = limitValue(n);
                var chosen = boxes.filter(function (b) { return b.checked; }).length;
                boxes.forEach(function (b) { b.disabled = !b.checked && chosen >= lim; });
                if (counterEl) counterEl.textContent = '(' + chosen + '/' + lim + ')';
            }
            boxes.forEach(function (b) { b.addEventListener('change', upd); });
            upd();
            return upd;
        }
        // Checkbox com uma linha de descrição inline (estilo "widget": vê o efeito sem sair da aba).
        function checkboxDesc(value, label, desc) {
            var lab = document.createElement('label');
            lab.className = 'flex cursor-pointer items-start gap-2 rounded border border-[var(--stroke)] bg-[var(--bg0)] px-2 py-1.5 text-sm hover:border-[var(--ember)]';
            var inp = document.createElement('input');
            inp.type = 'checkbox'; inp.value = value; inp.className = 'mt-0.5';
            var box = document.createElement('span'); box.className = 'min-w-0';
            var t = document.createElement('span'); t.className = 'block text-[var(--text)]'; t.textContent = label;
            box.appendChild(t);
            if (desc) {
                var d = document.createElement('span');
                d.className = 'mt-0.5 block text-[11px] leading-snug text-[var(--muted)] line-clamp-2';
                d.textContent = desc;
                box.appendChild(d);
            }
            lab.appendChild(inp); lab.appendChild(box);
            return lab;
        }
        function renderMd(v) {
            if (typeof renderBonfireMarkdown === 'function') return renderBonfireMarkdown(v);
            if (window.marked && window.marked.parse) return window.marked.parse(v, { gfm: true, breaks: true });
            var d = document.createElement('div'); d.textContent = v || ''; return d.innerHTML.replace(/\n/g, '<br>');
        }
        // Mostra/oculta o painel de descrição de um talento selecionado (markdown Bonfire).
        function showTalentoDesc(panel, t) {
            if (!panel) return;
            if (!t || !(t.descricao || '').trim()) { panel.classList.add('hidden'); panel.innerHTML = ''; return; }
            panel.innerHTML = renderMd(t.descricao);
            panel.classList.remove('hidden');
        }

        // índices auxiliares
        var racaBySlug = {}; CAT.racas.forEach(function (r) { racaBySlug[r.slug] = r; });
        var essenciaBySlug = {}; (CAT.essencias || []).forEach(function (e) { essenciaBySlug[e.slug] = e; });
        var classeBySlug = {}; CAT.classes.forEach(function (c) { classeBySlug[c.slug] = c; });
        var periciaBySlug = {}; CAT.pericias.forEach(function (p) { periciaBySlug[p.slug] = p; });
        var antecedenteBySlug = {}; (CAT.antecedentes || []).forEach(function (a) { antecedenteBySlug[a.slug] = a; });
        var defaultBgGrants = CAT.grants_antecedente || {};
        function toInt(v, fallback) {
            var n = parseInt(v, 10);
            return isNaN(n) ? fallback : n;
        }
        function currentBgGrants() {
            var a = (typeof antSel !== 'undefined' && antSel) ? antecedenteBySlug[antSel.value] : null;
            return (a && a.grants) || defaultBgGrants || {};
        }
        // ASI do antecedente em DUAS formas (regra de sistema 5.5e): '2/1' (+2 e +1) e
        // '1/1/1' (+1 em três atributos). A forma é do jogador, não do antecedente.
        function asiModo() {
            var rs = (typeof asiModoRadios !== 'undefined' && asiModoRadios) || [];
            for (var i = 0; i < rs.length; i++) { if (rs[i].checked) return rs[i].value; }
            return '2/1';
        }
        function asiShapeVals() { return asiModo() === '1/1/1' ? [1, 1, 1] : [2, 1]; }
        function asiActiveSelects() { return asiModo() === '1/1/1' ? [asi2, asi1, asi3] : [asi2, asi1]; }
        function currentAsiBonus() {
            var v = asiShapeVals();
            return asiActiveSelects().map(function (s, i) { return { sig: s.value, val: v[i] }; });
        }
        function asiAdd(sig) {
            var t = 0; currentAsiBonus().forEach(function (b) { if (b.sig === sig) t += b.val; }); return t;
        }
        function currentAsiParts() { var v = asiShapeVals(); return { major: v[0], minor: v[1], third: v[2] || 1 }; }
        function bgSkillN() { return toInt(currentBgGrants().pericias, 0); }
        function bgLangToolN() { return toInt(currentBgGrants().idiomas_ou_ferramentas, 0); }

        // ---- ASI (+2/+1 ou +1/+1/+1 — regra de sistema, forma à escolha do jogador)
        var asi2 = el('cf-asi2'), asi1 = el('cf-asi1'), asi3 = el('cf-asi3');
        var asi3Wrap = document.querySelector('[data-asi3-wrap]');
        var asiModoRadios = Array.prototype.slice.call(document.querySelectorAll('input[name="cf-asi-modo"]'));
        SIG.forEach(function (p) {
            asi2.appendChild(opt(p[0], p[1])); asi1.appendChild(opt(p[0], p[1]));
            if (asi3) asi3.appendChild(opt(p[0], p[1]));
        });
        asi2.value = 'DES'; asi1.value = 'CON'; if (asi3) asi3.value = 'FOR';
        // Os selects ATIVOS (2 no '2/1', 3 no '1/1/1') DEVEM ir em atributos diferentes:
        // desabilita no outro a opção já escolhida e empurra colisões p/ o próximo atributo livre.
        // Também mostra/oculta o 3º select e ajusta os rótulos (+2/+1 vs +1/+1/+1).
        function syncAsi() {
            var sels = asiActiveSelects();
            if (asi3Wrap) asi3Wrap.hidden = (asiModo() !== '1/1/1');
            var v = asiShapeVals();
            var l2 = document.querySelector('[data-asi-major-label]'); if (l2) l2.textContent = '+' + v[0];
            var l1 = document.querySelector('[data-asi-minor-label]'); if (l1) l1.textContent = '+' + v[1];
            var l3 = document.querySelector('[data-asi-third-label]'); if (l3) l3.textContent = '+' + (v[2] || 1);
            [asi2, asi1, asi3].forEach(function (s) {
                if (!s) return;
                var ativo = sels.indexOf(s) !== -1;
                Array.prototype.forEach.call(s.options, function (o) {
                    o.disabled = ativo && sels.some(function (other) { return other !== s && other.value === o.value; });
                });
            });
            for (var i = 0; i < sels.length; i++) {
                var taken = sels.slice(0, i).map(function (s) { return s.value; });
                if (taken.indexOf(sels[i].value) !== -1) {
                    for (var k = 0; k < sels[i].options.length; k++) {
                        if (taken.indexOf(sels[i].options[k].value) === -1) { sels[i].value = sels[i].options[k].value; break; }
                    }
                }
            }
        }
        function onAsiChange() { syncAsi(); updateMagiaLimit(); }
        asi2.addEventListener('change', onAsiChange);
        asi1.addEventListener('change', onAsiChange);
        if (asi3) asi3.addEventListener('change', onAsiChange);
        asiModoRadios.forEach(function (r) { r.addEventListener('change', onAsiChange); });
        syncAsi();

        function updateBackgroundCopy() {
            var g = currentBgGrants();
            // (os rótulos +2/+1 do ASI agora são atualizados por syncAsi, conforme a forma escolhida)
            var equipGold = document.querySelector('[data-equip-gold-alt]');
            if (equipGold) equipGold.textContent = toInt(g.equip_gold_alt, 0);
            var resumo = el('cf-antecedente-resumo');
            if (resumo) {
                resumo.textContent = 'Concede ' + toInt(g.po_inicial, 0) + ' PO, '
                    + toInt(g.pericias, 0) + ' perícia(s) e '
                    + toInt(g.idiomas_ou_ferramentas, 0) + ' escolha(s) de idioma/ferramenta.';
            }
            var hint = document.querySelector('[data-langtool-hint]');
            if (hint) {
                var n = toInt(g.idiomas_ou_ferramentas, 0);
                hint.textContent = '— ' + n + ' no total (idiomas, ferramentas ou misto)';
            }
        }

        // ---- Raça / linhagem / essência / vertente
        var racaSel = el('cf-raca');
        racaSel.appendChild(opt('', '— Selecione —'));
        CAT.racas.forEach(function (r) { racaSel.appendChild(opt(r.slug, r.nome)); });
        var linWrap = el('cf-linhagem-wrap'), linSel = el('cf-linhagem');
        var essWrap = el('cf-essencia-wrap'), essSel = el('cf-essencia');
        var verWrap = el('cf-vertente-wrap'), verSel = el('cf-vertente');

        // Linhagem e Essência são MUTUAMENTE EXCLUSIVAS (regra do sistema: o personagem
        // tem uma OU outra, nunca as duas). Ao escolher uma, a outra (e a vertente, que só
        // existe dependurada da essência) é desmarcada NA HORA — troca automática e fluida,
        // sem bloquear nenhum dos dois selects. Os dois listeners abaixo são registrados
        // ANTES de qualquer outro listener de linSel/essSel para que os re-renders
        // dependentes (painéis de info, talentos, perícias, prévia) já vejam o estado
        // corrigido quando rodarem.
        function limparEssencia() {
            if (!essSel.value) return;
            essSel.value = '';
            onEssencia();          // oculta/reseta a vertente (dependia da essência)
            renderEssenciaInfo();  // painel de info da essência reflete a troca
        }
        function limparLinhagem() {
            if (!linSel.value) return;
            linSel.value = '';
        }
        linSel.addEventListener('change', function () { if (linSel.value) limparEssencia(); });
        essSel.addEventListener('change', function () { if (essSel.value) limparLinhagem(); });

        // rótulo do seletor de sub-escolha da essência: "Vertente elemental" (elementais) OU
        // "Clã / Herança" (Vampirismo) — vem do catálogo por essência (subescolha_label).
        var verLabel = document.querySelector('label[for="cf-vertente"]');
        // sub-escolha (vertente/clã) atualmente selecionada, ou '' se o seletor está oculto.
        function currentVertente() { return verWrap.hidden ? '' : verSel.value; }
        function onEssencia() {
            var ess = essenciaBySlug[essSel.value];
            var vertentes = (ess && ess.vertentes && ess.vertentes.length) ? ess.vertentes : [];
            if (vertentes.length) {
                if (verLabel && ess && ess.subescolha_label) verLabel.textContent = ess.subescolha_label;
                verSel.innerHTML = '';
                verSel.appendChild(opt('', '— Selecione —'));
                vertentes.forEach(function (v) { verSel.appendChild(opt(v.slug, v.nome)); });
                verWrap.hidden = false;
            } else { verWrap.hidden = true; }
        }
        essSel.addEventListener('change', onEssencia);

        function onRaca() {
            var r = racaBySlug[racaSel.value];
            linSel.innerHTML = '';
            if (r && r.linhagens && r.linhagens.length) {
                linSel.appendChild(opt('', '— Selecione —'));
                r.linhagens.forEach(function (l) { linSel.appendChild(opt(l.slug, l.nome)); });
                linWrap.hidden = false;
            } else { linWrap.hidden = true; }
            if (r && r.permite_essencia) {
                essSel.innerHTML = '';
                essSel.appendChild(opt('', '— Selecione —'));
                (CAT.essencias || []).forEach(function (e) { essSel.appendChild(opt(e.slug, e.nome)); });
                essWrap.hidden = false;
            } else { essWrap.hidden = true; }
            onEssencia();
            refreshRaceDependent();
        }
        racaSel.addEventListener('change', onRaca);

        // ---- Classe (perícias + equipamento)
        var classeSel = el('cf-classe');
        classeSel.appendChild(opt('', '— Selecione —'));
        CAT.classes.forEach(function (c) { classeSel.appendChild(opt(c.slug, c.nome)); });
        var skillsWrap = el('cf-classe-skills');
        var skillCounter = document.querySelector('[data-skill-counter]');
        var equipTexto = el('cf-equip-texto');
        // ---- Escolhas de classe DIRIGIDAS POR TAGS pick:* (Maestria de Arma, Estilo de Luta,
        // e qualquer pick:opcao:<tipo>:N do N1). Renderizadas GENERICAMENTE a partir de
        // c.pick_groups (resolvedor home.picks) — um bloco por grupo. Substitui os caminhos
        // dedicados cf-maestria / cf-estilo. O payload manda picks:[{kind,tipo,valores}].
        var pickGroupsWrap = el('cf-pick-groups');
        var pickGroupState = [];  // [{kind, tipo, grid}]

        function pickItemCard(item, kind) {
            // Container é <div> (não <label>): quando há SUB-ESCOLHA de maestria, um <label>
            // pai faria o clique numa maestria alternar também o cabeçalho. Só a linha do topo
            // (checkbox + nome), quando existe, é um <label>.
            var card = document.createElement('div');
            card.className = 'cf-pick-item flex flex-col gap-0.5 rounded border border-[var(--stroke)] bg-[var(--bg1)] px-2 py-1.5 hover:border-[var(--ember)]';
            card.dataset.nome = (item.nome || '').toLowerCase();
            // Maestria de Arma (kind 'arma'): a MESMA ARMA pode aprender mais de uma maestria
            // (regra da staff — p.ex. lentidão E exposição no mesmo arco). Cada maestria é um
            // CHECKBOX independente cujo valor é o PAR `'<arma>|<maestria>'`; contam para o
            // limite do grupo (enforceLimit conta checkboxes). A unicidade do par é natural
            // (cada maestria é um checkbox), e o 2º slot "oferece só as ainda não aprendidas"
            // porque marcar uma maestria já a aprende (não há como marcá-la de novo).
            var armaSub = kind === 'arma' && item.maestrias && item.maestrias.length;
            if (armaSub) {
                var head = document.createElement('div'); head.className = 'flex items-center gap-2';
                var hn = document.createElement('span'); hn.className = 'text-sm font-semibold text-[var(--text)]'; hn.textContent = item.nome; head.appendChild(hn);
                if (item.dano) { var hd = document.createElement('span'); hd.className = 'ml-auto text-[11px] text-[var(--muted)]'; hd.textContent = item.dano; head.appendChild(hd); }
                card.appendChild(head);
                var sub = document.createElement('div');
                sub.className = 'cf-maestria-sub mt-1 flex flex-col gap-1 border-t border-[var(--stroke)]/50 pt-1';
                var slbl = document.createElement('div');
                slbl.className = 'text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]';
                slbl.textContent = 'Maestrias'; sub.appendChild(slbl);
                item.maestrias.forEach(function (m) {
                    var rl = document.createElement('label'); rl.className = 'flex cursor-pointer items-center gap-1.5 text-[11px] text-[var(--spark)]';
                    var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'cf-pick-arma-cb'; cb.value = item.slug + '|' + m.slug;
                    var s = document.createElement('span'); s.textContent = m.nome; if (m.efeito) s.title = m.efeito;
                    rl.appendChild(cb); rl.appendChild(s); sub.appendChild(rl);
                });
                card.appendChild(sub);
                var det0 = (item.pre ? ('Pré: ' + item.pre) : '') + ((item.pre && item.descricao) ? ' · ' : '') + (item.descricao || '');
                if (det0) { var p0 = document.createElement('div'); p0.className = 'text-[11px] text-[var(--muted)]'; p0.textContent = det0.length > 160 ? det0.slice(0, 160) + '…' : det0; card.appendChild(p0); }
                return card;
            }
            var top = document.createElement('label'); top.className = 'flex cursor-pointer items-center gap-2';
            var inp = document.createElement('input'); inp.type = 'checkbox'; inp.value = item.slug;
            var nm = document.createElement('span'); nm.className = 'text-sm font-semibold text-[var(--text)]'; nm.textContent = item.nome;
            top.appendChild(inp); top.appendChild(nm);
            if (item.dano) {
                var dano = document.createElement('span'); dano.className = 'ml-auto text-[11px] text-[var(--muted)]'; dano.textContent = item.dano; top.appendChild(dano);
            }
            card.appendChild(top);
            if (item.chips && item.chips.length) {
                var chips = document.createElement('div'); chips.className = 'flex flex-wrap gap-1';
                item.chips.forEach(function (m) {
                    var ch = document.createElement('span');
                    ch.className = 'rounded bg-[var(--bg0)] px-1.5 py-0.5 text-[10px] text-[var(--spark)]';
                    ch.textContent = m; chips.appendChild(ch);
                });
                card.appendChild(chips);
            }
            var det = (item.pre ? ('Pré: ' + item.pre) : '') + ((item.pre && item.descricao) ? ' · ' : '') + (item.descricao || '');
            if (det) {
                var p = document.createElement('div'); p.className = 'text-[11px] text-[var(--muted)]';
                p.textContent = det.length > 160 ? det.slice(0, 160) + '…' : det;
                card.appendChild(p);
            }
            return card;
        }

        function renderPickGroups(c) {
            pickGroupsWrap.innerHTML = '';
            pickGroupState = [];
            var groups = (c && c.pick_groups) || [];
            if (!groups.length) { pickGroupsWrap.hidden = true; return; }
            pickGroupsWrap.hidden = false;
            groups.forEach(function (g) {
                var sec = document.createElement('div');
                var head = document.createElement('div');
                head.className = 'mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--muted)]';
                head.textContent = 'Escolha ' + g.n + ' ' + (g.label || g.tipo || '') + ' ';
                var counter = document.createElement('span'); head.appendChild(counter);
                sec.appendChild(head);
                var box = document.createElement('div');
                box.className = 'max-h-80 overflow-y-auto rounded border border-[var(--stroke)] bg-[var(--bg0)] p-1.5';
                // busca (só faz sentido para universos grandes, ex.: armas)
                if ((g.universo || []).length > 12) {
                    var busca = document.createElement('input');
                    busca.type = 'search'; busca.placeholder = 'Buscar…'; busca.autocomplete = 'off';
                    busca.className = 'mb-1.5 w-full rounded border border-[var(--stroke)] bg-[var(--bg1)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--ember)] focus:outline-none';
                    busca.addEventListener('input', function () {
                        var q = (busca.value || '').toLowerCase().trim();
                        Array.prototype.forEach.call(box.querySelectorAll('.cf-pick-item'), function (it) {
                            it.style.display = (!q || (it.dataset.nome || '').indexOf(q) !== -1) ? '' : 'none';
                        });
                    });
                    sec.appendChild(busca);
                }
                var grid = document.createElement('div');
                // agrupa por 'cat' quando os itens a declaram (armas por categoria)
                var cats = {}, ordem = [];
                (g.universo || []).forEach(function (item) {
                    var cat = item.cat || '';
                    if (!(cat in cats)) { cats[cat] = []; ordem.push(cat); }
                    cats[cat].push(item);
                });
                var multiCat = ordem.length > 1 || (ordem.length === 1 && ordem[0]);
                ordem.forEach(function (cat) {
                    if (multiCat && cat) {
                        var h = document.createElement('div');
                        h.className = 'mb-1 mt-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]/80 first:mt-0';
                        h.textContent = cat; grid.appendChild(h);
                    }
                    var sub = document.createElement('div');
                    sub.className = 'grid grid-cols-1 gap-1 sm:grid-cols-2';
                    cats[cat].forEach(function (item) { sub.appendChild(pickItemCard(item, g.kind)); });
                    grid.appendChild(sub);
                });
                box.appendChild(grid);
                sec.appendChild(box);
                pickGroupsWrap.appendChild(sec);
                enforceLimit(box, g.n, counter);
                pickGroupState.push({ kind: g.kind, tipo: g.tipo, grid: box });
            });
        }
        function pickGroupsSel() {
            // Cada checkbox marcado JÁ carrega o valor final: para Maestria de Arma é o PAR
            // combinado `'<arma>|<maestria>'` (uma maestria por checkbox, a mesma arma pode
            // aparecer em vários), para arma sem maestrias e p/ opções é o próprio slug.
            return pickGroupState.map(function (g) {
                var vals = [];
                Array.prototype.forEach.call(g.grid.querySelectorAll('input[type=checkbox]'), function (cb) {
                    if (cb.checked) vals.push(cb.value);
                });
                return { kind: g.kind, tipo: g.tipo, valores: vals };
            });
        }

        function renderClasseSkills() {
            var c = classeBySlug[classeSel.value];
            skillsWrap.innerHTML = '';
            renderPickGroups(c);
            refreshExpertise();
            renderClasseProfChoices(c);
            renderMagias(c);
            if (!c) { skillCounter.textContent = ''; equipTexto.textContent = ''; return; }
            var lista = (c.pericias_lista && c.pericias_lista.length) ? c.pericias_lista
                        : CAT.pericias.map(function (p) { return p.slug; });
            lista.forEach(function (sl) {
                var info = periciaBySlug[sl];
                skillsWrap.appendChild(checkbox(sl, info ? info.nome : sl));
            });
            applySkillRules();
            equipTexto.textContent = c.equipamento ? c.equipamento : '(sem texto cadastrado)';
            renderArmadurasProf(c);
        }
        // Preview (informativo) das proficiências de armadura que a classe concede.
        var armadurasProfWrap = el('cf-armaduras-prof');
        function renderArmadurasProf(c) {
            if (!armadurasProfWrap) return;
            var lista = (c && c.armaduras_prof) || [];
            var out = armadurasProfWrap.querySelector('[data-armaduras-prof]');
            if (!lista.length) { armadurasProfWrap.hidden = true; if (out) out.textContent = ''; return; }
            armadurasProfWrap.hidden = false;
            out.textContent = lista.join(', ');
        }
        classeSel.addEventListener('change', renderClasseSkills);

        // ---- Especialização/expertise (Ladino) — (Estilo de Luta migrou p/ pick-groups genérico)
        var expertiseWrap = el('cf-expertise-wrap'), expertiseBox = el('cf-expertise');
        var expertiseCounter = document.querySelector('[data-expertise-counter]');
        var classeProfWrap = el('cf-classe-prof-wrap'), classeProfBox = el('cf-classe-prof');
        var classeProfGroups = [];

        function refreshExpertise() {
            var c = classeBySlug[classeSel.value];
            if (!c || !c.expertise_n) { expertiseWrap.hidden = true; expertiseBox.innerHTML = ''; return; }
            expertiseWrap.hidden = false;
            var prev = checkedVals(expertiseBox);
            var prof = checkedVals(skillsWrap).concat(checkedVals(bgWrap));
            var seen = {}, uniq = prof.filter(function (s) { if (seen[s]) return false; seen[s] = 1; return true; });
            expertiseBox.innerHTML = '';
            uniq.forEach(function (sl) {
                var info = periciaBySlug[sl];
                var lab = checkbox(sl, info ? info.nome : sl);
                if (prev.indexOf(sl) !== -1) lab.querySelector('input').checked = true;
                expertiseBox.appendChild(lab);
            });
            enforceLimit(expertiseBox, c.expertise_n, expertiseCounter);
        }

        function classeProfOptions(tipo) {
            var ferramentas = CAT.ferramentas || [];
            if (tipo === 'instrumento') {
                ferramentas = ferramentas.filter(function (f) { return f.subcategoria === 'instrumento'; });
            } else if (tipo === 'ferramenta_artesao') {
                ferramentas = ferramentas.filter(function (f) { return f.subcategoria === 'ferramenta_artesao'; });
            } else if (tipo === 'ferramenta_artesao_ou_instrumento') {
                ferramentas = ferramentas.filter(function (f) {
                    return f.subcategoria === 'ferramenta_artesao' || f.subcategoria === 'instrumento';
                });
            }
            return ferramentas.map(function (f) { return { value: f.nome, label: f.nome, desc: f.desc }; });
        }

        function classeProfLabel(tipo) {
            return {
                instrumento: 'instrumento(s)',
                ferramenta: 'ferramenta(s)',
                ferramenta_artesao: 'ferramenta(s) de artesão',
                ferramenta_ou_instrumento: 'ferramenta(s) ou instrumento(s)',
                ferramenta_artesao_ou_instrumento: 'ferramenta(s) de artesão ou instrumento(s)'
            }[tipo] || 'proficiência(s)';
        }

        function renderClasseProfChoices(c) {
            classeProfBox.innerHTML = '';
            classeProfGroups = [];
            var picks = (c && c.classe_prof_picks) || [];
            if (!picks.length) { classeProfWrap.hidden = true; return; }
            classeProfWrap.hidden = false;
            picks.forEach(function (pick) {
                var grp = document.createElement('div');
                var head = document.createElement('div');
                head.className = 'mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--muted)]';
                head.textContent = 'Escolha ' + pick.n + ' ' + classeProfLabel(pick.tipo) + ' ';
                if (pick.fonte) {
                    var f = document.createElement('span');
                    f.className = 'font-normal normal-case text-[var(--muted)]';
                    f.textContent = '— ' + pick.fonte + ' ';
                    head.appendChild(f);
                }
                var counter = document.createElement('span');
                head.appendChild(counter);
                grp.appendChild(head);
                var grid = document.createElement('div');
                grid.className = 'grid max-h-64 grid-cols-1 gap-1 overflow-y-auto rounded border border-[var(--stroke)] bg-[var(--bg0)] p-2 sm:grid-cols-2';
                classeProfOptions(pick.tipo).forEach(function (o) {
                    grid.appendChild(o.desc ? checkboxDesc(o.value, o.label, o.desc) : checkbox(o.value, o.label));
                });
                grp.appendChild(grid);
                classeProfBox.appendChild(grp);
                enforceLimit(grid, pick.n, counter);
                classeProfGroups.push({ tipo: pick.tipo, n: pick.n, grid: grid });
            });
        }

        function classeProfChoicesSel() {
            return classeProfGroups.map(function (g) {
                return { tipo: g.tipo, valores: checkedVals(g.grid) };
            });
        }

        // ---- Magias (truques + 1º nível) — contagem reativa ao mod de conjuração
        var SIG_AB = { str: 'FOR', dex: 'DES', con: 'CON', int: 'INT', wis: 'SAB', cha: 'CAR' };
        var magiasWrap = el('cf-magias-wrap'), truquesSec = el('cf-truques-sec');
        var truquesBox = el('cf-truques'), magiasBox = el('cf-magias');
        var truqueCounter = document.querySelector('[data-truque-counter]');
        var magiaCounter = document.querySelector('[data-magia-counter]');
        var magiaLimit = 0;

        function escapeRegExp(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
        function evalFormula(expr, ctx) {
            if (!expr) return null;
            var js = String(expr);
            Object.keys(ctx).sort(function (a, b) { return b.length - a.length; }).forEach(function (key) {
                js = js.replace(new RegExp(escapeRegExp(key), 'g'), String(ctx[key]));
            });
            js = js.replace(/\brounddown\s*\(/g, 'Math.floor(')
                   .replace(/\broundup\s*\(/g, 'Math.ceil(')
                   .replace(/\bmax\s*\(/g, 'Math.max(')
                   .replace(/\bmin\s*\(/g, 'Math.min(')
                   .replace(/\bround\s*\(/g, 'Math.round(')
                   .replace(/\babs\s*\(/g, 'Math.abs(');
            if (/[A-Za-z_]/.test(js.replace(/Math\.(?:max|min|floor|ceil|round|abs)/g, ''))) return null;
            try {
                var val = Function('"use strict"; return (' + js + ');')();
                return isFinite(val) ? Math.floor(val) : null;
            } catch (e) {
                return null;
            }
        }

        function spellCountNv1(conj) {
            if (conj.magias_n != null) return conj.magias_n;
            if (!conj.magias_formula) return 0;
            var scores = window.PointBuy ? window.PointBuy.scores() : {};
            var ctx = { classlvl: 1, lvl: 1 };
            Object.keys(SIG_AB).forEach(function (ab) {
                var sig = SIG_AB[ab];
                var sc = (scores[sig] || 8) + asiAdd(sig);
                ctx[ab + '_mod'] = Math.floor((sc - 10) / 2);
            });
            var abilities = String(conj.ability || 'int').split('|');
            ctx['spell_mod'] = Math.max.apply(null, abilities.map(function (ab) { return ctx[ab + '_mod'] || 0; }));
            var n = evalFormula(conj.magias_formula, ctx);
            return n == null ? 0 : Math.max(1, n);
        }
        function enforceMagias() {
            var boxes = Array.prototype.slice.call(magiasBox.querySelectorAll('input[type=checkbox]'));
            var chosen = boxes.filter(function (b) { return b.checked; }).length;
            boxes.forEach(function (b) { b.disabled = !b.checked && chosen >= magiaLimit; });
            if (magiaCounter) magiaCounter.textContent = '(' + chosen + '/' + magiaLimit + ')';
        }
        magiasBox.addEventListener('change', enforceMagias);
        function updateMagiaLimit() {
            var c = classeBySlug[classeSel.value];
            if (!c || !c.conjuracao) return;
            magiaLimit = spellCountNv1(c.conjuracao);
            enforceMagias();
        }
        function renderMagias(c) {
            truquesBox.innerHTML = ''; magiasBox.innerHTML = '';
            var conj = c && c.conjuracao;
            if (!conj) { magiasWrap.hidden = true; return; }
            magiasWrap.hidden = false;
            truquesSec.hidden = !conj.truques_n;
            if (conj.truques_n) {
                conj.truques.forEach(function (t) { truquesBox.appendChild(checkbox(t.slug, t.nome)); });
                enforceLimit(truquesBox, conj.truques_n, truqueCounter);
            }
            conj.magias_nv1.forEach(function (m) {
                magiasBox.appendChild(checkbox(m.slug, m.nome + (m.escola ? ' · ' + m.escola : '')));
            });
            updateMagiaLimit();
        }
        // recalcula a contagem de magias quando atributos mudam (o ASI já dispara via onAsiChange)
        if (window.PointBuy) window.PointBuy.onChange(updateMagiaLimit);

        // ---- Antecedente
        var antSel = el('cf-antecedente');
        antSel.appendChild(opt('', '— Selecione —'));
        CAT.antecedentes.forEach(function (a) { antSel.appendChild(opt(a.slug, a.nome)); });

        var bgWrap = el('cf-bg-skills');
        CAT.pericias.forEach(function (p) { bgWrap.appendChild(checkbox(p.slug, p.nome)); });
        // Perícias de CLASSE e de ANTECEDENTE são mutuamente exclusivas: uma já escolhida
        // num grupo fica bloqueada no outro (além do limite de cada grupo).
        function boxesOf(wrap) { return Array.prototype.slice.call(wrap.querySelectorAll('input[type=checkbox]')); }
        // Perícias que a raça/linhagem/essência atual concede automaticamente → {slug: fonte}.
        // Fonte única de bloqueio: alimenta applySkillRules (classe + antecedente) e as escolhas raciais.
        function grantedSkills() {
            var out = {};
            function add(list) { (list || []).forEach(function (g) { if (!(g.slug in out)) out[g.slug] = g.fonte; }); }
            // Perícia concedida por traço de CLÃ/herança (vertente) só entra quando o clã
            // escolhido casa (Furtividade só p/ Tenebrus, Acrobacia só p/ Sybaris…). As
            // compartilhadas (vertente vazia, ex.: Percepção da maldição) entram sempre.
            function addEss(list) {
                var vert = currentVertente();
                (list || []).forEach(function (g) {
                    if (g.vertente && g.vertente !== vert) return;
                    if (!(g.slug in out)) out[g.slug] = g.fonte;
                });
            }
            add((CAT.pericias_concedidas_raca || {})[racaSel.value]);
            if (!linWrap.hidden && linSel.value) add((CAT.pericias_concedidas_linhagem || {})[linSel.value]);
            if (!essWrap.hidden && essSel.value) addEss((CAT.pericias_concedidas_essencia || {})[essSel.value]);
            // Perícia GANHA (fixa) pela CLASSE (ex.: Mago/Arcanismo via 'Estudo Arcano'): entra no
            // mesmo bloqueio universal — trava nas listas de classe, antecedente e picks raciais.
            var _cls = classeBySlug[classeSel.value];
            if (_cls) add(_cls.pericias_concedidas);
            return out;
        }
        function markGrant(b, fonte) {
            var lab = b.parentNode;
            if (fonte) {
                b.checked = false;
                if (lab) { lab.title = 'já concedida por ' + fonte; lab.classList.add('cf-skill-granted'); }
            } else if (lab) { lab.removeAttribute('title'); lab.classList.remove('cf-skill-granted'); }
        }
        function applySkillRules() {
            var classN = (classeBySlug[classeSel.value] || {}).pericias_n || 0;
            var granted = grantedSkills();
            var cb = boxesOf(skillsWrap), bb = boxesOf(bgWrap);
            // Os picks raciais de PERÍCIA entram no bloqueio cruzado (idioma/ferramenta não):
            // uma perícia escolhida num pick racial trava nas listas de classe/antecedente e
            // vice-versa. `racialGroups` pode ainda estar indefinido na 1ª chamada (setup).
            var rGroups = (racialGroups || []).filter(function (g) { return g.tipo === 'pericia'; });
            // 1º passo: desmarca+trava as já concedidas pela raça em TODAS as listas
            var allBoxes = cb.concat(bb);
            rGroups.forEach(function (g) { allBoxes = allBoxes.concat(boxesOf(g.grid)); });
            allBoxes.forEach(function (b) { markGrant(b, granted[b.value]); });
            var cChk = cb.filter(function (b) { return b.checked; }), bChk = bb.filter(function (b) { return b.checked; });
            var cSel = cChk.map(function (b) { return b.value; }), bSel = bChk.map(function (b) { return b.value; });
            // união de TODAS as perícias já escolhidas nos picks raciais
            var rSelAll = [];
            rGroups.forEach(function (g) { rSelAll = rSelAll.concat(checkedVals(g.grid)); });
            function taken(v, arr) { return arr.indexOf(v) !== -1; }
            cb.forEach(function (b) { b.disabled = !b.checked && (!!granted[b.value] || cChk.length >= classN || taken(b.value, bSel) || taken(b.value, rSelAll)); });
            bb.forEach(function (b) { b.disabled = !b.checked && (!!granted[b.value] || bChk.length >= bgSkillN() || taken(b.value, cSel) || taken(b.value, rSelAll)); });
            // cada pick racial de perícia: trava se concedida, grupo cheio, ou a perícia já foi
            // escolhida em classe/antecedente/OUTRO pick racial (também gerencia seu contador).
            rGroups.forEach(function (g) {
                var gb = boxesOf(g.grid);
                var gChk = gb.filter(function (b) { return b.checked; });
                var outros = cSel.concat(bSel);
                rGroups.forEach(function (o) { if (o !== g) outros = outros.concat(checkedVals(o.grid)); });
                gb.forEach(function (b) { b.disabled = !b.checked && (!!granted[b.value] || gChk.length >= g.n || taken(b.value, outros)); });
                if (g.counter) g.counter.textContent = '(' + gChk.length + '/' + g.n + ')';
            });
            if (skillCounter) skillCounter.textContent = classN ? '(' + cChk.length + '/' + classN + ')' : '';
            var bgC = document.querySelector('[data-bgskill-counter]'); if (bgC) bgC.textContent = '(' + bChk.length + '/' + bgSkillN() + ')';
        }
        skillsWrap.addEventListener('change', applySkillRules);
        bgWrap.addEventListener('change', applySkillRules);
        applySkillRules();
        // expertise depende das perícias proficientes escolhidas (classe + antecedente)
        skillsWrap.addEventListener('change', refreshExpertise);
        bgWrap.addEventListener('change', refreshExpertise);

        var langWrap = el('cf-idiomas-lang'), toolWrap = el('cf-idiomas-tool');
        (CAT.idiomas || []).forEach(function (it) { langWrap.appendChild(checkboxDesc(it.nome, it.nome, it.desc)); });
        (CAT.ferramentas || []).forEach(function (it) { toolWrap.appendChild(checkboxDesc(it.nome, it.nome, it.desc)); });
        function idiomasFerramentasSel() { return checkedVals(langWrap).concat(checkedVals(toolWrap)); }
        // Cross-lock de IDIOMAS/FERRAMENTAS (mesmo padrão do de perícias): um idioma escolhido
        // numa fonte (pick racial de idioma OU lista do antecedente) trava o MESMO idioma na
        // outra fonte — o antecedente não deixa mais repetir um idioma já ganho na raça, e a
        // realocação é livre (desmarcou lá, reabre aqui). Gere também os limites (combinado do
        // antecedente lang+tool; próprio de cada pick racial). Ferramentas: cross-lock simétrico.
        function applyLangToolRules() {
            var lim = bgLangToolN();
            var langBoxes = boxesOf(langWrap), toolBoxes = boxesOf(toolWrap);
            var antChosen = langBoxes.concat(toolBoxes).filter(function (b) { return b.checked; }).length;
            var rLang = (racialGroups || []).filter(function (g) { return g.tipo === 'idioma'; });
            var rTool = (racialGroups || []).filter(function (g) { return g.tipo === 'ferramenta'; });
            function unionVals(antBoxes, rgs) {
                var v = antBoxes.filter(function (b) { return b.checked; }).map(function (b) { return b.value; });
                rgs.forEach(function (g) { v = v.concat(checkedVals(g.grid)); });
                return v;
            }
            var idiomaSel = unionVals(langBoxes, rLang), ferrSel = unionVals(toolBoxes, rTool);
            function has(v, arr) { return arr.indexOf(v) !== -1; }
            langBoxes.forEach(function (b) { b.disabled = !b.checked && (antChosen >= lim || has(b.value, idiomaSel)); });
            toolBoxes.forEach(function (b) { b.disabled = !b.checked && (antChosen >= lim || has(b.value, ferrSel)); });
            rLang.forEach(function (g) {
                var gChk = checkedVals(g.grid);
                boxesOf(g.grid).forEach(function (b) { b.disabled = !b.checked && (gChk.length >= g.n || has(b.value, idiomaSel)); });
                if (g.counter) g.counter.textContent = '(' + gChk.length + '/' + g.n + ')';
            });
            rTool.forEach(function (g) {
                var gChk = checkedVals(g.grid);
                boxesOf(g.grid).forEach(function (b) { b.disabled = !b.checked && (gChk.length >= g.n || has(b.value, ferrSel)); });
                if (g.counter) g.counter.textContent = '(' + gChk.length + '/' + g.n + ')';
            });
            var c = document.querySelector('[data-langtool-counter]'); if (c) c.textContent = '(' + antChosen + '/' + lim + ')';
        }
        langWrap.addEventListener('change', applyLangToolRules);
        toolWrap.addEventListener('change', applyLangToolRules);
        antSel.addEventListener('change', function () {
            updateBackgroundCopy();
            applySkillRules();
            applyLangToolRules();
            updateMagiaLimit();
        });
        updateBackgroundCopy();
        applyLangToolRules();

        // ---- Talentos
        var toSel = el('cf-talento-origem'), toDesc = el('cf-talento-origem-desc');
        var talentoOrigemById = {};
        toSel.appendChild(opt('', '— Selecione —'));
        CAT.talentos_origem.forEach(function (t) {
            talentoOrigemById[String(t.id)] = t;
            toSel.appendChild(opt(String(t.id), t.nome + (t.pre ? ' — req: ' + t.pre : '')));
        });
        toSel.addEventListener('change', function () { showTalentoDesc(toDesc, talentoOrigemById[toSel.value]); });

        var trSel = el('cf-talento-raca'), trVazio = el('cf-talento-raca-vazio'), trDesc = el('cf-talento-raca-desc');
        var talentoRacaByNome = {};
        var talentoRacaVazioPadrao = trVazio ? trVazio.textContent : '';
        // Talento da RAÇA base restrito a linhagens específicas (via pré-requisito): só aparece
        // se o personagem tiver uma dessas linhagens. Quem escolheu Essência (sem linhagem) não
        // vê exclusivos de linhagem, mas continua vendo os que aceitam 'ou Essência'.
        function talentoRacaVisivel(t) {
            if (!t.linhagens || !t.linhagens.length) return true;
            if (!linWrap.hidden && linSel.value && t.linhagens.indexOf(linSel.value) !== -1) return true;
            if (t.aceita_essencia && !essWrap.hidden && essSel.value) return true;
            return false;
        }
        function fillTalentosRaca() {
            // Fontes podem suprimir picks de outras fontes por
            // suppress:pick{talento_racial, source:raca}. A interface só aplica a
            // política declarada no catálogo; não conhece essências específicas.
            var suppressed = {};
            function addSuppressions(entries) {
                (entries || []).forEach(function (entry) {
                    var vert = currentVertente();
                    if (entry.pick === 'talento_racial'
                        && (!entry.vertente || entry.vertente === vert))
                        suppressed[entry.source] = true;
                });
            }
            addSuppressions(((CAT.pick_suppressions_raca || {})[racaSel.value] || []));
            if (!linWrap.hidden && linSel.value)
                addSuppressions(((CAT.pick_suppressions_linhagem || {})[linSel.value] || []));
            if (!essWrap.hidden && essSel.value)
                addSuppressions(((CAT.pick_suppressions_essencia || {})[essSel.value] || []));

            var lst = [];
            if (!suppressed.raca)
                ((CAT.talentos_raca || {})[racaSel.value] || []).forEach(function (t) { if (talentoRacaVisivel(t)) lst.push(t); });
            if (!suppressed.linhagem && !linWrap.hidden && linSel.value)
                ((CAT.talentos_linhagem || {})[linSel.value] || []).forEach(function (t) { lst.push(t); });
            if (!suppressed.essencia && !essWrap.hidden && essSel.value) {
                var vert = verWrap.hidden ? '' : verSel.value;
                ((CAT.talentos_essencia || {})[essSel.value] || []).forEach(function (t) {
                    // talento de vertente específica só aparece se casar com a vertente escolhida
                    if (!t.vertente || t.vertente === vert) lst.push(t);
                });
            }
            talentoRacaByNome = {};
            lst.forEach(function (t) { talentoRacaByNome[t.nome] = t; });
            trSel.innerHTML = '';
            if (trDesc) { trDesc.classList.add('hidden'); trDesc.innerHTML = ''; }
            if (!lst.length) {
                if (trVazio) trVazio.textContent = Object.keys(suppressed).length
                    ? 'A fonte selecionada substitui esta escolha por uma característica fixa.'
                    : talentoRacaVazioPadrao;
                trVazio.classList.remove('hidden'); trSel.classList.add('hidden'); return;
            }
            if (trVazio) trVazio.textContent = talentoRacaVazioPadrao;
            trVazio.classList.add('hidden'); trSel.classList.remove('hidden');
            trSel.appendChild(opt('', '— Selecione —'));
            lst.forEach(function (t) { trSel.appendChild(opt(t.nome, t.nome + (t.pre ? ' — req: ' + t.pre : ''))); });
        }
        trSel.addEventListener('change', function () { showTalentoDesc(trDesc, talentoRacaByNome[trSel.value]); });

        // ---- Escolhas de Raça (perícia/idioma/ferramenta extras), reativas à raça/linhagem/essência
        var racaEscWrap = el('cf-raca-escolhas-wrap'), racaEscBox = el('cf-raca-escolhas');
        var racialGroups = [];
        function racialOptionsFor(tipo, de) {
            if (tipo === 'pericia') {
                // perícia já concedida pela raça/linhagem/essência não é oferecida de novo
                var granted = grantedSkills();
                var ps = CAT.pericias.filter(function (p) { return !(p.slug in granted); });
                if (de && de.length) ps = ps.filter(function (p) { return de.indexOf(p.slug) !== -1; });
                return ps.map(function (p) { return { value: p.slug, label: p.nome }; });
            }
            var src = (tipo === 'idioma') ? (CAT.idiomas || []) : (CAT.ferramentas || []);
            if (de && de.length) src = src.filter(function (i) { return de.indexOf(i.nome) !== -1; });
            return src.map(function (i) { return { value: i.nome, label: i.nome, desc: i.desc }; });
        }
        function renderRacialChoices() {
            racaEscBox.innerHTML = '';
            racialGroups = [];
            var choices = [];
            ((CAT.racial_choices_raca || {})[racaSel.value] || []).forEach(function (c) { choices.push(c); });
            if (!linWrap.hidden && linSel.value)
                ((CAT.racial_choices_linhagem || {})[linSel.value] || []).forEach(function (c) { choices.push(c); });
            if (!essWrap.hidden && essSel.value) {
                // Escolha de PERÍCIA de um traço de clã (Educação Rubedo, Sangue Ruim…) só
                // aparece p/ o clã escolhido — senão o wizard obrigava a escolher a perícia do
                // Rubedo E a do Sangue Ruim juntas, sendo que são heranças MUTUAMENTE EXCLUSIVAS.
                var vert = currentVertente();
                ((CAT.racial_choices_essencia || {})[essSel.value] || []).forEach(function (c) {
                    if (!c.vertente || c.vertente === vert) choices.push(c);
                });
            }
            if (!choices.length) { racaEscWrap.hidden = true; return; }
            racaEscWrap.hidden = false;
            var lbl = { pericia: 'perícia(s)', idioma: 'idioma(s)', ferramenta: 'ferramenta(s)' };
            choices.forEach(function (ch) {
                var grp = document.createElement('div');
                var head = document.createElement('div');
                head.className = 'mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--muted)]';
                head.textContent = 'Escolha ' + ch.n + ' ' + (lbl[ch.tipo] || ch.tipo) + ' ';
                if (ch.fonte) {
                    var f = document.createElement('span');
                    f.className = 'font-normal normal-case text-[var(--muted)]'; f.textContent = '— ' + ch.fonte + ' ';
                    head.appendChild(f);
                }
                var counter = document.createElement('span'); head.appendChild(counter);
                grp.appendChild(head);
                var grid = document.createElement('div'); grid.className = 'grid grid-cols-1 gap-1 sm:grid-cols-2';
                racialOptionsFor(ch.tipo, ch.de).forEach(function (o) {
                    grid.appendChild(o.desc ? checkboxDesc(o.value, o.label, o.desc) : checkbox(o.value, o.label));
                });
                grp.appendChild(grid);
                racaEscBox.appendChild(grp);
                if (ch.tipo === 'pericia') {
                    // Perícia entra no bloqueio cruzado (classe/antecedente/outros picks):
                    // applySkillRules gerencia limite + lock + contador deste grupo.
                    grid.addEventListener('change', applySkillRules);
                    racialGroups.push({ tipo: ch.tipo, n: ch.n, grid: grid, counter: counter });
                } else {
                    // Idioma/ferramenta: cross-lock com a lista do antecedente (applyLangToolRules
                    // gerencia limite + trava de valor duplicado + contador deste grupo).
                    grid.addEventListener('change', applyLangToolRules);
                    racialGroups.push({ tipo: ch.tipo, n: ch.n, grid: grid, counter: counter });
                }
            });
            applyLangToolRules();
        }
        function racialChoicesSel() {
            var out = { pericias: [], idiomas: [], ferramentas: [] };
            racialGroups.forEach(function (g) {
                var vals = checkedVals(g.grid);
                if (g.tipo === 'pericia') out.pericias = out.pericias.concat(vals);
                else if (g.tipo === 'idioma') out.idiomas = out.idiomas.concat(vals);
                else out.ferramentas = out.ferramentas.concat(vals);
            });
            return out;
        }
        // Painel "Perícias concedidas": lista as perícias que a raça/linhagem/essência (clã)
        // concede automaticamente, com a fonte — MESMO padrão dos traços que concedem perícia.
        // Antes, uma perícia auto-concedida (ex.: Percepção da Maldição Vampírica) só aparecia
        // depois, na prévia da ficha; o wizard não indicava que ela já era garantida.
        var periciaNomeBySlug = {}; (CAT.pericias || []).forEach(function (p) { periciaNomeBySlug[p.slug] = p.nome; });
        var concedidasWrap = el('cf-pericias-concedidas-wrap'), concedidasBox = el('cf-pericias-concedidas');
        function renderPericiasConcedidas() {
            if (!concedidasWrap || !concedidasBox) return;
            var granted = grantedSkills(), slugs = Object.keys(granted);
            if (!slugs.length) { concedidasWrap.hidden = true; concedidasBox.innerHTML = ''; return; }
            slugs.sort(function (a, b) { return (periciaNomeBySlug[a] || a).localeCompare(periciaNomeBySlug[b] || b); });
            concedidasBox.innerHTML = '';
            slugs.forEach(function (sl) {
                var chip = document.createElement('span');
                chip.className = 'cf-skill-granted inline-flex items-center gap-1 rounded border border-[var(--stroke)] bg-[var(--bg0)] px-2 py-0.5 text-xs';
                chip.innerHTML = '<span class="text-[var(--text)]">' + escHtml(periciaNomeBySlug[sl] || sl) + '</span>' +
                                 '<span class="text-[var(--muted)]">— ' + escHtml(granted[sl]) + '</span>';
                concedidasBox.appendChild(chip);
            });
            concedidasWrap.hidden = false;
        }
        function refreshRaceDependent() {
            fillTalentosRaca(); renderRacialChoices();
            // as perícias concedidas dependem da raça/linhagem/essência: reavalia bloqueios
            applySkillRules(); refreshExpertise(); renderPericiasConcedidas();
        }

        linSel.addEventListener('change', refreshRaceDependent);
        essSel.addEventListener('change', refreshRaceDependent);
        // trocar a sub-escolha (vertente/clã) muda os talentos, as escolhas de perícia da
        // herança E as perícias concedidas — reavalia tudo que depende da raça/essência.
        verSel.addEventListener('change', refreshRaceDependent);
        refreshRaceDependent();

        // ================= Painéis de INFO (escolha informada — U2) =================
        function escHtml(s) { var d = document.createElement('div'); d.textContent = (s == null ? '' : String(s)); return d.innerHTML; }
        function infoMetaHtml(meta) {
            return '<div class="cf-info-meta">' + meta.map(function (m) {
                return '<span class="cf-chip">' + escHtml(m.k) + ' <b>' + escHtml(m.v) + '</b></span>';
            }).join('') + '</div>';
        }
        function infoLoreHtml(opts) {
            var h = '';
            if (opts.tagline) h += '<div class="cf-info-tagline">' + escHtml(String(opts.tagline).replace(/[*_`>#]/g, '').trim()) + '</div>';
            if (opts.resumo) h += '<div class="cf-info-resumo">' + escHtml(opts.resumo) + '</div>';
            if (opts.meta && opts.meta.length) h += infoMetaHtml(opts.meta);
            return h;
        }
        function infoTraitsHtml(traits) {
            return '<div class="cf-info-list">' + traits.map(function (t) {
                return '<div class="cf-info-trait"><b>' + escHtml(t.nome) + '</b>' +
                    (t.desc ? ' <span>— ' + escHtml(t.desc) + '</span>' : '') + '</div>';
            }).join('') + '</div>';
        }
        var _infoTab = 'tracos';  // preferência de aba (Traços default), persiste entre re-renders
        function fillInfoTabs(box, opts) {
            var traitsHtml = (opts.traits && opts.traits.length) ? infoTraitsHtml(opts.traits) : '';
            var loreHtml = infoLoreHtml(opts);
            if (!traitsHtml) {  // sem traços mecânicos (ex.: essência sem traços): só a lore, sem abas
                box.innerHTML = loreHtml || '<div class="cf-info-resumo">Sem descrição cadastrada.</div>';
                box.hidden = false; return;
            }
            var tab = _infoTab;
            box.innerHTML =
                '<div class="cf-info-tabs" role="tablist">' +
                  '<button type="button" class="cf-info-tab' + (tab === 'tracos' ? ' is-active' : '') + '" data-info-tab="tracos">Traços</button>' +
                  '<button type="button" class="cf-info-tab' + (tab === 'lore' ? ' is-active' : '') + '" data-info-tab="lore">Lore</button>' +
                '</div>' +
                '<div class="cf-info-pane" data-info-pane="tracos"' + (tab === 'tracos' ? '' : ' hidden') + '>' + traitsHtml + '</div>' +
                '<div class="cf-info-pane" data-info-pane="lore"' + (tab === 'lore' ? '' : ' hidden') + '>' +
                    (loreHtml || '<div class="cf-info-resumo">Sem lore cadastrada.</div>') + '</div>';
            box.hidden = false;
            Array.prototype.forEach.call(box.querySelectorAll('.cf-info-tab'), function (btn) {
                btn.addEventListener('click', function () {
                    _infoTab = btn.getAttribute('data-info-tab');
                    Array.prototype.forEach.call(box.querySelectorAll('.cf-info-tab'), function (b) { b.classList.toggle('is-active', b === btn); });
                    Array.prototype.forEach.call(box.querySelectorAll('.cf-info-pane'), function (p) { p.hidden = (p.getAttribute('data-info-pane') !== _infoTab); });
                });
            });
        }
        function fillInfo(box, opts) {
            if (!box) return;
            if (!opts) { box.hidden = true; box.innerHTML = ''; return; }
            if (opts.tabs) { fillInfoTabs(box, opts); return; }
            var h = infoLoreHtml(opts);
            if (opts.traits && opts.traits.length) h += infoTraitsHtml(opts.traits);
            box.innerHTML = h || '<div class="cf-info-resumo">Sem descrição cadastrada.</div>';
            box.hidden = false;
        }
        function renderRacaInfo() {
            var r = racaBySlug[racaSel.value];
            if (!r) { fillInfo(el('cf-raca-info'), null); return; }
            var traits = (r.tracos || []).slice();
            if (!linWrap.hidden && linSel.value) {
                var lobj = (r.linhagens || []).filter(function (l) { return l.slug === linSel.value; })[0];
                if (lobj && lobj.desc) traits.unshift({ nome: 'Linhagem: ' + lobj.nome, desc: lobj.desc });
            }
            // Traços são o conteúdo principal (aba default); lore na segunda aba. Sem corte a 6.
            fillInfo(el('cf-raca-info'), { tabs: true, tagline: r.tagline, resumo: r.resumo, traits: traits });
        }
        function renderEssenciaInfo() {
            var e = essenciaBySlug[essSel.value];
            fillInfo(el('cf-essencia-info'), (essWrap.hidden || !e) ? null
                : { tabs: true, tagline: 'Essência: ' + e.nome, resumo: e.resumo, traits: (e.tracos || []).slice() });
        }
        function renderClasseInfo() {
            var c = classeBySlug[classeSel.value];
            if (!c) { fillInfo(el('cf-classe-info'), null); return; }
            var meta = [];
            if (c.hit_die) meta.push({ k: 'Dado de vida', v: 'd' + c.hit_die });
            if (c.saves && c.saves.length) meta.push({ k: 'Resistências', v: c.saves.join(', ') });
            if (c.atributo_principal) meta.push({ k: 'Atributo', v: c.atributo_principal });
            fillInfo(el('cf-classe-info'), { tagline: c.tagline, resumo: c.resumo, meta: meta, traits: (c.features1 || []).slice(0, 6) });
        }
        function renderAntecedenteInfo() {
            var a = antecedenteBySlug[antSel.value];
            if (!a) { fillInfo(el('cf-antecedente-info'), null); return; }
            var g = a.grants || {};
            var meta = [{ k: 'PO inicial', v: (g.po_inicial || 0) },
                        { k: 'Perícias', v: (g.pericias || 0) },
                        { k: 'ASI', v: (g.asi || '+2/+1') }];
            fillInfo(el('cf-antecedente-info'), { resumo: a.resumo, meta: meta });
        }
        racaSel.addEventListener('change', renderRacaInfo);
        linSel.addEventListener('change', renderRacaInfo);
        essSel.addEventListener('change', function () { renderEssenciaInfo(); renderRacaInfo(); });
        verSel.addEventListener('change', renderRacaInfo);
        classeSel.addEventListener('change', renderClasseInfo);
        antSel.addEventListener('change', renderAntecedenteInfo);
        renderRacaInfo(); renderEssenciaInfo(); renderClasseInfo(); renderAntecedenteInfo();

        // ================= Validação por etapa (U3) =================
        var erroBox = el('cf-erros'), submitBtn = el('cf-submit');
        var _lblEsc = { pericia: 'perícia(s)', idioma: 'idioma(s)', ferramenta: 'ferramenta(s)' };

        var STEP_VALIDATORS = [
            function () { // 0 · Identidade + Atributos
                var e = [];
                if (!el('cf-nome').value.trim()) e.push('Dê um nome ao personagem.');
                var vals = asiActiveSelects().map(function (s) { return s.value; });
                if (vals.some(function (v, i) { return vals.indexOf(v) !== i; }))
                    e.push('Os aumentos do ASI devem ir em atributos diferentes.');
                return e;
            },
            function () { // 1 · Raça
                var e = [];
                if (!racaSel.value) e.push('Escolha uma raça.');
                if (!verWrap.hidden && !verSel.value) {
                    var _es = essenciaBySlug[essSel.value];
                    e.push('Escolha ' + ((_es && _es.subescolha_label) ? ('o ' + _es.subescolha_label) : 'a vertente elemental') + '.');
                }
                racialGroups.forEach(function (g) {
                    if (checkedVals(g.grid).length !== g.n)
                        e.push('Escolhas de raça: selecione ' + g.n + ' ' + (_lblEsc[g.tipo] || g.tipo) + '.');
                });
                return e;
            },
            function () { // 2 · Classe
                var e = [], c = classeBySlug[classeSel.value];
                if (!classeSel.value) { e.push('Escolha uma classe.'); return e; }
                if (c && checkedVals(skillsWrap).length !== c.pericias_n)
                    e.push('Escolha exatamente ' + c.pericias_n + ' perícia(s) de classe.');
                // escolhas genéricas dirigidas por tags pick:* (Maestria de Arma, Estilo de Luta, …)
                pickGroupState.forEach(function (g) {
                    var meta = ((c && c.pick_groups) || []).filter(function (x) { return x.kind === g.kind && x.tipo === g.tipo; })[0];
                    var need = meta ? meta.n : 0;
                    // cada checkbox marcado = uma escolha (para Maestria de Arma, um PAR
                    // arma+maestria; a mesma arma pode contribuir com mais de um).
                    var marcados = Array.prototype.slice.call(g.grid.querySelectorAll('input[type=checkbox]')).filter(function (cb) { return cb.checked; });
                    if (need && marcados.length !== need)
                        e.push('Escolha ' + need + ' ' + (meta.label || meta.tipo || 'opção(ões)') + '.');
                });
                if (c && c.expertise_n && checkedVals(expertiseBox).length !== c.expertise_n)
                    e.push('Escolha ' + c.expertise_n + ' perícia(s) para Especialização.');
                classeProfGroups.forEach(function (g) {
                    if (checkedVals(g.grid).length !== g.n)
                        e.push('Escolha ' + g.n + ' ' + classeProfLabel(g.tipo) + ' de classe.');
                });
                if (c && c.conjuracao) {
                    if (c.conjuracao.truques_n && checkedVals(truquesBox).length !== c.conjuracao.truques_n)
                        e.push('Escolha ' + c.conjuracao.truques_n + ' truque(s).');
                    if (checkedVals(magiasBox).length !== magiaLimit)
                        e.push('Escolha ' + magiaLimit + ' magia(s) de 1º nível.');
                }
                return e;
            },
            function () { // 3 · Antecedente
                var e = [];
                if (!antSel.value) { e.push('Escolha um antecedente.'); return e; }
                if (checkedVals(bgWrap).length !== bgSkillN()) e.push('Escolha ' + bgSkillN() + ' perícia(s) do antecedente.');
                if (idiomasFerramentasSel().length !== bgLangToolN()) e.push('Escolha ' + bgLangToolN() + ' idioma(s)/ferramenta(s).');
                return e;
            },
            function () { // 4 · Talentos
                var e = [];
                if (antSel.value && toSel.options.length > 1 && !toSel.value)
                    e.push('Escolha o Talento de Origem concedido pelo antecedente.');
                if (!trSel.classList.contains('hidden') && trSel.options.length > 1 && !trSel.value)
                    e.push('Escolha o Talento Racial concedido no nível 1.');
                return e;
            },
            function () { return []; } // 5 · Revisão
        ];
        function stepErrors(i) { try { return STEP_VALIDATORS[i] ? STEP_VALIDATORS[i]() : []; } catch (err) { return []; } }
        function clientValidate() {
            var all = [];
            for (var i = 0; i < STEP_VALIDATORS.length; i++) all = all.concat(stepErrors(i));
            return all;
        }

        // ================= Stepper (U1) =================
        var steps = Array.prototype.slice.call(document.querySelectorAll('.cf-step'));
        var tabs = Array.prototype.slice.call(document.querySelectorAll('.cf-step-tab'));
        var prevBtn = document.querySelector('[data-prev]');
        var nextBtn = document.querySelector('[data-next]');
        var navHint = el('cf-nav-hint');
        var LAST = steps.length - 1;
        var current = 0;
        var touched = {};

        function stepErrBox(i) { return document.querySelector('[data-step-err="' + i + '"]'); }
        function showStepErr(i, arr) {
            var box = stepErrBox(i);
            if (!box) return;
            if (!arr || !arr.length) { box.hidden = true; box.innerHTML = ''; return; }
            box.innerHTML = '<strong>Faltam ' + arr.length + ' item(ns) nesta etapa:</strong><ul>' +
                arr.map(function (x) { return '<li>' + escHtml(x) + '</li>'; }).join('') + '</ul>';
            box.hidden = false;
        }
        function updateStepper() {
            tabs.forEach(function (t, idx) {
                var errs = stepErrors(idx);
                t.classList.toggle('is-current', idx === current);
                t.classList.toggle('is-complete', errs.length === 0);
                t.classList.toggle('is-error', !!touched[idx] && errs.length > 0);
            });
            var e = stepErrors(current);
            var totalPend = clientValidate().length;
            if (current === LAST) {
                navHint.textContent = totalPend ? ('faltam ' + totalPend + ' item(ns) para criar') : 'tudo pronto — pode criar!';
                submitBtn.textContent = totalPend ? ('Criar (faltam ' + totalPend + ')') : 'Criar Personagem';
            } else {
                navHint.textContent = e.length ? ('faltam ' + e.length + ' nesta etapa') : '';
            }
        }
        function refreshCurrentErrors() {
            if (touched[current]) showStepErr(current, stepErrors(current));
            updateStepper();
        }
        function goTo(i, noscroll) {
            i = Math.max(0, Math.min(LAST, i));
            current = i;
            steps.forEach(function (s, idx) { s.hidden = idx !== i; });
            prevBtn.disabled = (i === 0);
            nextBtn.hidden = (i === LAST);
            submitBtn.hidden = (i !== LAST);
            showStepErr(i, touched[i] ? stepErrors(i) : []);
            if (i === LAST) renderReview();
            updateStepper();
            if (!noscroll) { try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) { window.scrollTo(0, 0); } }
        }
        tabs.forEach(function (t) {
            function jump() { goTo(parseInt(t.getAttribute('data-step-tab'), 10)); }
            t.addEventListener('click', jump);
            t.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); jump(); } });
        });
        nextBtn.addEventListener('click', function () {
            var e = stepErrors(current);
            touched[current] = true;
            if (e.length) { showStepErr(current, e); updateStepper(); return; }
            showStepErr(current, []);
            goTo(current + 1);
        });
        prevBtn.addEventListener('click', function () { goTo(current - 1); });

        function renderReview() {
            var box = el('cf-review');
            if (!box) return;
            function racaText() {
                var r = racaBySlug[racaSel.value]; if (!r) return '—';
                var out = r.nome;
                if (!linWrap.hidden && linSel.value) { var l = (r.linhagens || []).filter(function (x) { return x.slug === linSel.value; })[0]; if (l) out += ' · ' + l.nome; }
                if (!essWrap.hidden && essSel.value) { var es = essenciaBySlug[essSel.value]; if (es) out += ' · ' + es.nome; }
                return out;
            }
            var c = classeBySlug[classeSel.value];
            var a = antecedenteBySlug[antSel.value];
            var toTxt = (toSel.value && toSel.options[toSel.selectedIndex]) ? toSel.options[toSel.selectedIndex].textContent : '—';
            var rows = [
                ['Nome', el('cf-nome').value.trim() || '—'],
                ['Raça', racaText()],
                ['Classe', c ? c.nome : '—'],
                ['Antecedente', a ? a.nome : '—'],
                ['Talento de origem', toTxt]
            ];
            var h = rows.map(function (r) {
                return '<div class="flex justify-between gap-3 border-b border-[var(--stroke)] py-1"><span class="text-[var(--muted)]">' +
                    escHtml(r[0]) + '</span><span class="text-right font-semibold">' + escHtml(r[1]) + '</span></div>';
            }).join('');
            var pend = clientValidate();
            if (pend.length) {
                h += '<div class="cf-step-err" style="display:block;margin-top:.7rem"><strong>' +
                    (window.CRIAR_PATHBUILDER ? 'Pendências antes de simular:' : 'Pendências antes de criar:') +
                    '</strong><ul>' +
                    pend.map(function (x) { return '<li>' + escHtml(x) + '</li>'; }).join('') + '</ul></div>';
            } else {
                h += '<p class="mt-2 text-xs text-[var(--spark)]">' +
                    (window.CRIAR_PATHBUILDER
                        ? 'Tudo certo — esta base pode ser levada ao laboratório.'
                        : 'Tudo certo — a ficha bate com a prévia ao lado.') + '</p>';
            }
            box.innerHTML = h;
        }

        // ================= Preview AO VIVO (U4) =================
        var pvEl = document.querySelector('#cf-preview [data-pv]');
        var caEl = document.querySelector('#cf-preview [data-ca]');
        var pbEl = document.querySelector('#cf-preview [data-pb]');
        var attrsEl = el('cf-preview-attrs');
        var extraEl = el('cf-preview-extra');
        var statusEl = el('cf-preview-status');
        var nameEl = el('cf-preview-name');
        var subEl = el('cf-preview-sub');
        var previewTimer = null, previewSeq = 0;

        function localAttrs() {
            var scores = window.PointBuy ? window.PointBuy.scores() : {};
            return SIG.map(function (p) {
                var sig = p[0];
                var v = (scores[sig] || 8) + asiAdd(sig);
                return { sig: sig, valor: v, mod: Math.floor((v - 10) / 2), save_prof: false };
            });
        }
        function renderAttrs(list) {
            attrsEl.innerHTML = list.map(function (a) {
                return '<div class="cf-attr' + (a.save_prof ? ' save-prof' : '') + '"><span class="s">' + a.sig +
                    '</span><span class="m">' + (a.mod >= 0 ? '+' : '') + a.mod + '</span><span class="t">' + a.valor + '</span></div>';
            }).join('');
        }
        function chips(arr) {
            if (!arr || !arr.length) return '<span class="cf-prev-empty">—</span>';
            return '<div class="cf-prev-chips">' + arr.map(function (x) { return '<span class="cf-chip">' + escHtml(x) + '</span>'; }).join('') + '</div>';
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
        function updateName() {
            var nome = el('cf-nome').value.trim();
            var c = classeBySlug[classeSel.value], r = racaBySlug[racaSel.value];
            var sub = [r ? r.nome : null, c ? c.nome : null].filter(Boolean).join(' · ');
            nameEl.childNodes[0] && (nameEl.childNodes[0].nodeValue = (nome || 'Novo personagem') + ' ');
            subEl.textContent = sub;
        }
        function renderLocal() { renderAttrs(localAttrs()); updateName(); }
        function runPreview() {
            renderLocal();
            var ready = racaSel.value && classeSel.value && antSel.value;
            if (!ready) {
                pvEl.textContent = '—'; caEl.textContent = '—';
                statusEl.textContent = 'monte raça, classe e antecedente';
                statusEl.classList.remove('is-live');
                extraEl.innerHTML = '<p class="cf-preview-placeholder">Assim que você escolher raça, classe e antecedente, a prévia mostra PV, CA, perícias e proficiências — exatamente como a ficha final.</p>';
                return;
            }
            var seq = ++previewSeq;
            statusEl.textContent = 'atualizando…'; statusEl.classList.add('is-live');
            fetch(window.CRIAR_PREVIEW_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                body: JSON.stringify(payload())
            }).then(function (r) { return r.json(); }).then(function (j) {
                if (seq !== previewSeq) return; // resposta obsoleta
                statusEl.classList.remove('is-live');
                if (!j || !j.ready || !j.preview) { statusEl.textContent = 'nível 1'; return; }
                var pv = j.preview;
                pvEl.textContent = pv.pv == null ? '—' : pv.pv;
                caEl.textContent = pv.ca == null ? '—' : pv.ca;
                pbEl.textContent = (pv.pb >= 0 ? '+' : '') + pv.pb;
                statusEl.textContent = 'nível ' + (pv.nivel || 1) + (pv.pv_completo ? '' : ' (PV parcial)');
                renderAttrs(pv.atributos || localAttrs());
                extraEl.innerHTML = buildExtra(pv);
            }).catch(function () {
                if (seq !== previewSeq) return;
                statusEl.classList.remove('is-live'); statusEl.textContent = 'nível 1';
            });
        }
        function schedulePreview() {
            renderLocal();
            refreshCurrentErrors();
            clearTimeout(previewTimer);
            previewTimer = setTimeout(runPreview, 280);
        }
        form.addEventListener('change', schedulePreview);
        form.addEventListener('input', function (ev) { if (ev.target && ev.target.id === 'cf-nome') { updateName(); refreshCurrentErrors(); } });
        if (window.PointBuy) window.PointBuy.onChange(function () { renderLocal(); clearTimeout(previewTimer); previewTimer = setTimeout(runPreview, 280); });

        // legado: alguns caminhos ainda chamam showErros (submit agregado)
        function showErros(arr) {
            erroBox.innerHTML = '';
            if (!arr || !arr.length) { erroBox.classList.add('hidden'); return; }
            var ul = document.createElement('ul'); ul.className = 'list-inside list-disc';
            arr.forEach(function (e) { var li = document.createElement('li'); li.textContent = e; ul.appendChild(li); });
            erroBox.appendChild(ul);
            erroBox.classList.remove('hidden');
        }

        goTo(0, true);
        runPreview();

        function payload() {
            var equip = (form.querySelector('input[name=equip_classe]:checked') || {}).value;
            return {
                nome: el('cf-nome').value.trim(),
                scores: window.PointBuy ? window.PointBuy.scores() : {},
                asi: { modo: asiModo(), attrs: asiActiveSelects().map(function (s) { return s.value; }) },
                raca: racaSel.value,
                linhagem: linWrap.hidden ? '' : linSel.value,
                essencia: essWrap.hidden ? '' : essSel.value,
                vertente: verWrap.hidden ? '' : verSel.value,
                classe: classeSel.value,
                pericias_classe: checkedVals(skillsWrap),
                equip_classe: equip === 'inicial' ? 'inicial' : 'ouro',
                picks: pickGroupsSel(),
                expertise: expertiseWrap.hidden ? [] : checkedVals(expertiseBox),
                escolhas_classe_prof: classeProfChoicesSel(),
                truques: magiasWrap.hidden ? [] : checkedVals(truquesBox),
                magias: magiasWrap.hidden ? [] : checkedVals(magiasBox),
                antecedente: antSel.value,
                pericias_antecedente: checkedVals(bgWrap),
                idiomas_ferramentas: idiomasFerramentasSel(),
                escolhas_raca: racialChoicesSel(),
                talento_origem: toSel.value || null,
                talento_raca: trSel.classList.contains('hidden') ? '' : (trSel.value || '')
            };
        }

        function firstBadStep() {
            for (var i = 0; i < STEP_VALIDATORS.length; i++) { if (stepErrors(i).length) return i; }
            return -1;
        }
        form.addEventListener('submit', function (ev) {
            ev.preventDefault();
            var errs = clientValidate();
            if (errs.length) {
                // marca tudo como visitado, leva à 1ª etapa pendente e mostra o erro NELA (U3)
                for (var i = 0; i < STEP_VALIDATORS.length; i++) touched[i] = true;
                var bad = firstBadStep();
                showErros(errs);
                if (bad >= 0 && bad !== current) goTo(bad); else { renderReview(); updateStepper(); }
                return;
            }
            if (!window.CRIAR_LOGADO) { showErros(['Você precisa estar logado para salvar. Faça login e tente novamente.']); return; }
            showErros([]);
            var submittedPayload = payload();
            submitBtn.disabled = true;
            submitBtn.textContent = window.CRIAR_PATHBUILDER ? 'Abrindo…' : 'Salvando…';
            fetch(window.CRIAR_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                body: JSON.stringify(submittedPayload)
            }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
              .then(function (res) {
                  if (res.ok && res.j.ok) {
                      if (window.CRIAR_PATHBUILDER) {
                          sessionStorage.setItem('bonfire:pathbuilder:base', JSON.stringify(submittedPayload));
                          sessionStorage.removeItem('bonfire:pathbuilder:builds');
                      }
                      window.location.href = res.j.redirect;
                      return;
                  }
                  showErros((res.j && res.j.erros) || ['Erro ao salvar a ficha.']);
                  submitBtn.disabled = false;
                  submitBtn.textContent = window.CRIAR_SUBMIT_LABEL || 'Criar Personagem';
              }).catch(function () {
                  showErros(['Erro de rede ao salvar.']);
                  submitBtn.disabled = false;
                  submitBtn.textContent = window.CRIAR_SUBMIT_LABEL || 'Criar Personagem';
              });
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
