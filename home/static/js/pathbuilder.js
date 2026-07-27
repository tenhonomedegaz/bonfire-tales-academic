(function () {
    'use strict';

    var STORAGE_BASE = 'bonfire:pathbuilder:base';
    var STORAGE_BUILDS = 'bonfire:pathbuilder:builds';
    var STORAGE_SAVED = 'bonfire:pathbuilder:saved';
    var SIGLAS = ['FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR'];

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
    function readJson(id) {
        try { return JSON.parse(byId(id).textContent || '{}'); } catch (err) { return {}; }
    }
    function readStorage(key) {
        try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch (err) { return null; }
    }
    function readLocal(key) {
        try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (err) { return null; }
    }

    function init() {
        var app = byId('pathbuilder-app');
        if (!app) return;
        var base = readStorage(STORAGE_BASE);
        if (!base) {
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

        function emptyBuild() {
            return {
                modo: 'sandbox',
                classes: [{ slug: base.classe, nivel: 1, subclasse: '' }],
                atributos_bonus: {},
                escolhas: {},
                talentos: [],
                itens: [],
                magias: []
            };
        }
        var builds = readStorage(STORAGE_BUILDS);
        if (!Array.isArray(builds) || builds.length !== 2) {
            builds = [emptyBuild(), emptyBuild()];
        }
        function normalizeBuild(build) {
            build = build && typeof build === 'object' ? build : emptyBuild();
            build.classes = Array.isArray(build.classes) && build.classes.length
                ? build.classes : emptyBuild().classes;
            build.modo = build.modo === 'regras' ? 'regras' : 'sandbox';
            build.atributos_bonus = build.atributos_bonus || {};
            build.escolhas = build.escolhas && typeof build.escolhas === 'object'
                ? build.escolhas : {};
            build.talentos = Array.isArray(build.talentos) ? build.talentos : [];
            build.itens = Array.isArray(build.itens) ? build.itens : [];
            build.magias = Array.isArray(build.magias) ? build.magias : [];
            return build;
        }
        builds = builds.map(normalizeBuild);

        var active = 0;
        var itemKind = 'mundano';
        var detailTab = 'diff';
        var results = [null, null];
        var errors = [null, null];
        var timer = null;
        var requestSeq = 0;

        function persist() {
            sessionStorage.setItem(STORAGE_BUILDS, JSON.stringify(builds));
        }
        function current() { return builds[active]; }
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

        function optionHtml(value, label, selected) {
            return '<option value="' + esc(value) + '"' + (selected ? ' selected' : '') +
                '>' + esc(label) + '</option>';
        }
        function renderClasses() {
            var build = current();
            var total = totalLevel(build);
            byId('pb-total-level').textContent = 'Nível ' + total;
            byId('pb-classes').innerHTML = build.classes.map(function (row, index) {
                var info = classBySlug[row.slug] || { nome: row.slug, subclasses: [] };
                var min = Number(info.subclasse_nivel || 0);
                var unlocked = min && Number(row.nivel) >= min;
                var options = '<option value="">' +
                    (min ? (unlocked ? 'Sem subclasse' : 'Desbloqueia no nível ' + min) : 'Sem subclasse') +
                    '</option>';
                if (unlocked) {
                    options += (info.subclasses || []).map(function (sub) {
                        return optionHtml(sub.slug, sub.nome, sub.slug === row.subclasse);
                    }).join('');
                }
                var remove = index === 0
                    ? '<button type="button" class="pb-icon-button" disabled title="Classe inicial">-</button>'
                    : '<button type="button" class="pb-icon-button" data-remove-class="' + index +
                      '" title="Remover classe">x</button>';
                return '<div class="pb-class-row">' +
                    '<span class="pb-class-name">' + esc(info.nome) + '</span>' +
                    '<span class="pb-class-level">' +
                      '<button type="button" data-class-level="' + index + '" data-delta="-1" title="Reduzir nível">-</button>' +
                      '<output>' + Number(row.nivel || 1) + '</output>' +
                      '<button type="button" data-class-level="' + index + '" data-delta="1" title="Aumentar nível">+</button>' +
                    '</span>' +
                    '<select data-subclass="' + index + '"' + (unlocked ? '' : ' disabled') + '>' +
                      options + '</select>' + remove + '</div>';
            }).join('');
            var owned = {};
            build.classes.forEach(function (row) { owned[row.slug] = true; });
            var available = (catalogs.classes || []).filter(function (row) { return !owned[row.slug]; });
            byId('pb-class-select').innerHTML = available.length
                ? available.map(function (row) { return optionHtml(row.slug, row.nome, false); }).join('')
                : '<option value="">Todas as classes adicionadas</option>';
            byId('pb-add-class').disabled = !available.length || total >= 20;
        }

        function renderAttributes() {
            var values = current().atributos_bonus;
            byId('pb-attributes').innerHTML = SIGLAS.map(function (sig) {
                return '<div class="pb-attribute"><strong>' + sig + ' <output>+' +
                    Number(values[sig] || 0) + '</output></strong>' +
                    '<button type="button" data-attr="' + sig + '" data-delta="-1" title="Reduzir bônus">-</button>' +
                    '<button type="button" data-attr="' + sig + '" data-delta="1" title="Aumentar bônus">+</button></div>';
            }).join('');
        }

        function renderMode() {
            document.querySelectorAll('[data-build-mode]').forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.buildMode === current().modo);
            });
        }

        function renderChoices() {
            var result = results[active];
            var groups = result ? (result.escolhas_grupos || []) : [];
            var visible = groups.filter(function (group) {
                return group.pendentes || (group.selecionadas || []).length;
            });
            byId('pb-choices-section').hidden = !visible.length;
            if (!visible.length) {
                byId('pb-choices').innerHTML = '';
                return;
            }
            var pending = visible.reduce(function (sum, group) {
                return sum + Number(group.pendentes || 0);
            }, 0);
            byId('pb-choice-count').textContent = pending + ' pendente' + (pending === 1 ? '' : 's');
            byId('pb-choices').innerHTML = visible.map(function (group) {
                var selected = Array.isArray(current().escolhas[group.key])
                    ? current().escolhas[group.key] : [];
                var slotCount = selected.length + Number(group.pendentes || 0);
                var controls = [];
                for (var slot = 0; slot < slotCount; slot += 1) {
                    var chosen = selected[slot] || '';
                    var options = '<option value="">Escolher</option>' +
                        (group.opcoes || []).map(function (option) {
                            return optionHtml(option.valor,
                                option.nome + (option.meta ? ' · ' + option.meta : ''),
                                option.valor === chosen);
                        }).join('');
                    controls.push('<select data-choice-key="' + esc(group.key) +
                        '" data-choice-slot="' + slot + '">' + options + '</select>');
                }
                return '<div class="pb-choice-group"><div class="pb-choice-title"><strong>' +
                    esc(group.label) + '</strong><small>' +
                    esc([group.classe, group.origem].filter(Boolean).join(' · ')) +
                    '</small></div><div class="pb-choice-controls">' + controls.join('') +
                    '</div></div>';
            }).join('');
        }

        function renderTalents() {
            byId('pb-talents').innerHTML = current().talentos.map(function (slug, index) {
                var row = talentBySlug[slug] || { nome: slug, tipo: '' };
                return '<div class="pb-selected-row"><span class="pb-selected-name">' +
                    esc(row.nome) + '<small class="pb-selected-meta">' + esc(row.tipo || 'Talento') +
                    '</small></span><button type="button" class="pb-icon-button" data-remove-talent="' +
                    index + '" title="Remover talento">x</button></div>';
            }).join('');
            filterTalentSelect();
        }

        function renderItems() {
            document.querySelectorAll('[data-item-kind]').forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.itemKind === itemKind);
            });
            byId('pb-items').innerHTML = current().itens.map(function (row, index) {
                var info = row.tipo === 'magico' ? magicBySlug[row.slug] : mundaneBySlug[row.slug];
                info = info || { nome: row.slug };
                var meta = row.tipo === 'magico'
                    ? ((info.raridade || 'Item mágico') + (info.slot ? ' · ' + info.slot : ''))
                    : (info.categoria || 'Item mundano');
                var attune = row.tipo === 'magico' && info.requer_sintonizacao
                    ? '<label class="pb-check"><input type="checkbox" data-item-attuned="' + index + '"' +
                      (row.sintonizado ? ' checked' : '') + '> Sintonizado</label>' : '';
                return '<div class="pb-selected-row"><span class="pb-selected-name">' + esc(info.nome) +
                    '<small class="pb-selected-meta">' + esc(meta) + '</small></span>' +
                    '<input type="number" min="1" max="999" value="' + Number(row.qtd || 1) +
                    '" data-item-qty="' + index + '" aria-label="Quantidade">' +
                    '<label class="pb-check"><input type="checkbox" data-item-equipped="' + index + '"' +
                    (row.equipado ? ' checked' : '') + '> Equipado</label>' + attune +
                    '<button type="button" class="pb-icon-button" data-remove-item="' + index +
                    '" title="Remover item">x</button></div>';
            }).join('');
            filterItemSelect();
        }

        function renderSpells() {
            byId('pb-spells').innerHTML = current().magias.map(function (row, index) {
                var info = spellBySlug[row.slug] || { nome: row.slug, nivel: 0 };
                var level = Number(info.nivel || 0) === 0 ? 'Truque' : info.nivel + 'º nível';
                return '<div class="pb-selected-row"><span class="pb-selected-name">' + esc(info.nome) +
                    '<small class="pb-selected-meta">' + esc(level + (info.escola ? ' · ' + info.escola : '')) +
                    '</small></span><label class="pb-check"><input type="checkbox" data-spell-prepared="' +
                    index + '"' + (row.preparada ? ' checked' : '') + '> Preparada</label>' +
                    '<button type="button" class="pb-icon-button" data-remove-spell="' + index +
                    '" title="Remover magia">x</button></div>';
            }).join('');
            filterSpellSelect();
        }

        function filterRows(rows, query, label) {
            query = String(query || '').trim().toLocaleLowerCase('pt-BR');
            return rows.filter(function (row) {
                return !query || label(row).toLocaleLowerCase('pt-BR').indexOf(query) >= 0;
            }).slice(0, 250);
        }
        function filterTalentSelect() {
            var owned = {};
            current().talentos.forEach(function (slug) { owned[slug] = true; });
            var rows = filterRows(catalogs.talentos || [], byId('pb-talent-search').value,
                function (row) { return row.nome + ' ' + row.tipo; })
                .filter(function (row) { return !owned[row.slug]; });
            byId('pb-talent-select').innerHTML = rows.length
                ? rows.map(function (row) {
                    return optionHtml(row.slug, row.nome + (row.tipo ? ' · ' + row.tipo : ''), false);
                }).join('') : '<option value="">Nenhum resultado</option>';
        }
        function filterItemSelect() {
            var source = itemKind === 'magico'
                ? (catalogs.itens_magicos || []) : (catalogs.itens_mundanos || []);
            var rows = filterRows(source, byId('pb-item-search').value, function (row) {
                return row.nome + ' ' + (row.categoria || row.raridade || '') + ' ' + (row.slot || '');
            });
            byId('pb-item-select').innerHTML = rows.length
                ? rows.map(function (row) {
                    var meta = row.categoria || row.raridade || '';
                    return optionHtml(row.slug, row.nome + (meta ? ' · ' + meta : ''), false);
                }).join('') : '<option value="">Nenhum resultado</option>';
        }
        function filterSpellSelect() {
            var rows = filterRows(catalogs.magias || [], byId('pb-spell-search').value,
                function (row) { return row.nome + ' ' + row.escola + ' nivel ' + row.nivel; });
            byId('pb-spell-select').innerHTML = rows.length
                ? rows.map(function (row) {
                    var level = Number(row.nivel || 0) === 0 ? 'Truque' : row.nivel + 'º';
                    return optionHtml(row.slug, row.nome + ' · ' + level, false);
                }).join('') : '<option value="">Nenhum resultado</option>';
        }

        function renderEditor() {
            document.querySelectorAll('[data-build-tab]').forEach(function (button) {
                var selected = Number(button.dataset.buildTab) === active;
                button.classList.toggle('is-active', selected);
                button.setAttribute('aria-selected', selected ? 'true' : 'false');
            });
            byId('pb-active-label').textContent = active === 0 ? 'Build A' : 'Build B';
            byId('pb-clone').textContent = active === 0 ? 'Copiar para Build B' : 'Copiar para Build A';
            byId('pb-detail-title').textContent = 'Detalhes da ' + (active === 0 ? 'Build A' : 'Build B');
            renderMode();
            renderClasses();
            renderAttributes();
            renderChoices();
            renderTalents();
            renderItems();
            renderSpells();
            renderDetail();
        }

        function chips(rows) {
            if (!rows || !rows.length) return '<span class="pb-muted">Nenhum</span>';
            return '<div class="pb-chips">' + rows.map(function (value) {
                return '<span class="pb-chip">' + esc(value) + '</span>';
            }).join('') + '</div>';
        }
        function vital(label, value, different) {
            return '<div class="pb-vital' + (different ? ' is-different' : '') +
                '"><small>' + esc(label) + '</small><strong>' + esc(value) + '</strong></div>';
        }
        function differs(index, key) {
            var other = results[index === 0 ? 1 : 0];
            return !!(results[index] && other && String(results[index][key]) !== String(other[key]));
        }
        function validationHtml(result) {
            if (!result || !result.validacao || result.validacao.modo !== 'regras') return '';
            var validation = result.validacao;
            if (validation.valida) {
                return '<div class="pb-validation is-valid"><strong>Build válida</strong></div>';
            }
            return '<div class="pb-validation"><strong>Ajustes pelas regras</strong><ul>' +
                (validation.problemas || []).map(function (problem) {
                    return '<li>' + esc(problem) + '</li>';
                }).join('') + '</ul></div>';
        }
        function renderResult(index) {
            var target = byId('pb-result-' + index);
            var result = results[index];
            if (errors[index]) {
                target.innerHTML = '<div class="pb-result-header"><span>Build ' +
                    (index === 0 ? 'A' : 'B') + '</span><h2>Build inválida</h2></div>' +
                    '<div class="pb-result-body pb-muted">' + esc(errors[index]) + '</div>';
                return;
            }
            if (!result) {
                target.innerHTML = '<div class="pb-result-body pb-muted">Calculando...</div>';
                return;
            }
            var classes = (result.classes || []).map(function (row) {
                return row.classe + ' ' + row.nivel + (row.subclasse ? ' · ' + row.subclasse : '');
            });
            var skills = (result.pericias || []).slice(0, 12).map(function (row) {
                return row.nome + ' ' + signed(row.bonus) + (row.expertise ? ' · expertise' : '');
            });
            var attrs = (result.atributos || []).map(function (row) {
                var other = results[index === 0 ? 1 : 0];
                var otherAttr = other && (other.atributos || []).find(function (x) { return x.sig === row.sig; });
                var changed = otherAttr && Number(otherAttr.valor) !== Number(row.valor);
                return '<div class="pb-attr' + (changed ? ' is-different' : '') + '"><span>' +
                    esc(row.sig) + '</span><strong>' + esc(row.valor) + '</strong><small>' +
                    signed(row.mod) + '</small></div>';
            }).join('');
            var pending = result.escolhas_pendentes || [];
            target.innerHTML =
                '<div class="pb-result-header"><span>Build ' + (index === 0 ? 'A' : 'B') +
                '</span><h2>' + esc(result.nome) + '</h2></div>' +
                '<div class="pb-vitals">' +
                  vital('Nível', result.nivel, differs(index, 'nivel')) +
                  vital('PV', result.pv, differs(index, 'pv')) +
                  vital('CA', result.ca, differs(index, 'ca')) +
                  vital('Prof.', signed(result.pb), differs(index, 'pb')) +
                '</div><div class="pb-result-body">' +
                  '<div class="pb-class-summary">' + chips(classes) + '</div>' +
                  '<div class="pb-attrs">' + attrs + '</div>' +
                  '<div class="pb-result-section"><h3>Perícias</h3>' + chips(skills) + '</div>' +
                  '<div class="pb-result-section"><h3>Defesas e sentidos</h3>' +
                    chips([].concat(result.resistencias || [], result.imunidades || [], result.sentidos || [])) +
                  '</div>' +
                  validationHtml(result) +
                  (pending.length ? '<div class="pb-pending"><strong>Escolhas pendentes:</strong> ' +
                    esc(pending.map(function (row) {
                        return row.label + ' (' + row.pendentes + ')';
                    }).join(', ')) + '</div>' : '') +
                '</div>';
        }

        function table(headers, rows) {
            if (!rows.length) return '<p class="pb-muted">Nenhum registro nesta build.</p>';
            return '<div class="overflow-x-auto"><table class="pb-table"><thead><tr>' +
                headers.map(function (head) { return '<th>' + esc(head) + '</th>'; }).join('') +
                '</tr></thead><tbody>' + rows.join('') + '</tbody></table></div>';
        }
        function keyedRows(rows, keyFn) {
            var out = Object.create(null);
            (rows || []).forEach(function (row) { out[keyFn(row)] = row; });
            return out;
        }
        function renderDiff() {
            var left = results[active];
            var right = results[active === 0 ? 1 : 0];
            if (!left || !right) return '<p class="pb-muted">As duas builds precisam estar calculadas.</p>';
            var rows = [];
            [
                ['PV', left.pv, right.pv],
                ['CA', left.ca, right.ca],
                ['Iniciativa', left.iniciativa, right.iniciativa],
                ['Deslocamento', left.velocidade, right.velocidade],
                ['Bônus de proficiência', signed(left.pb), signed(right.pb)]
            ].forEach(function (row) {
                if (String(row[1]) !== String(row[2])) {
                    rows.push('<tr><td><strong>' + esc(row[0]) + '</strong></td><td>' +
                        esc(row[1]) + '</td><td>' + esc(row[2]) + '</td></tr>');
                }
            });
            var leftFeatures = keyedRows(left.features, function (row) {
                return [row.nome, row.origem, row.nivel].join('|');
            });
            var rightFeatures = keyedRows(right.features, function (row) {
                return [row.nome, row.origem, row.nivel].join('|');
            });
            Object.keys(leftFeatures).forEach(function (key) {
                if (!rightFeatures[key]) {
                    rows.push('<tr><td><strong>Habilidade</strong></td><td>' +
                        esc(leftFeatures[key].nome) + '</td><td class="pb-muted">—</td></tr>');
                }
            });
            Object.keys(rightFeatures).forEach(function (key) {
                if (!leftFeatures[key]) {
                    rows.push('<tr><td><strong>Habilidade</strong></td><td class="pb-muted">—</td><td>' +
                        esc(rightFeatures[key].nome) + '</td></tr>');
                }
            });
            return table(['Diferença', active === 0 ? 'Build A' : 'Build B',
                active === 0 ? 'Build B' : 'Build A'], rows);
        }
        function renderProgression(result) {
            var grouped = {};
            (result.features || []).forEach(function (row) {
                var level = Number(row.nivel || 0);
                var key = level > 0 ? level : 0;
                grouped[key] = grouped[key] || [];
                grouped[key].push(row);
            });
            var levels = Object.keys(grouped).map(Number).sort(function (a, b) { return a - b; });
            if (!levels.length) return '<p class="pb-muted">Nenhuma progressão disponível.</p>';
            return '<div class="pb-timeline">' + levels.map(function (level) {
                return '<div class="pb-timeline-row"><strong>' +
                    (level ? 'Nível ' + level : 'Base') + '</strong><div>' +
                    grouped[level].map(function (row) {
                        return '<span class="pb-timeline-feature">' + esc(row.nome) +
                            '<small>' + esc(row.origem || row.fonte) + '</small></span>';
                    }).join('') + '</div></div>';
            }).join('') + '</div>';
        }
        function spellcastingHtml(result) {
            var casting = result.conjuracao || {};
            if (!(casting.spellcasters || []).length) return '';
            var casters = (casting.spellcasters || []).map(function (caster) {
                return '<div class="pb-caster"><strong>' + esc(caster.classe) +
                    '</strong><span>' + esc(caster.ability) + '</span><span>CD ' +
                    esc(caster.cd) + '</span><span>Ataque ' + signed(caster.ataque) +
                    '</span></div>';
            }).join('');
            var slots = (casting.slots || []).map(function (slot) {
                return '<span class="pb-slot"><small>' + slot.nivel + 'º</small><strong>' +
                    esc(slot.total) + '</strong></span>';
            }).join('');
            return '<div class="pb-casting-summary">' + casters +
                (slots ? '<div class="pb-slots">' + slots + '</div>' : '') + '</div>';
        }
        function renderDetail() {
            document.querySelectorAll('[data-detail-tab]').forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.detailTab === detailTab);
            });
            var result = results[active];
            var body = byId('pb-detail-body');
            if (!result) {
                body.innerHTML = '<p class="pb-muted">Aguardando a build ativa.</p>';
                return;
            }
            if (detailTab === 'diff') {
                body.innerHTML = renderDiff();
            } else if (detailTab === 'progression') {
                body.innerHTML = renderProgression(result);
            } else if (detailTab === 'features') {
                body.innerHTML = table(['Habilidade', 'Origem', 'Nível'],
                    (result.features || []).map(function (row) {
                        return '<tr><td><strong>' + esc(row.nome) + '</strong></td><td>' +
                            esc(row.origem || row.fonte) + '</td><td>' + esc(row.nivel || '—') + '</td></tr>';
                    }));
            } else if (detailTab === 'inventory') {
                body.innerHTML = table(['Item', 'Qtd.', 'Uso', 'Tipo'],
                    (result.inventario || []).map(function (row) {
                        var use = row.equipado ? 'Equipado' : 'Guardado';
                        if (row.sintonizado) use += ' · Sintonizado';
                        return '<tr><td><strong>' + esc(row.nome) + '</strong></td><td>' +
                            esc(row.qtd) + '</td><td>' + esc(use) + '</td><td>' +
                            esc(row.raridade || row.consumivel_tipo || row.tipo_equip || 'Mundano') + '</td></tr>';
                    }));
            } else if (detailTab === 'spells') {
                body.innerHTML = spellcastingHtml(result) + table(['Magia', 'Nível', 'Preparada', 'Origem'],
                    (result.magias || []).map(function (row) {
                        return '<tr><td><strong>' + esc(row.nome) + '</strong></td><td>' +
                            esc(row.nivel === 0 ? 'Truque' : row.nivel) + '</td><td>' +
                            (row.preparada ? 'Sim' : 'Não') + '</td><td>' +
                            esc(row.origem || 'Pathbuilder') + '</td></tr>';
                    }));
            } else {
                var attacks = (result.ataques || []).map(function (row) {
                    return '<tr><td><strong>' + esc(row.nome || row.escopo || 'Ataque') +
                        '</strong></td><td>' + esc(signed(row.bonus_ataque)) + '</td><td>' +
                        esc(row.dano || row.dado || '—') + '</td><td>' +
                        esc(row.maestria || row.tipo_dano || '—') + '</td></tr>';
                });
                var resources = Object.keys(result.recursos || {}).map(function (key) {
                    return '<tr><td><strong>' + esc(key) + '</strong></td><td colspan="3">' +
                        esc(result.recursos[key]) + '</td></tr>';
                });
                var metrics = result.metricas_combate || {};
                body.innerHTML = '<div class="pb-combat-metrics">' +
                    vital('Melhor ataque', metrics.melhor_bonus_ataque == null
                        ? '—' : signed(metrics.melhor_bonus_ataque), false) +
                    vital('Maior dano médio', metrics.maior_dano_medio == null
                        ? '—' : metrics.maior_dano_medio, false) +
                    vital('Perfis de ataque', metrics.quantidade_ataques || 0, false) +
                    vital('Iniciativa', signed(result.iniciativa), false) +
                    '</div>' +
                    table(['Ataque/Recurso', 'Bônus', 'Dano/Valor', 'Maestria'],
                        attacks.concat(resources));
            }
        }

        function renderResults() {
            renderResult(0);
            renderResult(1);
            renderChoices();
            renderDetail();
        }

        function fetchBuild(index, seq) {
            return fetch(window.PATHBUILDER_PREVIEW_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                body: JSON.stringify({ base: base, build: builds[index] })
            }).then(function (response) {
                return response.json().then(function (json) {
                    return { ok: response.ok, json: json };
                });
            }).then(function (response) {
                if (seq !== requestSeq) return;
                if (response.ok && response.json.ok) {
                    results[index] = response.json.build;
                    errors[index] = null;
                } else {
                    results[index] = null;
                    errors[index] = ((response.json || {}).erros || ['Build inválida.']).join(' ');
                }
            }).catch(function () {
                if (seq !== requestSeq) return;
                results[index] = null;
                errors[index] = 'Não foi possível calcular esta build.';
            });
        }
        function runPreview() {
            var seq = ++requestSeq;
            var status = byId('pb-status');
            status.textContent = 'Calculando as duas builds...';
            status.classList.remove('is-error');
            Promise.all([fetchBuild(0, seq), fetchBuild(1, seq)]).then(function () {
                if (seq !== requestSeq) return;
                renderResults();
                if (errors[0] || errors[1]) {
                    status.textContent = 'Uma das builds precisa de ajuste.';
                    status.classList.add('is-error');
                } else {
                    status.textContent = 'Builds calculadas pelo motor real da ficha. Nenhum personagem foi salvo.';
                }
            });
        }
        function schedulePreview() {
            clearTimeout(timer);
            timer = setTimeout(runPreview, 240);
        }

        document.addEventListener('click', function (event) {
            var button = event.target.closest('button');
            if (!button || !app.contains(button)) return;
            if (button.dataset.buildTab != null) {
                active = Number(button.dataset.buildTab);
                renderEditor();
                return;
            }
            if (button.dataset.detailTab) {
                detailTab = button.dataset.detailTab;
                renderDetail();
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
                });
                return;
            }
            if (button.dataset.removeClass != null) {
                mutate(function (build) { build.classes.splice(Number(button.dataset.removeClass), 1); });
                return;
            }
            if (button.dataset.attr) {
                mutate(function (build) {
                    var sig = button.dataset.attr;
                    var next = Number(build.atributos_bonus[sig] || 0) + Number(button.dataset.delta);
                    build.atributos_bonus[sig] = Math.max(0, Math.min(10, next));
                });
                return;
            }
            if (button.dataset.removeTalent != null) {
                mutate(function (build) { build.talentos.splice(Number(button.dataset.removeTalent), 1); });
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
        });

        document.addEventListener('change', function (event) {
            var target = event.target;
            if (!app.contains(target)) return;
            if (target.dataset.subclass != null) {
                mutate(function (build) {
                    build.classes[Number(target.dataset.subclass)].subclasse = target.value;
                });
            } else if (target.dataset.itemQty != null) {
                mutate(function (build) {
                    build.itens[Number(target.dataset.itemQty)].qtd =
                        Math.max(1, Math.min(999, Number(target.value || 1)));
                });
            } else if (target.dataset.itemEquipped != null) {
                mutate(function (build) {
                    build.itens[Number(target.dataset.itemEquipped)].equipado = target.checked;
                });
            } else if (target.dataset.itemAttuned != null) {
                mutate(function (build) {
                    build.itens[Number(target.dataset.itemAttuned)].sintonizado = target.checked;
                });
            } else if (target.dataset.spellPrepared != null) {
                mutate(function (build) {
                    build.magias[Number(target.dataset.spellPrepared)].preparada = target.checked;
                });
            } else if (target.dataset.choiceKey != null) {
                mutate(function (build) {
                    var key = target.dataset.choiceKey;
                    var slot = Number(target.dataset.choiceSlot || 0);
                    var values = Array.isArray(build.escolhas[key])
                        ? build.escolhas[key].slice() : [];
                    values[slot] = target.value;
                    build.escolhas[key] = values.filter(Boolean);
                });
            }
        });

        byId('pb-add-class').addEventListener('click', function () {
            var slug = byId('pb-class-select').value;
            if (!slug) return;
            mutate(function (build) {
                if (!build.classes.some(function (row) { return row.slug === slug; })) {
                    build.classes.push({ slug: slug, nivel: 1, subclasse: '' });
                }
            });
        });
        byId('pb-add-talent').addEventListener('click', function () {
            var slug = byId('pb-talent-select').value;
            if (!slug) return;
            mutate(function (build) {
                if (build.talentos.indexOf(slug) < 0) build.talentos.push(slug);
            });
        });
        byId('pb-add-item').addEventListener('click', function () {
            var slug = byId('pb-item-select').value;
            if (!slug) return;
            mutate(function (build) {
                build.itens.push({
                    tipo: itemKind,
                    slug: slug,
                    qtd: 1,
                    equipado: false,
                    sintonizado: false
                });
            });
        });
        byId('pb-add-spell').addEventListener('click', function () {
            var slug = byId('pb-spell-select').value;
            if (!slug) return;
            mutate(function (build) {
                if (!build.magias.some(function (row) { return row.slug === slug; })) {
                    build.magias.push({ slug: slug, preparada: true });
                }
            });
        });
        byId('pb-talent-search').addEventListener('input', filterTalentSelect);
        byId('pb-item-search').addEventListener('input', filterItemSelect);
        byId('pb-spell-search').addEventListener('input', filterSpellSelect);
        byId('pb-clone').addEventListener('click', function () {
            builds[active === 0 ? 1 : 0] = clone(current());
            persist();
            renderEditor();
            schedulePreview();
        });
        byId('pb-reset').addEventListener('click', function () {
            builds = [emptyBuild(), emptyBuild()];
            persist();
            renderEditor();
            schedulePreview();
        });

        function savedVersions() {
            var saved = readLocal(STORAGE_SAVED);
            return Array.isArray(saved) ? saved : [];
        }
        function renderSavedVersions(selectedId) {
            var rows = savedVersions();
            byId('pb-saved-builds').innerHTML = '<option value="">Builds salvas</option>' +
                rows.map(function (row) {
                    return optionHtml(row.id, row.nome, row.id === selectedId);
                }).join('');
            byId('pb-delete-save').disabled = !selectedId;
        }
        function loadBundle(bundle) {
            if (!bundle || !bundle.base || !Array.isArray(bundle.builds) ||
                    bundle.builds.length !== 2) {
                throw new Error('Arquivo de Pathbuilder inválido.');
            }
            base = clone(bundle.base);
            builds = clone(bundle.builds).map(normalizeBuild);
            sessionStorage.setItem(STORAGE_BASE, JSON.stringify(base));
            persist();
            renderEditor();
            runPreview();
        }
        byId('pb-save').addEventListener('click', function () {
            var name = window.prompt('Nome desta versão:', 'Build ' +
                new Date().toLocaleString('pt-BR'));
            if (!name || !name.trim()) return;
            var rows = savedVersions();
            var id = String(Date.now());
            rows.unshift({
                id: id,
                nome: name.trim().slice(0, 80),
                salvo_em: new Date().toISOString(),
                base: clone(base),
                builds: clone(builds)
            });
            localStorage.setItem(STORAGE_SAVED, JSON.stringify(rows.slice(0, 30)));
            renderSavedVersions(id);
        });
        byId('pb-saved-builds').addEventListener('change', function () {
            var id = this.value;
            byId('pb-delete-save').disabled = !id;
            if (!id) return;
            var bundle = savedVersions().find(function (row) { return row.id === id; });
            if (bundle) loadBundle(bundle);
        });
        byId('pb-delete-save').addEventListener('click', function () {
            var id = byId('pb-saved-builds').value;
            if (!id) return;
            var rows = savedVersions().filter(function (row) { return row.id !== id; });
            localStorage.setItem(STORAGE_SAVED, JSON.stringify(rows));
            renderSavedVersions('');
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
                    byId('pb-status').textContent = error.message;
                    byId('pb-status').classList.add('is-error');
                }
            };
            reader.readAsText(file);
            this.value = '';
        });

        renderSavedVersions('');
        renderEditor();
        runPreview();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
