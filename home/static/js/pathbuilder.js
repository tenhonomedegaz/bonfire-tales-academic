/* Laboratório de builds — cliente.
 *
 * Duas regras que definem este arquivo:
 *   1. NÃO existe markup de ficha aqui. A prévia vem pronta do servidor
 *      (`build.ficha_html`, os partials da aba Ficha) e só é injetada em #pb-folha.
 *   2. Seleção é DIRETA: clicar no cartão adiciona/remove. Nada de "buscar → escolher no
 *      select → clicar em Adicionar". A descrição abre no próprio cartão, sob demanda.
 */
(function () {
    'use strict';

    var STORAGE_BASE = 'bonfire:pathbuilder:base';
    var STORAGE_BASE_FP = 'bonfire:pathbuilder:base_fp';
    var STORAGE_BUILDS = 'bonfire:pathbuilder:builds';
    var STORAGE_SAVED = 'bonfire:pathbuilder:saved';
    var SIGLAS = ['FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR'];
    var STEPS = ['Base', 'Progressão', 'Escolhas', 'Aumentos', 'Equipamento', 'Magias', 'Revisão'];

    function byId(id) { return document.getElementById(id); }
    function clone(value) { return JSON.parse(JSON.stringify(value)); }
    function esc(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function signed(value) {
        value = Number(value || 0);
        return (value >= 0 ? '+' : '') + value;
    }
    /* Filtro insensível a acento: "pocao" acha "Poção". */
    var DIACRITICOS = new RegExp('[\\u0300-\\u036f]', 'g');
    function fold(value) {
        return String(value == null ? '' : value).toLocaleLowerCase('pt-BR')
            .normalize('NFD').replace(DIACRITICOS, '');
    }
    function readJson(id) {
        try { return JSON.parse(byId(id).textContent || '{}'); } catch (err) { return {}; }
    }
    /* A base sobrevive ao fechar a aba (localStorage) mas continua LOCAL: o antigo
       sessionStorage transformava um F5 em "monte tudo de novo". */
    function readStore(key) {
        var raw = null;
        try { raw = sessionStorage.getItem(key); } catch (err) { /* sessão indisponível */ }
        if (raw != null) {
            try {
                var sessionValue = JSON.parse(raw);
                if (sessionValue != null) return sessionValue;
            } catch (err) { /* cópia da sessão corrompida: tentar a local */ }
        }
        try { raw = localStorage.getItem(key); } catch (err) { return null; }
        try { return JSON.parse(raw || 'null'); } catch (err) { return null; }
    }
    function writeStore(key, value) {
        var raw = JSON.stringify(value);
        var session = false;
        var local = false;
        try { sessionStorage.setItem(key, raw); session = true; }
        catch (err) {
            /* Uma cópia antiga na sessão não pode ocultar a nova cópia local no reload. */
            try { sessionStorage.removeItem(key); } catch (removeError) { /* acesso negado */ }
        }
        try { localStorage.setItem(key, raw); local = true; } catch (err) { /* cota */ }
        return { session: session, local: local };
    }
    function readLocal(key) {
        try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (err) { return null; }
    }
    /* Impressão digital da base do criador: muda quando o personagem-base muda. */
    function baseFingerprint(b) {
        b = b || {};
        return JSON.stringify([b.nome, b.classe, b.raca, b.linhagem, b.essencia,
                               b.antecedente, b.scores]);
    }
    function markBase(b) {
        writeStore(STORAGE_BASE_FP, baseFingerprint(b));
    }

    function init() {
        var app = byId('pathbuilder-app');
        if (!app) return;
        var base = readStore(STORAGE_BASE);
        if (!base || !base.classe) {
            byId('pb-empty').hidden = false;
            return;
        }
        byId('pb-workspace').hidden = false;

        var catalogs = readJson('pb-catalogs');
        var classBySlug = Object.create(null);
        var talentBySlug = Object.create(null);
        var mundaneBySlug = Object.create(null);
        var magicBySlug = Object.create(null);
        var spellBySlug = Object.create(null);
        (catalogs.classes || []).forEach(function (row) { classBySlug[row.slug] = row; });
        (catalogs.talentos || []).forEach(function (row) { talentBySlug[row.slug] = row; });
        (catalogs.itens_mundanos || []).forEach(function (row) { mundaneBySlug[row.slug] = row; });
        (catalogs.itens_magicos || []).forEach(function (row) { magicBySlug[row.slug] = row; });
        (catalogs.magias || []).forEach(function (row) { spellBySlug[row.slug] = row; });

        function emptyBuild(ownerBase) {
            return {
                modo: 'sandbox',
                classes: [{ slug: (ownerBase || base).classe, nivel: 1, subclasse: '' }],
                atributos_bonus: {},
                escolhas: {},
                talentos: [],
                talentos_raciais: [],
                itens: [],
                magias: []
            };
        }
        function normalizeTalent(raw) {
            if (raw && typeof raw === 'object') {
                return { slug: String(raw.slug || ''), atributo: String(raw.atributo || '').toUpperCase() };
            }
            return { slug: String(raw || ''), atributo: '' };
        }
        function normalizeBuild(build, ownerBase) {
            ownerBase = ownerBase && typeof ownerBase === 'object' ? ownerBase : base;
            build = build && typeof build === 'object' && !Array.isArray(build)
                ? build : emptyBuild(ownerBase);
            build.classes = Array.isArray(build.classes) && build.classes.length
                ? build.classes : emptyBuild(ownerBase).classes;
            /* Base nova + build antiga guardada = "a classe inicial precisa permanecer na
               build" em todo preview. Se a build não fala da classe da base, ela é de outro
               personagem: começa limpa em vez de travar o laboratório. */
            if (!build.classes.some(function (row) { return row && row.slug === ownerBase.classe; })) {
                return emptyBuild(ownerBase);
            }
            build.modo = build.modo === 'regras' ? 'regras' : 'sandbox';
            build.atributos_bonus = build.atributos_bonus &&
                typeof build.atributos_bonus === 'object' &&
                !Array.isArray(build.atributos_bonus) ? build.atributos_bonus : {};
            build.escolhas = build.escolhas && typeof build.escolhas === 'object' &&
                !Array.isArray(build.escolhas)
                ? build.escolhas : {};
            var seenTalents = Object.create(null);
            build.talentos = (Array.isArray(build.talentos) ? build.talentos : [])
                .map(normalizeTalent).filter(function (row) {
                    if (!row.slug || seenTalents[row.slug]) return false;
                    seenTalents[row.slug] = true;
                    return true;
                });
            var seenRacial = Object.create(null);
            build.talentos_raciais = (Array.isArray(build.talentos_raciais)
                ? build.talentos_raciais : []).filter(function (row) {
                    var level = Number(row && row.nivel || 0);
                    if (!row || !row.nome || !level || seenRacial[level]) return false;
                    row.nivel = level;
                    row.nome = String(row.nome);
                    seenRacial[level] = true;
                    return true;
                });
            build.itens = Array.isArray(build.itens) ? build.itens.filter(function (row) {
                return row && typeof row === 'object' && !Array.isArray(row);
            }) : [];
            var seenSpells = Object.create(null);
            build.magias = (Array.isArray(build.magias) ? build.magias : []).filter(function (row) {
                if (!row || !row.slug) return false;
                row.slug = String(row.slug);
                if (row.classe != null && row.classe !== '') row.classe = String(row.classe);
                else delete row.classe; // payload legado: o servidor pode inferir a fonte única.
                row.preparada = !!row.preparada;
                var key = row.slug + '\u0000' + (row.classe || '');
                if (seenSpells[key]) return false;
                seenSpells[key] = true;
                return true;
            });
            return build;
        }
        /* Base trocada no criador = builds antigas descartadas. Sem esta impressão digital,
           uma build guardada de OUTRO personagem reaparecia por cima da base nova (o
           criador só limpa a cópia de sessão). */
        var builds = readStore(STORAGE_BUILDS);
        if (readStore(STORAGE_BASE_FP) !== baseFingerprint(base)) builds = null;
        markBase(base);
        if (!Array.isArray(builds) || builds.length !== 2) builds = [emptyBuild(), emptyBuild()];
        builds = builds.map(function (build) { return normalizeBuild(build, base); });

        var active = 0;
        var step = 0;
        var itemKind = 'mundano';
        var results = [null, null];
        var resultInputs = [null, null];
        var resultContexts = [null, null];
        var errors = [null, null];
        var timer = null;
        var requestSeq = 0;
        var loadSeq = 0;
        var detailCache = Object.create(null);
        var queries = { classe: '', talento: '', item: '', magia: '' };
        var spellClass = '';
        var storageWarning = '';

        function persist() {
            var saved = writeStore(STORAGE_BUILDS, builds);
            if (!saved.local) {
                storageWarning = saved.session
                    ? 'Edição guardada só nesta sessão. Exporte um arquivo para manter uma cópia.'
                    : 'Não foi possível guardar a edição. Exporte um arquivo antes de sair desta página.';
                savedFeedback(storageWarning, true);
            } else if (storageWarning) {
                if (byId('pb-save-status').textContent === storageWarning) savedFeedback('', false);
                storageWarning = '';
            }
        }
        function current() { return builds[active]; }
        function previewInput(index) { return JSON.stringify({ base: base, build: builds[index] }); }
        function budgetContext(index) { return JSON.stringify([base, builds[index].classes]); }
        function freshResult(index) { return resultInputs[index] === previewInput(index); }
        function clearResult(index) {
            results[index] = null;
            resultInputs[index] = null;
            resultContexts[index] = null;
            errors[index] = null;
        }
        function totalLevel(build) {
            return (build.classes || []).reduce(function (sum, row) {
                return sum + Number(row.nivel || 0);
            }, 0);
        }
        function mutate(callback) {
            callback(current());
            persist();
            renderEditor();
            schedulePreview();
        }

        /* ---------------------------------------------------------------- cartões */
        /* UM componente para tudo que se escolhe: nome + meta + chevron que busca a
           descrição no servidor e a mostra NO LUGAR (padrão dos cards da ficha). */
        function optionCard(kind, slug, nome, meta, selected, extra) {
            return '<div class="pb-opt' + (selected ? ' is-on' : '') + '"' +
                ' data-opt-kind="' + esc(kind) + '" data-opt-slug="' + esc(slug) + '">' +
                '<button type="button" class="pb-opt-pick" data-opt-pick title="' +
                  (selected ? 'Remover da build' : 'Adicionar à build') + '">' +
                  '<span class="pb-opt-mark" aria-hidden="true"></span>' +
                  '<span class="pb-opt-main"><span class="pb-opt-name">' + esc(nome) + '</span>' +
                  (meta ? '<span class="pb-opt-meta">' + esc(meta) + '</span>' : '') + '</span>' +
                '</button>' +
                '<button type="button" class="pb-opt-more" data-opt-more aria-expanded="false"' +
                  ' title="Ver descrição">' +
                  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"' +
                  ' stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>' +
                '</button>' +
                (extra || '') +
                '<div class="pb-opt-desc" data-opt-desc hidden></div>' +
                '</div>';
        }
        function renderMd(raw) {
            var value = String(raw || '').trim();
            if (!value) return '';
            if (typeof window.renderBonfireMarkdown === 'function') {
                return '<div class="bonfire-markdown">' + window.renderBonfireMarkdown(value) + '</div>';
            }
            return '<p>' + esc(value).replace(/\n/g, '<br>') + '</p>';
        }
        function detailHtml(payload) {
            var html = '';
            if ((payload.linhas || []).length) {
                html += '<div class="pb-opt-lines">' + payload.linhas.map(function (row) {
                    return '<span><b>' + esc(row[0]) + ':</b> ' + esc(row[1]) + '</span>';
                }).join('') + '</div>';
            }
            html += renderMd(payload.descricao);
            if (payload.extra) {
                html += '<div class="pb-opt-extra">' + renderMd(payload.extra) + '</div>';
            }
            return html || '<p class="pb-muted">Sem descrição cadastrada.</p>';
        }
        var DETAIL_TIPO = {
            talento: 'talento', magia: 'magia', subclasse: 'subclasse',
            mundano: 'item_mundano', magico: 'item_magico'
        };
        function loadDetail(kind, slug, target) {
            var tipo = DETAIL_TIPO[kind];
            if (!tipo) { target.innerHTML = '<p class="pb-muted">Sem descrição cadastrada.</p>'; return; }
            var key = tipo + ':' + slug;
            if (detailCache[key]) { target.innerHTML = detailCache[key]; return; }
            target.innerHTML = '<p class="pb-muted">Carregando…</p>';
            fetch(window.PATHBUILDER_DETALHE_URL + '?tipo=' + encodeURIComponent(tipo) +
                  '&slug=' + encodeURIComponent(slug))
                .then(function (r) { return r.json(); })
                .then(function (json) {
                    var html = json && json.ok ? detailHtml(json.detalhe)
                        : '<p class="pb-muted">Sem descrição cadastrada.</p>';
                    detailCache[key] = html;
                    target.innerHTML = html;
                })
                .catch(function () {
                    target.innerHTML = '<p class="pb-muted">Não foi possível carregar a descrição.</p>';
                });
        }

        /* --------------------------------------------------------------- pickers */
        function filterCatalog(rows, query, selected) {
            var q = fold(query);
            var out = [];
            for (var i = 0; i < rows.length && out.length < 160; i += 1) {
                var row = rows[i];
                if (selected && selected[row.slug]) continue;
                if (q && fold(row.nome + ' ' + (row.nome_ingles || '') + ' ' +
                        (row.meta || '') + ' ' + (row.grupo || '')).indexOf(q) < 0) continue;
                out.push(row);
            }
            return out;
        }
        function pickerHtml(kind, rows, total) {
            if (!rows.length) {
                return '<p class="pb-muted pb-opt-empty">Nenhum resultado para este filtro.</p>';
            }
            var html = '';
            var group = null;
            rows.forEach(function (row) {
                if (row.grupo && row.grupo !== group) {
                    group = row.grupo;
                    html += '<div class="pb-opt-group">' + esc(group) + '</div>';
                }
                html += optionCard(kind, row.slug, row.nome, row.meta, false);
            });
            if (total > rows.length) {
                html += '<p class="pb-muted pb-opt-empty">' + (total - rows.length) +
                    ' resultado(s) além destes — refine o filtro.</p>';
            }
            return html;
        }
        function renderPicker(kind) {
            var host = document.querySelector('[data-picker="' + kind + '"]');
            if (!host) return;
            var list = host.querySelector('[data-picker-list]');
            var build = current();
            var owned = Object.create(null);
            var source = [];
            if (kind === 'classe') {
                build.classes.forEach(function (row) { owned[row.slug] = true; });
                source = (catalogs.classes || []).map(function (row) {
                    return { slug: row.slug, nome: row.nome, grupo: 'Classes',
                             meta: row.subclasse_nivel ? 'subclasse no nível ' + row.subclasse_nivel : '' };
                });
            } else if (kind === 'talento') {
                build.talentos.forEach(function (row) { owned[row.slug] = true; });
                source = catalogs.talentos || [];
            } else if (kind === 'item') {
                source = itemKind === 'magico' ? (catalogs.itens_magicos || []) : (catalogs.itens_mundanos || []);
            } else {
                if (!spellClass) {
                    list.innerHTML = '<p class="pb-muted pb-opt-empty">Escolha a classe que adiciona a magia.</p>';
                    byId('pb-spell-results').textContent =
                        build.magias.length + ' escolha(s) mantida(s) · escolha uma classe para buscar';
                    return;
                }
                build.magias.forEach(function (row) {
                    if ((row.classe || '') === spellClass) owned[row.slug] = true;
                });
                source = (catalogs.magias || []).map(function (row) {
                    return Object.assign({}, row, { meta: (row.nome_ingles ? row.nome_ingles + ' · ' : '') +
                        (row.meta || '') });
                });
            }
            /* Item pode repetir na build (3 poções), então o catálogo de itens não esconde
               o que já foi escolhido; classe/talento/magia são únicos e saem da lista. */
            var hide = kind === 'item' ? null : owned;
            var rows = filterCatalog(source, queries[kind], hide);
            var totalMatching = 0;
            var q = fold(queries[kind]);
            source.forEach(function (row) {
                if (hide && hide[row.slug]) return;
                if (!q || fold(row.nome + ' ' + (row.nome_ingles || '') + ' ' +
                        (row.meta || '') + ' ' + (row.grupo || '')).indexOf(q) >= 0) {
                    totalMatching += 1;
                }
            });
            if (kind === 'magia') {
                byId('pb-spell-results').textContent = totalMatching +
                    ' magia(s) encontrada(s) · ' + build.magias.length + ' escolha(s) mantida(s)';
            }
            list.innerHTML = pickerHtml(kind === 'item' ? itemKind : kind, rows, totalMatching);
        }

        /* ------------------------------------------------------------- progressão */
        function renderClasses() {
            var build = current();
            var total = totalLevel(build);
            byId('pb-total-level').textContent = 'Nível ' + total + ' / 20';
            byId('pb-classes').innerHTML = build.classes.map(function (row, index) {
                var info = classBySlug[row.slug] || { nome: row.slug, subclasses: [] };
                var min = Number(info.subclasse_nivel || 0);
                var unlocked = min && Number(row.nivel) >= min;
                var subs = '';
                if (unlocked && (info.subclasses || []).length) {
                    subs = '<div class="pb-subclass" data-subclass-for="' + index + '">' +
                        (info.subclasses || []).map(function (sub) {
                            return optionCard('subclasse', sub.slug, sub.nome, sub.meta,
                                sub.slug === row.subclasse,
                                '<input type="hidden" data-subclass-index="' + index + '">');
                        }).join('') + '</div>';
                } else if (min) {
                    subs = '<p class="pb-row-note">Subclasse libera no nível ' + min +
                        ' desta classe.</p>';
                }
                return '<div class="pb-row">' +
                    '<div class="pb-row-head">' +
                      '<span class="pb-row-name">' + esc(info.nome) +
                        (index === 0 ? '<small>classe inicial</small>' : '') + '</span>' +
                      '<span class="pb-stepper-num">' +
                        '<button type="button" data-class-level="' + index + '" data-delta="-1"' +
                          (Number(row.nivel) <= 1 ? ' disabled' : '') + ' aria-label="Reduzir nível">−</button>' +
                        '<output>' + Number(row.nivel || 1) + '</output>' +
                        '<button type="button" data-class-level="' + index + '" data-delta="1"' +
                          (total >= 20 ? ' disabled' : '') + ' aria-label="Aumentar nível">+</button>' +
                      '</span>' +
                      (index === 0 ? ''
                        : '<button type="button" class="pb-x" data-remove-class="' + index +
                          '" title="Remover classe">×</button>') +
                    '</div>' + subs + '</div>';
            }).join('');
        }

        /* -------------------------------------------------------------- aumentos */
        function orcamento() {
            var result = results[active];
            if (resultContexts[active] !== budgetContext(active)) return null;
            return (result && result.orcamento) || null;
        }
        function normalAttributePoints(build) {
            return SIGLAS.reduce(function (sum, sig) {
                return sum + Math.max(0, Number((build.atributos_bonus || {})[sig] || 0));
            }, 0);
        }
        function localAsiBudget(build) {
            var budget = orcamento();
            if (!budget) return null;
            var slots = Number(budget.asi_slots || 0);
            var available = Math.max(0, slots - build.talentos.length) * 2;
            var used = normalAttributePoints(build);
            return { slots: slots, available: available, used: used, remaining: available - used };
        }
        function localFeatBonus(build, sig) {
            return build.talentos.reduce(function (sum, row) {
                return sum + (row.atributo === sig ? 1 : 0);
            }, 0);
        }
        function projectedAttribute(build, sig, normalBonus) {
            var result = results[active];
            if (!result) return null;
            var attr = (result.atributos || []).find(function (row) { return row.sig === sig; });
            if (!attr || attr.valor == null) return null;
            var applied = Number((result.atributos_pathbuilder_aplicados || {})[sig] || 0);
            return Number(attr.valor) - applied + Number(normalBonus || 0) + localFeatBonus(build, sig);
        }
        function renderAttributes() {
            var build = current();
            var values = build.atributos_bonus;
            var budget = orcamento();
            var result = results[active];
            var attrs = result ? (result.atributos || []) : [];
            var localBudget = localAsiBudget(build);
            var restantes = localBudget ? localBudget.remaining : null;
            byId('pb-attributes').innerHTML = SIGLAS.map(function (sig) {
                var bonus = Number(values[sig] || 0);
                var final = attrs.find(function (row) { return row.sig === sig; });
                var projectedNext = projectedAttribute(build, sig, bonus + 1);
                var plusDisabled = !localBudget || restantes <= 0 ||
                    (projectedNext !== null && projectedNext > 20);
                return '<div class="pb-attr' + (bonus ? ' is-on' : '') + '">' +
                    '<span class="pb-attr-sig">' + sig + '</span>' +
                    '<span class="pb-attr-final">' + (final && final.valor != null ? final.valor : '—') +
                      '<small>' + (final ? signed(final.mod) : '') + '</small></span>' +
                    '<span class="pb-stepper-num sm">' +
                      '<button type="button" data-attr="' + sig + '" data-delta="-1"' +
                        (bonus <= 0 ? ' disabled' : '') + ' aria-label="Reduzir ' + sig + '">−</button>' +
                      '<output>+' + bonus + '</output>' +
                      '<button type="button" data-attr="' + sig + '" data-delta="1"' +
                        (plusDisabled ? ' disabled' : '') +
                        ' aria-label="Aumentar ' + sig + '">+</button>' +
                    '</span></div>';
            }).join('');

            if (!budget) {
                byId('pb-asi-counter').textContent = '—';
                byId('pb-talent-counter').textContent = '—';
                byId('pb-asi-hint').textContent = 'Aguarde uma prévia válida desta progressão para adicionar aumentos. Você pode remover escolhas para corrigir a build.';
                return;
            }
            var counter = byId('pb-asi-counter');
            counter.textContent = localBudget.used + '/' + localBudget.available + ' pontos';
            counter.classList.toggle('is-bad', localBudget.remaining !== 0);
            counter.classList.toggle('is-ok', localBudget.available > 0 && localBudget.remaining === 0);
            byId('pb-asi-hint').textContent = budget.asi_slots
                ? 'A build tem ' + localBudget.slots + ' slot(s) de ASI: ' + build.talentos.length +
                  ' gasto(s) em talento e ' + Math.max(0, localBudget.slots - build.talentos.length) +
                  ' em pontos (2 cada).'
                : 'Nenhum slot de ASI neste nível — suba a progressão para liberar aumentos.';
            var talents = byId('pb-talent-counter');
            talents.textContent = build.talentos.length + '/' + localBudget.slots + ' slots';
            talents.classList.toggle('is-bad', build.talentos.length > localBudget.slots);
        }

        function renderTalents() {
            renderPicker('talento');
            var build = current();
            var selectedHost = document.querySelector('[data-picker="talento"] [data-picker-list]');
            if (!selectedHost) return;
            var chosen = build.talentos.map(function (selected) {
                var row = talentBySlug[selected.slug] || {
                    nome: selected.slug, meta: '', atributos: SIGLAS
                };
                var options = (row.atributos || SIGLAS).map(function (sig) {
                    return '<option value="' + esc(sig) + '"' +
                        (selected.atributo === sig ? ' selected' : '') + '>' + esc(sig) + '</option>';
                }).join('');
                var extra = '<label class="pb-opt-control"><span>+1 em atributo</span>' +
                    '<select class="pb-select-inline" data-talent-attr="' + esc(selected.slug) + '">' +
                    '<option value="">Escolha</option>' + options + '</select></label>';
                return optionCard('talento', selected.slug, row.nome, row.meta || 'Talento', true, extra);
            }).join('');
            if (chosen) {
                selectedHost.insertAdjacentHTML('afterbegin',
                    '<div class="pb-opt-group">Na build</div>' + chosen);
            }
        }

        function renderRacialTalents() {
            var host = byId('pb-racial-talents');
            if (!host) return;
            var build = current();
            var result = results[active];
            var groups = result ? (result.talentos_raciais_grupos || []).slice() : [];
            var knownLevels = Object.create(null);
            groups.forEach(function (group) { knownLevels[Number(group.nivel)] = true; });
            build.talentos_raciais.forEach(function (row) {
                if (!knownLevels[Number(row.nivel)]) {
                    groups.push({ nivel: Number(row.nivel), selecionado: row.nome,
                                  opcoes: [], indisponivel: true });
                }
            });
            groups.sort(function (a, b) { return Number(a.nivel) - Number(b.nivel); });
            if (!groups.length) {
                host.innerHTML = '<p class="pb-muted">Nenhum marco racial adicional foi liberado neste nivel.</p>';
                return;
            }
            host.innerHTML = groups.map(function (group) {
                var selected = build.talentos_raciais.find(function (row) {
                    return Number(row.nivel) === Number(group.nivel);
                });
                var value = selected ? selected.nome : '';
                var valid = !!value && !group.indisponivel && (group.opcoes || []).some(function (row) {
                    return row.nome === value;
                });
                var options = (group.opcoes || []).map(function (row) {
                    return '<option value="' + esc(row.nome) + '"' +
                        (row.nome === value ? ' selected' : '') + '>' + esc(row.nome) + '</option>';
                }).join('');
                var unavailable = value && !valid
                    ? '<option value="' + esc(value) + '" selected disabled>' + esc(value) + ' (indisponível)</option>'
                    : '';
                return '<div class="pb-row' + (valid ? '' : ' is-pending') + '">' +
                    '<div class="pb-row-head"><span class="pb-row-name">Talento racial' +
                    '<small>Marco de nivel ' + Number(group.nivel) + '</small></span>' +
                    '<span class="pb-counter' + (valid ? ' is-ok' : ' is-bad') + '">' +
                    (valid ? 'escolhido' : value ? 'indisponível' : 'pendente') + '</span></div>' +
                    '<select class="pb-racial-select" data-racial-level="' + Number(group.nivel) + '">' +
                    '<option value="">Escolha um talento racial</option>' + unavailable + options + '</select>' +
                    (value && !valid ? '<p class="pb-card-hint">Escolha outra opção ou limpe este marco.</p>' : '') +
                    '</div>';
            }).join('');
        }

        /* -------------------------------------------------------------- escolhas */
        function choiceFromTalent(key, slug) {
            // Contrato de _groups_with_keys: kind|tipo|classe_id|slug(origem)|ocorrência.
            var source = talentBySlug[slug];
            var origin = String(source ? source.nome : slug).normalize('NFKD')
                .replace(/[^\x00-\x7F]/g, '').toLowerCase().replace(/[^\w\s-]/g, '')
                .trim().replace(/[-\s]+/g, '-').replace(/^[-_]+|[-_]+$/g, '');
            var parts = key.split('|');
            return parts.length === 5 && parts[2] === '0' && parts[3] === origin;
        }
        function editableChoiceGroups() {
            var result = results[active];
            var submitted = resultInputs[active] ? JSON.parse(resultInputs[active]).build : null;
            var removed = submitted ? submitted.talentos.filter(function (talent) {
                return !current().talentos.some(function (row) { return row.slug === talent.slug; });
            }) : [];
            return ((result && result.escolhas_grupos) || []).filter(function (group) {
                return !removed.some(function (talent) { return choiceFromTalent(group.key, talent.slug); });
            });
        }
        function fixedChoices(group) {
            // Separa concessões da base das escolhas enviadas na prévia anterior.
            // Comparar com a edição atual faria uma escolha removida parecer fixa.
            var submitted = group.selecionadas || [];
            return (group.resolvidas || []).filter(function (row) {
                return submitted.indexOf(row.valor) < 0;
            });
        }
        function renderChoices() {
            var groups = editableChoiceGroups();
            var host = byId('pb-choices');
            if (!groups.length) {
                byId('pb-choice-count').textContent = 'nenhuma';
                host.innerHTML = '<p class="pb-muted">Esta build não declara escolhas por tag ' +
                    'neste nível. Suba a progressão ou escolha uma subclasse.</p>';
                return;
            }
            var pending = groups.reduce(function (sum, g) { return sum + Number(g.pendentes || 0); }, 0);
            var counter = byId('pb-choice-count');
            counter.textContent = pending ? pending + ' pendente' + (pending === 1 ? '' : 's') : 'tudo resolvido';
            counter.classList.toggle('is-bad', pending > 0);
            counter.classList.toggle('is-ok', pending === 0);

            var build = current();
            host.innerHTML = groups.map(function (group) {
                var picked = Array.isArray(build.escolhas[group.key]) ? build.escolhas[group.key] : [];
                var pickedSet = Object.create(null);
                picked.forEach(function (v) { pickedSet[v] = true; });
                var fixed = fixedChoices(group);
                var opts = (group.opcoes || []).map(function (option) {
                    return '<div class="pb-opt' + (pickedSet[option.valor] ? ' is-on' : '') + '"' +
                        ' data-choice-key="' + esc(group.key) + '" data-choice-val="' + esc(option.valor) + '">' +
                        '<button type="button" class="pb-opt-pick" data-choice-pick' +
                          (option.ja_proficiente && !pickedSet[option.valor] ? ' disabled' : '') + '>' +
                          '<span class="pb-opt-mark" aria-hidden="true"></span>' +
                          '<span class="pb-opt-main"><span class="pb-opt-name">' + esc(option.nome) +
                          (option.ja_proficiente ? ' — já proficiente' : '') + '</span>' +
                          (option.meta ? '<span class="pb-opt-meta">' + esc(option.meta) + '</span>' : '') +
                          '</span></button>' +
                        (option.descricao
                          ? '<button type="button" class="pb-opt-more" data-choice-more aria-expanded="false"' +
                            ' title="Ver efeito"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
                            ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="m6 9 6 6 6-6"/></svg></button>' +
                            '<div class="pb-opt-desc" hidden>' + renderMd(option.descricao) + '</div>'
                          : '') +
                        '</div>';
                }).join('');
                var fixedCount = fixed.length;
                var maxSelectable = Math.max(0, Number(group.limite || 0) - fixedCount);
                var restam = Math.max(0, maxSelectable - picked.length);
                /* Grupo grande (Maestria de Arma tem 128 opções) ganha filtro próprio —
                   sem isso a etapa vira um paredão de cartões. */
                var filtro = (group.opcoes || []).length > 12
                    ? '<input type="search" class="pb-search pb-choice-search"' +
                      ' data-choice-filter placeholder="Filtrar ' +
                      esc(String(group.label).toLocaleLowerCase('pt-BR')) + ' (' +
                      (group.opcoes || []).length + ' opções)" aria-label="Filtrar opções">'
                    : '';
                return '<div class="pb-row pb-choice' + (group.pendentes ? ' is-pending' : '') + '">' +
                    '<div class="pb-row-head">' +
                      '<span class="pb-row-name">' + esc(group.label) +
                        '<small>' + esc([group.classe, group.origem].filter(Boolean).join(' · ')) + '</small></span>' +
                      '<span class="pb-counter' + (restam > 0 ? ' is-bad' : ' is-ok') + '">' +
                        (restam > 0 ? 'escolha ' + restam : 'ok') + '</span>' +
                    '</div>' +
                    (fixed.length ? '<p class="pb-row-note">Já na ficha: ' +
                       esc(fixed.map(function (r) { return r.nome; }).join(', ')) + '</p>' : '') +
                    filtro +
                    '<div class="pb-opts-inline' + (filtro ? ' is-long' : '') +
                      '" data-choice-opts>' + opts + '</div></div>';
            }).join('');
        }

        /* ------------------------------------------------------------ equipamento */
        function renderItems() {
            document.querySelectorAll('[data-item-kind]').forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.itemKind === itemKind);
            });
            var build = current();
            var host = byId('pb-items');
            if (!build.itens.length) {
                host.innerHTML = '<p class="pb-muted">Nenhum item na build. Escolha no catálogo abaixo.</p>';
            } else {
                host.innerHTML = build.itens.map(function (row, index) {
                    var info = (row.tipo === 'magico' ? magicBySlug[row.slug] : mundaneBySlug[row.slug])
                        || { nome: row.slug, meta: '' };
                    var attune = row.tipo === 'magico' && info.requer_sintonizacao
                        ? '<label class="pb-check"><input type="checkbox" data-item-attuned="' + index + '"' +
                          (row.sintonizado ? ' checked' : '') + '> sintonizado</label>' : '';
                    return '<div class="pb-line">' +
                        '<span class="pb-line-name">' + esc(info.nome) +
                          '<small>' + esc(info.meta || '') + '</small></span>' +
                        '<span class="pb-line-tools">' +
                          '<span class="pb-stepper-num sm"><button type="button" data-item-qty-delta="' + index +
                            '" data-delta="-1" aria-label="Menos">−</button><output>' + Number(row.qtd || 1) +
                            '</output><button type="button" data-item-qty-delta="' + index +
                            '" data-delta="1" aria-label="Mais">+</button></span>' +
                          '<label class="pb-check"><input type="checkbox" data-item-equipped="' + index + '"' +
                            (row.equipado ? ' checked' : '') + '> equipado</label>' + attune +
                          '<button type="button" class="pb-x" data-remove-item="' + index +
                            '" title="Remover">×</button>' +
                        '</span></div>';
                }).join('');
            }
            var budget = orcamento();
            var counter = byId('pb-attune-counter');
            if (budget) {
                counter.textContent = budget.sintonizacao_usada + '/' + budget.sintonizacao_maxima + ' sintonizados';
                counter.classList.toggle('is-bad', budget.sintonizacao_usada > budget.sintonizacao_maxima);
            } else {
                counter.textContent = '—';
            }
            renderPicker('item');
        }

        /* ---------------------------------------------------------------- magias */
        function spellSourceRows() {
            var result = results[active] || {};
            var summary = result.summary || result;
            return Array.isArray(summary.magias_fontes) ? summary.magias_fontes.filter(function (row) {
                return row && row.slug;
            }) : [];
        }
        function spellClassOptions(includeLegacy) {
            var seen = Object.create(null);
            var rows = [];
            spellSourceRows().forEach(function (row) {
                var slug = String(row.slug);
                if (seen[slug]) return;
                seen[slug] = true;
                rows.push({ slug: slug, nome: row.nome || ((classBySlug[slug] || {}).nome) || slug });
            });
            current().magias.forEach(function (row) {
                var slug = row.classe || '';
                if (seen[slug]) return;
                seen[slug] = true;
                rows.push({ slug: slug, nome: slug
                    ? (((classBySlug[slug] || {}).nome) || slug) + ' (origem indisponível)'
                    : 'Sem classe (legado)' });
            });
            if (includeLegacy && !seen['']) rows.push({ slug: '', nome: 'Sem classe (legado)' });
            return rows;
        }
        function spellKey(slug, classe) { return String(slug) + '\u0000' + String(classe || ''); }
        function upsertSpell(build, slug, classe, preparada) {
            var key = spellKey(slug, classe);
            var at = build.magias.findIndex(function (row) {
                return spellKey(row.slug, row.classe) === key;
            });
            var value = { slug: slug, classe: classe, preparada: !!preparada };
            if (!classe) delete value.classe;
            if (at >= 0) build.magias[at] = value;
            else build.magias.push(value);
        }
        function renderSpellClassPicker() {
            var select = byId('pb-spell-class');
            var options = spellSourceRows();
            if (!options.some(function (row) { return row.slug === spellClass; })) spellClass = '';
            select.innerHTML = '<option value="">Escolha uma classe</option>' + options.map(function (row) {
                return '<option value="' + esc(row.slug) + '"' + (row.slug === spellClass ? ' selected' : '') +
                    '>' + esc(row.nome) + '</option>';
            }).join('');
        }
        function renderSpellRows(host, build) {
            var manual = Object.create(null);
            build.magias.forEach(function (row, index) { manual[spellKey(row.slug, row.classe)] = index; });
            var rows = [];
            var used = Object.create(null);
            spellSourceRows().forEach(function (source) {
                (source.magias || []).forEach(function (spell) {
                    var key = spellKey(spell.slug, source.slug);
                    var override = manual[key];
                    var legacyKey = spellKey(spell.slug, '');
                    if (override == null && manual[legacyKey] != null &&
                            spellSourceRows().filter(function (s) {
                                return (s.magias || []).some(function (m) { return m.slug === spell.slug; });
                            }).length === 1) {
                        override = manual[legacyKey];
                        used[legacyKey] = true;
                    }
                    if (spell.base === false && override == null) return;
                    rows.push({ slug: spell.slug, classe: String(source.slug), nome: spell.nome,
                        nivel: spell.nivel, preparada: override == null
                            ? !!(spell.base ? spell.preparada_base : spell.preparada) : !!build.magias[override].preparada,
                        sempre_preparada: !!spell.sempre_preparada, manualIndex: override == null ? -1 : override });
                    used[key] = true;
                });
            });
            build.magias.forEach(function (row, index) {
                var key = spellKey(row.slug, row.classe);
                if (!used[key]) rows.push({ slug: row.slug, classe: row.classe || '', preparada: !!row.preparada,
                    sempre_preparada: false, manualIndex: index });
            });
            if (!rows.length) {
                host.innerHTML = '<p class="pb-muted">Nenhuma magia disponível para esta build.</p>';
            } else {
                host.innerHTML = rows.map(function (row) {
                    var info = spellBySlug[row.slug] || { nome: row.slug, nivel: 0, meta: '' };
                    var levelValue = row.nivel == null ? info.nivel : row.nivel;
                    var level = Number(levelValue || 0) === 0 ? 'Truque' : levelValue + 'º nível';
                    var classes = spellClassOptions(true);
                    if (!classes.some(function (item) { return item.slug === row.classe; })) {
                        classes.push({ slug: row.classe, nome: row.classe + ' (origem indisponível)' });
                    }
                    return '<div class="pb-line">' +
                        '<span class="pb-line-name">' + esc(row.nome || info.nome) +
                          '<small>' + esc(level + (info.meta ? ' · ' + info.meta : '')) + '</small></span>' +
                        '<span class="pb-line-tools">' +
                          '<label class="pb-check">Classe <select class="pb-select-inline" data-spell-class-row="' +
                            row.manualIndex + '" data-spell-slug="' + esc(row.slug) + '"' +
                            (row.manualIndex < 0 || row.sempre_preparada ? ' disabled' : '') + '>' +
                            classes.map(function (item) { return '<option value="' + esc(item.slug) + '"' +
                                (item.slug === row.classe ? ' selected' : '') + '>' + esc(item.nome) + '</option>'; }).join('') +
                          '</select></label>' +
                          '<label class="pb-check"><input type="checkbox" data-spell-prepared-slug="' + esc(row.slug) +
                            '" data-spell-prepared-row="' + row.manualIndex +
                            '" data-spell-prepared-class="' + esc(row.classe) + '"' + (row.preparada ? ' checked' : '') +
                            (row.sempre_preparada ? ' disabled' : '') + '> preparada</label>' +
                          (row.manualIndex >= 0 ? '<button type="button" class="pb-x" data-remove-spell="' + row.manualIndex +
                            '" title="Remover alteração">×</button>' : '') +
                        '</span></div>';
                }).join('');
            }
            byId('pb-spell-counter').textContent = rows.length ? rows.length + ' no repertório' : 'nenhuma';
        }
        function renderSpells() {
            var build = current();
            var host = byId('pb-spells');
            renderSpellRows(host, build);
            renderSpellClassPicker();
            renderPicker('magia');

        }

        /* ----------------------------------------------------------------- base */
        function renderBase() {
            var info = classBySlug[base.classe];
            var rows = [
                ['Nome', base.nome || '—'],
                ['Classe', info ? info.nome : base.classe],
                ['Raça', [base.raca, base.linhagem, base.essencia, base.vertente]
                    .filter(Boolean).join(' · ') || '—'],
                ['Antecedente', base.antecedente || '—']
            ];
            SIGLAS.forEach(function (sig) {
                rows.push([sig, String((base.scores || {})[sig] == null ? '—' : base.scores[sig])]);
            });
            byId('pb-base-grid').innerHTML = rows.map(function (row) {
                return '<div class="pb-base-cell"><span class="k">' + esc(row[0]) +
                    '</span><span class="v">' + esc(row[1]) + '</span></div>';
            }).join('');
            var modo = current().modo;
            byId('pb-mode-hint').textContent = modo === 'regras'
                ? 'A ficha aponta toda divergência de regra (ASI não gasto, subclasse em falta, sintonização acima do limite).'
                : 'Livre: a ficha deriva mesmo com escolhas em aberto — bom para testar teto de dano e combinações.';
        }

        /* ----------------------------------------------------------------- passos */
        function stepPending(index) {
            var result = results[active];
            if (!result) return 0;
            var budget = result.orcamento || {};
            if (index === 1) {
                return (result.validacao && result.validacao.problemas || []).filter(function (p) {
                    return p.indexOf('subclasse') >= 0;
                }).length;
            }
            if (index === 2) {
                return (result.escolhas_pendentes || []).reduce(function (s, g) {
                    return s + Number(g.pendentes || 0);
                }, 0);
            }
            if (index === 3) {
                var racialGroups = result.talentos_raciais_grupos || [];
                var racial = racialGroups.filter(function (group) {
                    return !current().talentos_raciais.some(function (row) {
                        return Number(row.nivel) === Number(group.nivel) &&
                            (group.opcoes || []).some(function (option) { return option.nome === row.nome; });
                    });
                }).length;
                racial += current().talentos_raciais.filter(function (row) {
                    return !racialGroups.some(function (group) {
                        return Number(group.nivel) === Number(row.nivel);
                    });
                }).length;
                return racial + (Number(budget.pontos_restantes || 0) !== 0 ? 1 : 0);
            }
            if (index === 4) {
                return Number(budget.sintonizacao_usada || 0) > Number(budget.sintonizacao_maxima || 3) ? 1 : 0;
            }
            if (index === 5 || index === 6) {
                var validation = (results[active] && results[active].validacao) || {};
                return (validation[index === 5 ? 'magias' : 'problemas'] || []).length;
            }
            return 0;
        }
        function renderStepper() {
            document.querySelectorAll('[data-step-tab]').forEach(function (tab) {
                var index = Number(tab.dataset.stepTab);
                tab.classList.toggle('is-current', index === step);
                var pending = stepPending(index);
                tab.classList.toggle('is-error', pending > 0);
                tab.classList.toggle('is-complete', pending === 0 && index !== step &&
                    !!results[active] && freshResult(active) && !errors[active]);
                var badge = tab.querySelector('.pb-step-badge');
                if (badge) badge.setAttribute('data-pending', pending > 0 ? String(pending) : '');
            });
            document.querySelectorAll('[data-step]').forEach(function (panel) {
                panel.hidden = Number(panel.dataset.step) !== step;
            });
            document.querySelector('[data-step-prev]').disabled = step === 0;
            document.querySelector('[data-step-next]').disabled = step === STEPS.length - 1;
            byId('pb-stepnav-hint').textContent = 'Etapa ' + (step + 1) + ' de ' + STEPS.length +
                ' · ' + STEPS[step];

            var result = results[active];
            var problems = result && result.validacao && (result.validacao.modo === 'regras' || step === 6)
                ? (result.validacao.problemas || []) : [];
            var errBox = byId('pb-step-err');
            if (problems.length) {
                errBox.hidden = false;
                errBox.innerHTML = '<strong>Pelas regras, ajuste:</strong><ul>' +
                    problems.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul>';
            } else {
                errBox.hidden = true;
                errBox.innerHTML = '';
            }
            var ready = result && freshResult(active) && !errors[active];
            var valid = ready && result.validacao && result.validacao.valida === true;
            byId('pb-conclude').disabled = !valid;
            byId('pb-review-status').textContent = !ready
                ? 'Aguarde uma prévia atualizada para revisar a simulação.'
                : !valid ? 'Resolva as pendências antes de concluir. Suas escolhas foram preservadas.'
                : 'Simulação pronta para concluir. Nenhum personagem será criado.';
        }

        function actionFeedback(message) {
            var host = byId('pb-action-feedback');
            host.textContent = message || '';
            host.hidden = !message;
        }

        function choiceFeedback(message) {
            var host = byId('pb-choice-feedback');
            host.textContent = message || '';
            host.hidden = !message;
        }

        function renderVariant() {
            document.querySelectorAll('[data-build-tab]').forEach(function (button) {
                var selected = Number(button.dataset.buildTab) === active;
                button.classList.toggle('is-active', selected);
                button.setAttribute('aria-selected', selected ? 'true' : 'false');
            });
            byId('pb-clone').textContent = active === 0 ? 'Duplicar em B' : 'Duplicar em A';
        }

        function renderEditor() {
            renderVariant();
            byId('pb-retry-preview').hidden = !errors[active];
            renderBase();
            document.querySelectorAll('[data-build-mode]').forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.buildMode === current().modo);
            });
            renderClasses();
            renderPicker('classe');
            renderChoices();
            renderAttributes();
            renderTalents();
            renderRacialTalents();
            renderItems();
            renderSpells();
            renderStepper();
        }

        /* ------------------------------------------------------------ ficha/diff */
        function bindFolha(root) {
            /* Cards de característica da ficha: o markup vem do servidor com o JSON das
               descrições dentro do fragmento — reaproveita o mesmo contrato da aba Ficha. */
            var map = {};
            var script = root.querySelector('#ficha-feat-desc');
            if (script) { try { map = JSON.parse(script.textContent || '{}'); } catch (e) { map = {}; } }
            root.querySelectorAll('[data-feat-group]').forEach(function (group) {
                var n = group.querySelectorAll('[data-feat-card]').length;
                if (!n) { group.style.display = 'none'; return; }
                var badge = group.querySelector('[data-feat-count]');
                if (badge) badge.textContent = n;
            });
            root.querySelectorAll('.feat-card').forEach(function (card) {
                var head = card.querySelector('.feat-head');
                var inner = card.querySelector('.feat-body-inner');
                if (!head || !inner) return;
                var rendered = false;
                head.addEventListener('click', function () {
                    var willOpen = !card.classList.contains('open');
                    if (willOpen && !rendered) {
                        inner.innerHTML = renderMd(map[card.getAttribute('data-feat-key')]) ||
                            '<p class="feat-desc empty">Sem descrição detalhada.</p>';
                        rendered = true;
                    }
                    card.classList.toggle('open', willOpen);
                    head.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
                });
            });
            var pp = root.querySelector('[data-passive-perception]');
            if (pp) {
                var percRaw = (pp.getAttribute('data-perc-bonus') || '').trim();
                var sabMod = parseInt(pp.getAttribute('data-sab-mod') || '0', 10) || 0;
                var out = pp.querySelector('[data-pp-value]') || pp;
                out.textContent = percRaw !== '' ? (parseInt(percRaw, 10) + 10) : (10 + sabMod);
            }
        }
        function renderDiff() {
            var box = byId('pb-diff');
            var mine = results[active];
            var other = results[active === 0 ? 1 : 0];
            if (!mine || !other || !freshResult(0) || !freshResult(1) || errors[0] || errors[1]) {
                box.hidden = true; box.innerHTML = ''; return;
            }
            var pairs = [
                ['Nível', mine.nivel, other.nivel],
                ['PV', mine.pv, other.pv],
                ['CA', mine.ca, other.ca],
                ['Ataque', (mine.metricas_combate || {}).melhor_bonus_ataque,
                    (other.metricas_combate || {}).melhor_bonus_ataque],
                ['Dano méd.', (mine.metricas_combate || {}).maior_dano_medio,
                    (other.metricas_combate || {}).maior_dano_medio]
            ].filter(function (row) { return String(row[1]) !== String(row[2]); });
            if (!pairs.length) { box.hidden = true; box.innerHTML = ''; return; }
            box.hidden = false;
            box.innerHTML = '<span class="pb-diff-lbl">vs Build ' + (active === 0 ? 'B' : 'A') + '</span>' +
                pairs.map(function (row) {
                    var a = row[1] == null ? '—' : row[1];
                    var b = row[2] == null ? '—' : row[2];
                    return '<span class="pb-diff-cell"><small>' + esc(row[0]) + '</small><b>' +
                        esc(a) + '</b><i>' + esc(b) + '</i></span>';
                }).join('');
        }
        function renderSheet() {
            var host = byId('pb-folha');
            var result = results[active];
            var notice = errors[active]
                ? '<div class="pb-sheet-error" role="alert"><strong>Prévia não atualizada</strong><p>' +
                  esc(errors[active]) + (result ? ' Exibindo a última prévia válida.' : '') + '</p></div>'
                : '';
            host.innerHTML = notice + (result ? (result.ficha_html || '') : '');
            bindFolha(host);
            renderDiff();
        }

        function fetchBuild(index, seq) {
            var input = previewInput(index);
            var context = budgetContext(index);
            return fetch(window.PATHBUILDER_PREVIEW_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                body: input
            }).then(function (response) {
                return response.json().then(function (json) {
                    return { ok: response.ok, json: json };
                });
            }).then(function (response) {
                if (seq !== requestSeq || input !== previewInput(index)) return;
                var candidate = response.json && response.json.build;
                if (response.ok && response.json.ok && candidate && candidate.orcamento &&
                        Array.isArray(candidate.atributos)) {
                    results[index] = response.json.build;
                    resultInputs[index] = input;
                    resultContexts[index] = context;
                    errors[index] = null;
                } else {
                    errors[index] = ((response.json || {}).erros || ['Build inválida.']).join(' ');
                }
            }).catch(function () {
                if (seq !== requestSeq || input !== previewInput(index)) return;
                errors[index] = 'Não foi possível derivar esta build.';
            });
        }
        /* Só a build ATIVA é derivada a cada edição. O antigo laboratório materializava as
           duas fichas a cada tecla — dobro de custo para uma comparação que ninguém pediu. */
        function runPreview(alsoOther) {
            clearTimeout(timer);
            var seq = ++requestSeq;
            var status = byId('pb-status');
            status.textContent = 'Derivando…';
            status.classList.remove('is-error');
            byId('pb-retry-preview').hidden = true;
            var jobs = [fetchBuild(active, seq)];
            if (alsoOther) jobs.push(fetchBuild(active === 0 ? 1 : 0, seq));
            Promise.all(jobs).then(function () {
                if (seq !== requestSeq) return;
                renderSheet();
                renderEditor();
                if (errors[active]) {
                    status.textContent = results[active]
                        ? 'Prévia não atualizada · exibindo a última válida.'
                        : 'Prévia indisponível · ajuste a build e tente novamente.';
                    status.classList.add('is-error');
                } else {
                    var result = results[active];
                    status.textContent = 'Nível ' + (result ? result.nivel : '?') +
                        ' · nenhum personagem salvo';
                }
                byId('pb-retry-preview').hidden = !errors[active];
            });
        }
        function schedulePreview() {
            // Invalida a resposta em voo já na edição, antes de esperar o debounce.
            requestSeq++;
            clearTimeout(timer);
            byId('pb-status').textContent = 'Alterações pendentes · aguardando prévia.';
            byId('pb-retry-preview').hidden = true;
            renderDiff();
            timer = setTimeout(function () { runPreview(false); }, 260);
        }

        /* ---------------------------------------------------------------- eventos */
        function toggleDesc(card, descEl, moreBtn, kind, slug) {
            var willOpen = descEl.hidden;
            descEl.hidden = !willOpen;
            card.classList.toggle('is-open', willOpen);
            moreBtn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            if (willOpen && kind && !descEl.dataset.loaded) {
                descEl.dataset.loaded = '1';
                loadDetail(kind, slug, descEl);
            }
        }

        app.addEventListener('click', function (event) {
            var target = event.target;

            var stepTab = target.closest('[data-step-tab]');
            if (stepTab) { step = Number(stepTab.dataset.stepTab); renderStepper(); return; }

            var more = target.closest('[data-opt-more]');
            if (more) {
                var card = more.closest('.pb-opt');
                toggleDesc(card, card.querySelector('[data-opt-desc]'), more,
                    card.dataset.optKind, card.dataset.optSlug);
                return;
            }
            var choiceMore = target.closest('[data-choice-more]');
            if (choiceMore) {
                var cCard = choiceMore.closest('.pb-opt');
                toggleDesc(cCard, cCard.querySelector('.pb-opt-desc'), choiceMore, '', '');
                return;
            }

            var choicePick = target.closest('[data-choice-pick]');
            if (choicePick) {
                if (choicePick.disabled) return;
                var box = choicePick.closest('[data-choice-key]');
                var key = box.dataset.choiceKey;
                var val = box.dataset.choiceVal;
                var group = editableChoiceGroups().find(function (row) {
                    return row.key === key;
                });
                var selected = Array.isArray(current().escolhas[key]) ? current().escolhas[key] : [];
                if (!group) {
                    choiceFeedback('Aguarde uma prévia atualizada antes de escolher.');
                    return;
                }
                if (selected.indexOf(val) < 0 && resultContexts[active] !== budgetContext(active)) {
                    choiceFeedback('Aguarde uma prévia atualizada desta progressão antes de escolher.');
                    return;
                }
                var limit = Math.max(0, Number(group.limite || 0) - fixedChoices(group).length);
                if (selected.indexOf(val) < 0 && selected.length >= limit) {
                    choiceFeedback('Todas as escolhas de ' + group.label +
                        ' estão preenchidas. Remova uma opção antes de escolher outra.');
                    return;
                }
                choiceFeedback('');
                mutate(function (build) {
                    var values = Array.isArray(build.escolhas[key]) ? build.escolhas[key].slice() : [];
                    var at = values.indexOf(val);
                    if (at >= 0) {
                        values.splice(at, 1);
                    } else {
                        var fixed = fixedChoices(group).length;
                        var limit = Math.max(0, Number(group.limite || 0) - fixed);
                        if (values.length >= limit) return;
                        values.push(val);
                    }
                    build.escolhas[key] = values;
                });
                return;
            }

            var pick = target.closest('[data-opt-pick]');
            if (pick) {
                var optCard = pick.closest('.pb-opt');
                var kind = optCard.dataset.optKind;
                var slug = optCard.dataset.optSlug;
                if (kind === 'classe') {
                    mutate(function (build) {
                        if (totalLevel(build) >= 20) return;
                        if (!build.classes.some(function (r) { return r.slug === slug; })) {
                            build.classes.push({ slug: slug, nivel: 1, subclasse: '' });
                        }
                    });
                } else if (kind === 'subclasse') {
                    var holder = optCard.querySelector('[data-subclass-index]');
                    var idx = Number(holder ? holder.dataset.subclassIndex : optCard
                        .closest('[data-subclass-for]').dataset.subclassFor);
                    mutate(function (build) {
                        var row = build.classes[idx];
                        if (!row) return;
                        row.subclasse = row.subclasse === slug ? '' : slug;
                    });
                } else if (kind === 'talento') {
                    var chosen = current().talentos.some(function (row) { return row.slug === slug; });
                    var availableBudget = localAsiBudget(current());
                    if (!chosen && (!availableBudget || current().talentos.length >= availableBudget.slots ||
                            availableBudget.used > Math.max(0, availableBudget.slots - current().talentos.length - 1) * 2)) {
                        actionFeedback(!availableBudget ? 'Aguarde uma prévia válida para escolher um talento.'
                            : 'Sem slot de ASI livre para este talento. Remova outro talento ou devolva os pontos de atributo desse slot.');
                        return;
                    }
                    actionFeedback('');
                    mutate(function (build) {
                        var at = build.talentos.findIndex(function (row) { return row.slug === slug; });
                        if (at >= 0) {
                            build.talentos.splice(at, 1);
                            Object.keys(build.escolhas).forEach(function (key) {
                                if (choiceFromTalent(key, slug)) delete build.escolhas[key];
                            });
                        } else {
                            var localBudget = localAsiBudget(build);
                            if (!localBudget || (build.talentos.length >= localBudget.slots ||
                                    localBudget.used > Math.max(0, localBudget.slots -
                                        build.talentos.length - 1) * 2)) return;
                            build.talentos.push({ slug: slug, atributo: '' });
                        }
                    });
                } else if (kind === 'mundano' || kind === 'magico') {
                    mutate(function (build) {
                        build.itens.push({ tipo: kind, slug: slug, qtd: 1,
                                           equipado: false, sintonizado: false });
                    });
                } else if (kind === 'magia') {
                    if (!spellClass) return;
                    mutate(function (build) {
                        upsertSpell(build, slug, spellClass, true);
                    });
                }
                return;
            }

            var button = target.closest('button');
            if (!button) return;
            if (button.id === 'pb-conclude') {
                var review = results[active];
                if (!freshResult(active) || errors[active] || !review || !review.validacao || !review.validacao.valida) return;
                byId('pb-review-status').textContent = 'Simulação concluída e validada. Nenhum personagem foi criado.';
                return;
            }

            if (button.dataset.buildTab != null) {
                clearTimeout(timer);
                requestSeq++;
                active = Number(button.dataset.buildTab);
                renderEditor();
                renderSheet();
                if (!freshResult(active) || errors[active]) { runPreview(false); }
                else { byId('pb-status').textContent = 'Nível ' + results[active].nivel + ' · nenhum personagem salvo'; }
                return;
            }
            if (button.dataset.itemKind) {
                itemKind = button.dataset.itemKind;
                renderItems();
                return;
            }
            if (button.dataset.buildMode) {
                mutate(function (build) { build.modo = button.dataset.buildMode; });
                return;
            }
            if (button.dataset.classLevel != null) {
                var classIndex = Number(button.dataset.classLevel);
                var delta = Number(button.dataset.delta);
                mutate(function (build) {
                    var row = build.classes[classIndex];
                    if (!row) return;
                    var next = Number(row.nivel || 1) + delta;
                    if (next < 1 || next > 20 || (delta > 0 && totalLevel(build) >= 20)) return;
                    row.nivel = next;
                    var info = classBySlug[row.slug];
                    if (info && info.subclasse_nivel && next < Number(info.subclasse_nivel)) {
                        row.subclasse = '';
                    }
                    var newTotal = totalLevel(build);
                    build.talentos_raciais = build.talentos_raciais.filter(function (racial) {
                        return Number(racial.nivel || 0) <= newTotal;
                    });
                });
                return;
            }
            if (button.dataset.removeClass != null) {
                mutate(function (build) {
                    build.classes.splice(Number(button.dataset.removeClass), 1);
                    var newTotal = totalLevel(build);
                    build.talentos_raciais = build.talentos_raciais.filter(function (racial) {
                        return Number(racial.nivel || 0) <= newTotal;
                    });
                });
                return;
            }
            if (button.dataset.attr) {
                mutate(function (build) {
                    var sig = button.dataset.attr;
                    var currentBonus = Number(build.atributos_bonus[sig] || 0);
                    var delta = Number(button.dataset.delta);
                    var next = currentBonus + delta;
                    var budget = localAsiBudget(build);
                    if (delta > 0 && (!budget || budget.remaining <= 0)) return;
                    var projected = projectedAttribute(build, sig, next);
                    if (delta > 0 && projected !== null && projected > 20) return;
                    build.atributos_bonus[sig] = Math.max(0, Math.min(10, next));
                });
                return;
            }
            if (button.dataset.itemQtyDelta != null) {
                mutate(function (build) {
                    var row = build.itens[Number(button.dataset.itemQtyDelta)];
                    if (!row) return;
                    row.qtd = Math.max(1, Math.min(999, Number(row.qtd || 1) + Number(button.dataset.delta)));
                });
                return;
            }
            if (button.dataset.removeItem != null) {
                mutate(function (build) { build.itens.splice(Number(button.dataset.removeItem), 1); });
                return;
            }
            if (button.dataset.removeSpell != null) {
                mutate(function (build) { build.magias.splice(Number(button.dataset.removeSpell), 1); });
                return;
            }
            if (button.hasAttribute('data-step-prev')) { step = Math.max(0, step - 1); renderStepper(); return; }
            if (button.hasAttribute('data-step-next')) {
                step = Math.min(STEPS.length - 1, step + 1); renderStepper(); return;
            }
        });

        app.addEventListener('keydown', function (event) {
            var spellPicker = event.target.closest('[data-picker="magia"]');
            if (spellPicker && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
                var cards = Array.prototype.slice.call(spellPicker.querySelectorAll('[data-picker-list] .pb-opt-pick'));
                var at = cards.indexOf(event.target);
                if (cards.length && (at >= 0 || event.target.matches('[data-picker-search]'))) {
                    event.preventDefault();
                    cards[at < 0 ? (event.key === 'ArrowDown' ? 0 : cards.length - 1) :
                        (at + (event.key === 'ArrowDown' ? 1 : -1) + cards.length) % cards.length].focus();
                    return;
                }
            }
            if (event.key !== 'Enter' && event.key !== ' ') return;
            var stepTab = event.target.closest('[data-step-tab]');
            if (!stepTab) return;
            event.preventDefault();
            step = Number(stepTab.dataset.stepTab);
            renderStepper();
        });

        app.addEventListener('input', function (event) {
            /* Filtro de um grupo de escolha: esconde/mostra os cartões já renderizados.
               Nada de re-render — o cursor do campo não pode ser perdido a cada tecla. */
            var choiceFilter = event.target.closest('[data-choice-filter]');
            if (choiceFilter) {
                var q = fold(choiceFilter.value);
                var box = choiceFilter.closest('.pb-choice').querySelector('[data-choice-opts]');
                Array.prototype.forEach.call(box.children, function (card) {
                    var name = card.querySelector('.pb-opt-name');
                    var meta = card.querySelector('.pb-opt-meta');
                    var text = fold((name ? name.textContent : '') + ' ' +
                                    (meta ? meta.textContent : ''));
                    card.hidden = !!q && text.indexOf(q) < 0 &&
                        !card.classList.contains('is-on');
                });
                return;
            }
            var search = event.target.closest('[data-picker-search]');
            if (!search) return;
            var kind = search.closest('[data-picker]').dataset.picker;
            queries[kind] = search.value;
            /* renderTalents() já chama renderPicker('talento') e prende os escolhidos no
               topo — chamar os dois renderizaria a lista duas vezes por tecla. */
            if (kind === 'talento') { renderTalents(); } else { renderPicker(kind); }
        });

        app.addEventListener('change', function (event) {
            var target = event.target;
            if (target.dataset.itemEquipped != null) {
                mutate(function (build) {
                    build.itens[Number(target.dataset.itemEquipped)].equipado = target.checked;
                });
            } else if (target.dataset.itemAttuned != null) {
                mutate(function (build) {
                    build.itens[Number(target.dataset.itemAttuned)].sintonizado = target.checked;
                });
            } else if (target.dataset.spellPreparedSlug != null) {
                mutate(function (build) {
                    var index = Number(target.dataset.spellPreparedRow);
                    if (index >= 0 && build.magias[index]) build.magias.splice(index, 1);
                    upsertSpell(build, target.dataset.spellPreparedSlug,
                        target.dataset.spellPreparedClass, target.checked);
                });
            } else if (target.dataset.spellClassRow != null) {
                mutate(function (build) {
                    var at = Number(target.dataset.spellClassRow);
                    var row = build.magias[at];
                    if (!row) return;
                    var slug = row.slug;
                    var prepared = row.preparada;
                    build.magias.splice(at, 1);
                    upsertSpell(build, slug, target.value, prepared);
                });
            } else if (target.id === 'pb-spell-class') {
                spellClass = target.value;
                renderSpells();
            } else if (target.dataset.talentAttr != null) {
                mutate(function (build) {
                    var row = build.talentos.find(function (talent) {
                        return talent.slug === target.dataset.talentAttr;
                    });
                    if (row) row.atributo = target.value;
                });
            } else if (target.dataset.racialLevel != null) {
                mutate(function (build) {
                    var level = Number(target.dataset.racialLevel);
                    var at = build.talentos_raciais.findIndex(function (row) {
                        return Number(row.nivel) === level;
                    });
                    if (!target.value) {
                        if (at >= 0) build.talentos_raciais.splice(at, 1);
                    } else if (at >= 0) {
                        build.talentos_raciais[at].nome = target.value;
                    } else {
                        build.talentos_raciais.push({ nivel: level, nome: target.value });
                    }
                });
            }
        });

        byId('pb-sheet-collapse').addEventListener('click', function () {
            var collapsed = byId('pb-sheet').classList.toggle('is-collapsed');
            this.textContent = collapsed ? 'mostrar' : 'ocultar';
            this.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        });
        byId('pb-retry-preview').addEventListener('click', function () {
            runPreview(false);
        });
        byId('pb-clone').addEventListener('click', function () {
            builds[active === 0 ? 1 : 0] = clone(current());
            clearResult(active === 0 ? 1 : 0);
            persist();
            renderEditor();
            runPreview(true);
        });
        byId('pb-reset').addEventListener('click', function () {
            builds = [emptyBuild(), emptyBuild()];
            clearResult(0);
            clearResult(1);
            persist();
            renderEditor();
            renderSheet();
            runPreview(false);
        });

        /* --------------------------------------------------------- versões salvas */
        function savedVersions() {
            var saved = readLocal(STORAGE_SAVED);
            return Array.isArray(saved) ? saved : [];
        }
        function savedFeedback(message, isError) {
            var feedback = byId('pb-save-status');
            feedback.textContent = message;
            feedback.classList.toggle('is-error', !!isError);
        }
        function writeSavedVersions(rows) {
            try {
                localStorage.setItem(STORAGE_SAVED, JSON.stringify(rows));
                return true;
            } catch (error) {
                savedFeedback('Não foi possível guardar versões neste navegador. Exporte um arquivo para preservar a build.', true);
                return false;
            }
        }
        function renderSavedVersions(selectedId) {
            var rows = savedVersions();
            byId('pb-saved-builds').innerHTML = '<option value="">Versões salvas</option>' +
                rows.map(function (row) {
                    return '<option value="' + esc(row.id) + '"' +
                        (row.id === selectedId ? ' selected' : '') + '>' + esc(row.nome) + '</option>';
                }).join('');
            byId('pb-delete-save').disabled = !selectedId;
        }
        function validInteger(value, minimum, maximum) {
            if (typeof value === 'string' && /^[0-9]+$/.test(value.trim())) {
                value = Number(value.trim());
            }
            return typeof value === 'number' && Number.isInteger(value) &&
                value >= minimum && value <= maximum;
        }
        function loadBundle(bundle) {
            var attempt = ++loadSeq;
            if (!bundle || !bundle.base || typeof bundle.base !== 'object' ||
                    Array.isArray(bundle.base) || typeof bundle.base.classe !== 'string' ||
                    !bundle.base.classe ||
                    (bundle.formato !== undefined && bundle.formato !== 'bonfire-pathbuilder') ||
                    (bundle.versao !== undefined && bundle.versao !== 1) ||
                    !Array.isArray(bundle.builds) ||
                    bundle.builds.length !== 2 || bundle.builds.some(function (build) {
                        return !build || typeof build !== 'object' || Array.isArray(build) ||
                            !Array.isArray(build.classes) || !build.classes.length ||
                            !build.classes.some(function (row) {
                                return row && row.slug === bundle.base.classe;
                            }) ||
                            build.classes.some(function (row) {
                                return !row || typeof row !== 'object' || Array.isArray(row) ||
                                    typeof row.slug !== 'string' || !row.slug ||
                                    (row.nivel !== undefined && !validInteger(row.nivel, 1, 20));
                            }) ||
                            (build.atributos_bonus && SIGLAS.some(function (sigla) {
                                return Object.prototype.hasOwnProperty.call(build.atributos_bonus, sigla) &&
                                    !validInteger(build.atributos_bonus[sigla], 0, 10);
                            })) ||
                            (build.atributos_bonus !== undefined &&
                                (!build.atributos_bonus || typeof build.atributos_bonus !== 'object' ||
                                    Array.isArray(build.atributos_bonus))) ||
                            (build.escolhas !== undefined &&
                                (!build.escolhas || typeof build.escolhas !== 'object' ||
                                    Array.isArray(build.escolhas) ||
                                    Object.keys(build.escolhas).some(function (key) {
                                        return !Array.isArray(build.escolhas[key]);
                                    }))) ||
                            (build.talentos !== undefined &&
                                (!Array.isArray(build.talentos) || build.talentos.some(function (row) {
                                    return !(typeof row === 'string' && row) &&
                                        !(row && typeof row === 'object' && !Array.isArray(row) &&
                                            typeof row.slug === 'string' && row.slug &&
                                            (row.atributo == null || typeof row.atributo === 'string'));
                                }) || build.talentos.some(function (row, index, rows) {
                                    var slug = typeof row === 'string' ? row : row.slug;
                                    return rows.findIndex(function (other) {
                                        return (typeof other === 'string' ? other : other.slug) === slug;
                                    }) !== index;
                                }))) ||
                            (build.talentos_raciais !== undefined && !Array.isArray(build.talentos_raciais)) ||
                            (Array.isArray(build.talentos_raciais) && build.talentos_raciais.some(function (row) {
                                return !row || typeof row !== 'object' || Array.isArray(row) ||
                                    typeof row.nome !== 'string' || !row.nome ||
                                    !validInteger(row.nivel, 1, 20);
                            })) ||
                            (Array.isArray(build.talentos_raciais) &&
                                build.talentos_raciais.some(function (row, index, rows) {
                                    return rows.findIndex(function (other) {
                                        return Number(other.nivel) === Number(row.nivel);
                                    }) !== index;
                                })) ||
                            (build.itens !== undefined && !Array.isArray(build.itens)) ||
                            (Array.isArray(build.itens) && build.itens.some(function (row) {
                                return !row || typeof row !== 'object' || Array.isArray(row) ||
                                    typeof row.slug !== 'string' || !row.slug ||
                                    (row.qtd !== undefined && !validInteger(row.qtd, 1, 999));
                            })) ||
                            (build.magias !== undefined &&
                                (!Array.isArray(build.magias) || build.magias.some(function (row) {
                                    return !row || typeof row !== 'object' || Array.isArray(row) ||
                                        typeof row.slug !== 'string' || !row.slug ||
                                        (row.classe != null && typeof row.classe !== 'string') ||
                                        (row.preparada !== undefined && typeof row.preparada !== 'boolean');
                                }) || build.magias.some(function (row, index, rows) {
                                    return rows.findIndex(function (other) {
                                        return other.slug === row.slug &&
                                            (other.classe || '') === (row.classe || '');
                                    }) !== index;
                                })));
                    })) {
                throw new Error('Arquivo de Pathbuilder inválido.');
            }
            // Prepara tudo antes de trocar o editor: um arquivo ruim conserva a edição atual.
            var importedBase = clone(bundle.base);
            var importedBuilds = clone(bundle.builds).map(function (build) {
                return normalizeBuild(build, importedBase);
            });
            var editingBefore = JSON.stringify({ base: base, builds: builds });
            var status = byId('pb-status');
            status.textContent = 'Validando as duas builds…';
            status.classList.remove('is-error');
            return Promise.all(importedBuilds.map(function (build, index) {
                return fetch(window.PATHBUILDER_PREVIEW_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                    body: JSON.stringify({ base: importedBase, build: build })
                }).then(function (response) {
                    return response.json().then(function (json) {
                        if (!response.ok || !json.ok || !json.build) {
                            throw new Error('Build ' + (index === 0 ? 'A' : 'B') + ': ' +
                                ((json.erros || ['prévia inválida.']).join(' ')));
                        }
                        return json.build;
                    });
                });
            })).then(function (previews) {
                if (attempt !== loadSeq) return;
                if (editingBefore !== JSON.stringify({ base: base, builds: builds })) {
                    throw new Error('A edição mudou durante a validação. Abra a versão novamente.');
                }
                ++requestSeq;
                clearTimeout(timer);
                var entries = [
                    [STORAGE_BASE, JSON.stringify(importedBase)],
                    [STORAGE_BUILDS, JSON.stringify(importedBuilds)],
                    [STORAGE_BASE_FP, JSON.stringify(baseFingerprint(importedBase))]
                ];
                function saveImport(storage) {
                    var previous = entries.map(function (entry) {
                        return storage.getItem(entry[0]);
                    });
                    try {
                        entries.forEach(function (entry) { storage.setItem(entry[0], entry[1]); });
                        return true;
                    } catch (error) {
                        entries.forEach(function (entry, index) {
                            try {
                                if (previous[index] === null) storage.removeItem(entry[0]);
                                else storage.setItem(entry[0], previous[index]);
                            } catch (rollbackError) { /* preserva a edição em memória */ }
                        });
                        return false;
                    }
                }
                if (!saveImport(sessionStorage)) {
                    throw new Error('Não foi possível guardar a versão nesta sessão. Libere espaço e tente novamente.');
                }
                var savedLocally = saveImport(localStorage);
                base = importedBase;
                builds = importedBuilds;
                results = previews;
                resultInputs = [previewInput(0), previewInput(1)];
                resultContexts = [budgetContext(0), budgetContext(1)];
                errors = [null, null];
                renderEditor();
                renderSheet();
                status.textContent = 'Nível ' + previews[active].nivel +
                    (savedLocally ? ' · nenhum personagem salvo' :
                        ' · edição guardada só nesta sessão. Exporte um arquivo para manter uma cópia.');
                byId('pb-retry-preview').hidden = true;
            }).catch(function (error) {
                if (attempt !== loadSeq) return;
                status.textContent = error.message || 'Não foi possível validar esta versão.';
                status.classList.add('is-error');
            });
        }
        byId('pb-save').addEventListener('click', function () {
            var name = window.prompt('Nome desta versão:', 'Build ' +
                new Date().toLocaleString('pt-BR'));
            if (!name || !name.trim()) return;
            var rows = savedVersions();
            var id = String(Date.now());
            while (rows.some(function (row) { return row.id === id; })) {
                id = String(Number(id) + 1);
            }
            rows.unshift({
                id: id,
                nome: name.trim().slice(0, 80),
                salvo_em: new Date().toISOString(),
                base: clone(base),
                builds: clone(builds)
            });
            if (writeSavedVersions(rows.slice(0, 30))) {
                renderSavedVersions(id);
                savedFeedback('Versão salva neste navegador. Exporte um arquivo para ter uma cópia fora dele.', false);
            }
        });
        byId('pb-saved-builds').addEventListener('change', function () {
            var id = this.value;
            byId('pb-delete-save').disabled = !id;
            if (!id) return;
            var bundle = savedVersions().find(function (row) { return row.id === id; });
            if (!bundle) return;
            try {
                loadBundle(bundle);
            } catch (error) {
                var status = byId('pb-status');
                status.textContent = error.message;
                status.classList.add('is-error');
            }
        });
        byId('pb-delete-save').addEventListener('click', function () {
            var id = byId('pb-saved-builds').value;
            if (!id) return;
            if (writeSavedVersions(savedVersions().filter(function (row) { return row.id !== id; }))) {
                renderSavedVersions('');
                savedFeedback('Versão local excluída.', false);
            }
        });
        byId('pb-export').addEventListener('click', function () {
            var payload = JSON.stringify({
                formato: 'bonfire-pathbuilder',
                versao: 1,
                exportado_em: new Date().toISOString(),
                base: base,
                builds: builds
            }, null, 2);
            var url = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
            var anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = 'bonfire-pathbuilder-' +
                new Date().toISOString().slice(0, 10) + '.json';
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
        });
        byId('pb-import').addEventListener('change', function () {
            var file = this.files && this.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function () {
                try {
                    loadBundle(JSON.parse(reader.result));
                } catch (error) {
                    var status = byId('pb-status');
                    status.textContent = error.message;
                    status.classList.add('is-error');
                }
            };
            reader.readAsText(file);
            this.value = '';
        });

        renderSavedVersions('');
        renderEditor();
        runPreview(false);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
