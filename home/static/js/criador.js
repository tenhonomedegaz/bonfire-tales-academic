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
        function currentAsiParts() {
            var m = String(currentBgGrants().asi || '+2/+1').match(/\+?\s*(\d+)\s*\/\s*\+?\s*(\d+)/);
            return { major: m ? parseInt(m[1], 10) : 2, minor: m ? parseInt(m[2], 10) : 1 };
        }
        function bgSkillN() { return toInt(currentBgGrants().pericias, 0); }
        function bgLangToolN() { return toInt(currentBgGrants().idiomas_ou_ferramentas, 0); }

        // ---- ASI (+2 / +1)
        var asi2 = el('cf-asi2'), asi1 = el('cf-asi1');
        SIG.forEach(function (p) { asi2.appendChild(opt(p[0], p[1])); asi1.appendChild(opt(p[0], p[1])); });
        asi2.value = 'DES'; asi1.value = 'CON';
        // +2 e +1 do antecedente DEVEM ir em atributos diferentes: desabilita no outro select
        // a opção já escolhida e, se colidirem, empurra o +1 para o próximo atributo livre.
        function syncAsi() {
            Array.prototype.forEach.call(asi1.options, function (o) { o.disabled = (o.value === asi2.value); });
            Array.prototype.forEach.call(asi2.options, function (o) { o.disabled = (o.value === asi1.value); });
            if (asi1.value === asi2.value) {
                for (var i = 0; i < asi1.options.length; i++) {
                    if (asi1.options[i].value !== asi2.value) { asi1.value = asi1.options[i].value; break; }
                }
            }
        }
        asi2.addEventListener('change', syncAsi);
        asi1.addEventListener('change', syncAsi);
        syncAsi();

        function updateBackgroundCopy() {
            var g = currentBgGrants();
            var asi = currentAsiParts();
            var majorLabel = document.querySelector('[data-asi-major-label]');
            var minorLabel = document.querySelector('[data-asi-minor-label]');
            if (majorLabel) majorLabel.textContent = '+' + asi.major;
            if (minorLabel) minorLabel.textContent = '+' + asi.minor;
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

        function onEssencia() {
            var ess = essenciaBySlug[essSel.value];
            var vertentes = (ess && ess.vertentes && ess.vertentes.length) ? ess.vertentes : [];
            if (vertentes.length) {
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
        var maestriaWrap = el('cf-maestria-wrap');
        var maestriaArmas = el('cf-maestria-armas');
        var maestriaCounter = document.querySelector('[data-maestria-counter]');
        var maestriaBusca = el('cf-maestria-busca');
        if (maestriaBusca) maestriaBusca.addEventListener('input', function () {
            var q = (maestriaBusca.value || '').toLowerCase().trim();
            Array.prototype.forEach.call(maestriaArmas.querySelectorAll('.cf-maestria-item'), function (it) {
                it.style.display = (!q || (it.dataset.nome || '').indexOf(q) !== -1) ? '' : 'none';
            });
        });

        function maestriaCard(w) {
            var lab = document.createElement('label');
            lab.className = 'cf-maestria-item flex cursor-pointer flex-col gap-0.5 rounded border border-[var(--stroke)] bg-[var(--bg1)] px-2 py-1.5 hover:border-[var(--ember)]';
            lab.dataset.nome = (w.nome || '').toLowerCase();
            var top = document.createElement('div'); top.className = 'flex items-center gap-2';
            var inp = document.createElement('input'); inp.type = 'checkbox'; inp.value = w.slug;
            var nm = document.createElement('span'); nm.className = 'text-sm font-semibold text-[var(--text)]'; nm.textContent = w.nome;
            var dano = document.createElement('span'); dano.className = 'ml-auto text-[11px] text-[var(--muted)]'; dano.textContent = w.dano || '';
            top.appendChild(inp); top.appendChild(nm); top.appendChild(dano);
            lab.appendChild(top);
            if (w.maestrias && w.maestrias.length) {
                var chips = document.createElement('div'); chips.className = 'flex flex-wrap gap-1';
                w.maestrias.forEach(function (m) {
                    var ch = document.createElement('span');
                    ch.className = 'rounded bg-[var(--bg0)] px-1.5 py-0.5 text-[10px] text-[var(--spark)]';
                    ch.textContent = m; chips.appendChild(ch);
                });
                lab.appendChild(chips);
            }
            return lab;
        }
        function renderMaestria(c) {
            maestriaArmas.innerHTML = '';
            if (maestriaBusca) maestriaBusca.value = '';
            var n = (c && c.maestria_n) || 0;
            if (!n) { maestriaWrap.hidden = true; return; }
            maestriaWrap.hidden = false;
            // agrupa as armas por categoria (Arma Simples, Marcial, etc.) com cartões + chips de maestria
            var grupos = {}, ordem = [];
            (CAT.armas || []).forEach(function (w) {
                var cat = w.cat || 'Arma';
                if (!grupos[cat]) { grupos[cat] = []; ordem.push(cat); }
                grupos[cat].push(w);
            });
            ordem.forEach(function (cat) {
                var h = document.createElement('div');
                h.className = 'mb-1 mt-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]/80 first:mt-0';
                h.textContent = cat;
                maestriaArmas.appendChild(h);
                var grid = document.createElement('div');
                grid.className = 'grid grid-cols-1 gap-1 sm:grid-cols-2';
                grupos[cat].forEach(function (w) { grid.appendChild(maestriaCard(w)); });
                maestriaArmas.appendChild(grid);
            });
            enforceLimit(maestriaArmas, n, maestriaCounter);
        }

        function renderClasseSkills() {
            var c = classeBySlug[classeSel.value];
            skillsWrap.innerHTML = '';
            renderMaestria(c);
            renderEstilo(c);
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

        // ---- Estilo de Luta (Guerreiro) + Especialização/expertise (Ladino)
        var estiloWrap = el('cf-estilo-wrap'), estiloSel = el('cf-estilo');
        var expertiseWrap = el('cf-expertise-wrap'), expertiseBox = el('cf-expertise');
        var expertiseCounter = document.querySelector('[data-expertise-counter]');
        var classeProfWrap = el('cf-classe-prof-wrap'), classeProfBox = el('cf-classe-prof');
        var classeProfGroups = [];

        function renderEstilo(c) {
            if (c && c.estilo_n) {
                if (!estiloSel.options.length) {
                    estiloSel.appendChild(opt('', '— Selecione —'));
                    (CAT.estilos_luta || []).forEach(function (e) { estiloSel.appendChild(opt(e.slug, e.nome)); });
                }
                estiloWrap.hidden = false;
            } else { estiloWrap.hidden = true; }
        }

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
            var asi = currentAsiParts();
            var scores = window.PointBuy ? window.PointBuy.scores() : {};
            var ctx = { classlvl: 1, lvl: 1 };
            Object.keys(SIG_AB).forEach(function (ab) {
                var sig = SIG_AB[ab];
                var sc = (scores[sig] || 8) + (asi2.value === sig ? asi.major : 0) + (asi1.value === sig ? asi.minor : 0);
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
        // recalcula a contagem de magias quando atributos/ASI mudam
        if (window.PointBuy) window.PointBuy.onChange(updateMagiaLimit);
        asi2.addEventListener('change', updateMagiaLimit);
        asi1.addEventListener('change', updateMagiaLimit);

        // ---- Antecedente
        var antSel = el('cf-antecedente');
        antSel.appendChild(opt('', '— Selecione —'));
        CAT.antecedentes.forEach(function (a) { antSel.appendChild(opt(a.slug, a.nome)); });

        var bgWrap = el('cf-bg-skills');
        CAT.pericias.forEach(function (p) { bgWrap.appendChild(checkbox(p.slug, p.nome)); });
        // Perícias de CLASSE e de ANTECEDENTE são mutuamente exclusivas: uma já escolhida
        // num grupo fica bloqueada no outro (além do limite de cada grupo).
        function boxesOf(wrap) { return Array.prototype.slice.call(wrap.querySelectorAll('input[type=checkbox]')); }
        function applySkillRules() {
            var classN = (classeBySlug[classeSel.value] || {}).pericias_n || 0;
            var cb = boxesOf(skillsWrap), bb = boxesOf(bgWrap);
            var cChk = cb.filter(function (b) { return b.checked; }), bChk = bb.filter(function (b) { return b.checked; });
            var cSel = cChk.map(function (b) { return b.value; }), bSel = bChk.map(function (b) { return b.value; });
            cb.forEach(function (b) { b.disabled = !b.checked && (cChk.length >= classN || bSel.indexOf(b.value) !== -1); });
            bb.forEach(function (b) { b.disabled = !b.checked && (bChk.length >= bgSkillN() || cSel.indexOf(b.value) !== -1); });
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
        var updateLangToolLimit = enforceLimitGroup([langWrap, toolWrap], bgLangToolN, document.querySelector('[data-langtool-counter]'));
        function idiomasFerramentasSel() { return checkedVals(langWrap).concat(checkedVals(toolWrap)); }
        antSel.addEventListener('change', function () {
            updateBackgroundCopy();
            applySkillRules();
            updateLangToolLimit();
            updateMagiaLimit();
        });
        updateBackgroundCopy();
        updateLangToolLimit();

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
        function fillTalentosRaca() {
            // junta talentos da RAÇA (sempre) + da linhagem e da essência atualmente selecionadas
            var lst = [];
            ((CAT.talentos_raca || {})[racaSel.value] || []).forEach(function (t) { lst.push(t); });
            if (!linWrap.hidden && linSel.value)
                ((CAT.talentos_linhagem || {})[linSel.value] || []).forEach(function (t) { lst.push(t); });
            if (!essWrap.hidden && essSel.value) {
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
            if (!lst.length) { trVazio.classList.remove('hidden'); trSel.classList.add('hidden'); return; }
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
                var ps = CAT.pericias;
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
            if (!essWrap.hidden && essSel.value)
                ((CAT.racial_choices_essencia || {})[essSel.value] || []).forEach(function (c) { choices.push(c); });
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
                enforceLimit(grid, ch.n, counter);
                racialGroups.push({ tipo: ch.tipo, n: ch.n, grid: grid });
            });
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
        function refreshRaceDependent() { fillTalentosRaca(); renderRacialChoices(); }

        linSel.addEventListener('change', refreshRaceDependent);
        essSel.addEventListener('change', refreshRaceDependent);
        verSel.addEventListener('change', fillTalentosRaca);
        refreshRaceDependent();

        // ================= Painéis de INFO (escolha informada — U2) =================
        function escHtml(s) { var d = document.createElement('div'); d.textContent = (s == null ? '' : String(s)); return d.innerHTML; }
        function fillInfo(box, opts) {
            if (!box) return;
            if (!opts) { box.hidden = true; box.innerHTML = ''; return; }
            var h = '';
            if (opts.tagline) h += '<div class="cf-info-tagline">' + escHtml(String(opts.tagline).replace(/[*_`>#]/g, '').trim()) + '</div>';
            if (opts.resumo) h += '<div class="cf-info-resumo">' + escHtml(opts.resumo) + '</div>';
            if (opts.meta && opts.meta.length) {
                h += '<div class="cf-info-meta">' + opts.meta.map(function (m) {
                    return '<span class="cf-chip">' + escHtml(m.k) + ' <b>' + escHtml(m.v) + '</b></span>';
                }).join('') + '</div>';
            }
            if (opts.traits && opts.traits.length) {
                h += '<div class="cf-info-list">' + opts.traits.map(function (t) {
                    return '<div class="cf-info-trait"><b>' + escHtml(t.nome) + '</b>' +
                        (t.desc ? ' <span>— ' + escHtml(t.desc) + '</span>' : '') + '</div>';
                }).join('') + '</div>';
            }
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
            fillInfo(el('cf-raca-info'), { tagline: r.tagline, resumo: r.resumo, traits: traits.slice(0, 6) });
        }
        function renderEssenciaInfo() {
            var e = essenciaBySlug[essSel.value];
            fillInfo(el('cf-essencia-info'), (essWrap.hidden || !e) ? null : { tagline: 'Essência: ' + e.nome, resumo: e.resumo });
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
                var asi = currentAsiParts();
                if (asi2.value === asi1.value) e.push('O +' + asi.major + ' e o +' + asi.minor + ' do ASI devem ir em atributos diferentes.');
                return e;
            },
            function () { // 1 · Raça
                var e = [];
                if (!racaSel.value) e.push('Escolha uma raça.');
                if (!verWrap.hidden && !verSel.value) e.push('Escolha a vertente elemental.');
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
                if (c && c.maestria_n && checkedVals(maestriaArmas).length !== c.maestria_n)
                    e.push('Escolha ' + c.maestria_n + ' arma(s) para Maestria de Arma.');
                if (c && c.estilo_n && !estiloSel.value) e.push('Escolha um Estilo de Luta.');
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
                h += '<div class="cf-step-err" style="display:block;margin-top:.7rem"><strong>Pendências antes de criar:</strong><ul>' +
                    pend.map(function (x) { return '<li>' + escHtml(x) + '</li>'; }).join('') + '</ul></div>';
            } else {
                h += '<p class="mt-2 text-xs text-[var(--spark)]">Tudo certo — a ficha bate com a prévia ao lado.</p>';
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
            var asi = currentAsiParts();
            return SIG.map(function (p) {
                var sig = p[0];
                var v = (scores[sig] || 8) + (asi2.value === sig ? asi.major : 0) + (asi1.value === sig ? asi.minor : 0);
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
                asi: { mais2: asi2.value, mais1: asi1.value },
                raca: racaSel.value,
                linhagem: linWrap.hidden ? '' : linSel.value,
                essencia: essWrap.hidden ? '' : essSel.value,
                vertente: verWrap.hidden ? '' : verSel.value,
                classe: classeSel.value,
                pericias_classe: checkedVals(skillsWrap),
                equip_classe: equip === 'inicial' ? 'inicial' : 'ouro',
                estilo_luta: estiloWrap.hidden ? '' : estiloSel.value,
                expertise: expertiseWrap.hidden ? [] : checkedVals(expertiseBox),
                escolhas_classe_prof: classeProfChoicesSel(),
                truques: magiasWrap.hidden ? [] : checkedVals(truquesBox),
                magias: magiasWrap.hidden ? [] : checkedVals(magiasBox),
                antecedente: antSel.value,
                pericias_antecedente: checkedVals(bgWrap),
                idiomas_ferramentas: idiomasFerramentasSel(),
                maestrias: maestriaWrap.hidden ? [] : checkedVals(maestriaArmas),
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
            submitBtn.disabled = true; submitBtn.textContent = 'Salvando…';
            fetch(window.CRIAR_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                body: JSON.stringify(payload())
            }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
              .then(function (res) {
                  if (res.ok && res.j.ok) { window.location.href = res.j.redirect; return; }
                  showErros((res.j && res.j.erros) || ['Erro ao salvar a ficha.']);
                  submitBtn.disabled = false; submitBtn.textContent = 'Criar Personagem';
              }).catch(function () {
                  showErros(['Erro de rede ao salvar.']);
                  submitBtn.disabled = false; submitBtn.textContent = 'Criar Personagem';
              });
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
