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

        // ---- Validação + submit
        var erroBox = el('cf-erros'), submitBtn = el('cf-submit');

        function showErros(arr) {
            erroBox.innerHTML = '';
            if (!arr || !arr.length) { erroBox.classList.add('hidden'); return; }
            var ul = document.createElement('ul'); ul.className = 'list-inside list-disc';
            arr.forEach(function (e) { var li = document.createElement('li'); li.textContent = e; ul.appendChild(li); });
            erroBox.appendChild(ul);
            erroBox.classList.remove('hidden');
            erroBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        function clientValidate() {
            var errs = [];
            if (!el('cf-nome').value.trim()) errs.push('Dê um nome ao personagem.');
            var asi = currentAsiParts();
            if (asi2.value === asi1.value) errs.push('O +' + asi.major + ' e o +' + asi.minor + ' do ASI devem ir em atributos diferentes.');
            if (!racaSel.value) errs.push('Escolha uma raça.');
            if (!classeSel.value) errs.push('Escolha uma classe.');
            if (!antSel.value) errs.push('Escolha um antecedente.');
            var c = classeBySlug[classeSel.value];
            if (c && checkedVals(skillsWrap).length !== c.pericias_n)
                errs.push('Escolha exatamente ' + c.pericias_n + ' perícia(s) de classe.');
            if (checkedVals(bgWrap).length !== bgSkillN()) errs.push('Escolha ' + bgSkillN() + ' perícia(s) do antecedente.');
            if (idiomasFerramentasSel().length !== bgLangToolN()) errs.push('Escolha ' + bgLangToolN() + ' idioma(s)/ferramenta(s).');
            var _lbl = { pericia: 'perícia(s)', idioma: 'idioma(s)', ferramenta: 'ferramenta(s)' };
            racialGroups.forEach(function (g) {
                if (checkedVals(g.grid).length !== g.n)
                    errs.push('Escolhas de raça: selecione ' + g.n + ' ' + (_lbl[g.tipo] || g.tipo) + '.');
            });
            if (!verWrap.hidden && !verSel.value) errs.push('Escolha a vertente elemental.');
            if (c && c.maestria_n && checkedVals(maestriaArmas).length !== c.maestria_n)
                errs.push('Escolha ' + c.maestria_n + ' arma(s) para Maestria de Arma.');
            if (c && c.estilo_n && !estiloSel.value) errs.push('Escolha um Estilo de Luta.');
            if (c && c.expertise_n && checkedVals(expertiseBox).length !== c.expertise_n)
                errs.push('Escolha ' + c.expertise_n + ' perícia(s) para Especialização.');
            classeProfGroups.forEach(function (g) {
                if (checkedVals(g.grid).length !== g.n)
                    errs.push('Escolha ' + g.n + ' ' + classeProfLabel(g.tipo) + ' de classe.');
            });
            if (c && c.conjuracao) {
                if (c.conjuracao.truques_n && checkedVals(truquesBox).length !== c.conjuracao.truques_n)
                    errs.push('Escolha ' + c.conjuracao.truques_n + ' truque(s).');
                if (checkedVals(magiasBox).length !== magiaLimit)
                    errs.push('Escolha ' + magiaLimit + ' magia(s) de 1º nível.');
            }
            return errs;
        }

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

        form.addEventListener('submit', function (ev) {
            ev.preventDefault();
            var errs = clientValidate();
            if (errs.length) { showErros(errs); return; }
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
