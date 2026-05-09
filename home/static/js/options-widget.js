

(function () {
    'use strict';

    
    const WIDGET_CSS = `
.bonfire-options-widget {
    border: 1px solid var(--stroke);
    border-radius: 8px;
    margin: 1.5rem 0;
    overflow: hidden;
    background: var(--bg0);
    position: relative;
    display: flex;
    flex-direction: column;
}
.bonfire-options-widget-header {
    align-items: center;
    border-bottom: 1px solid var(--stroke);
    display: flex;
    flex-wrap: wrap;
    gap: .5rem;
    padding: .6rem .75rem;
    background: var(--bg1);
}
.bonfire-options-widget-title {
    color: var(--ember);
    flex: 1;
    font-family: 'Cinzel', serif;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .1em;
    text-transform: uppercase;
    min-width: 120px;
}
.bonfire-options-controls {
    display: flex;
    gap: .5rem;
    flex: 2;
    min-width: 200px;
}
.bonfire-options-search {
    background: var(--bg0);
    border: 1px solid var(--stroke);
    border-radius: 6px;
    color: var(--text);
    font-size: 12px;
    outline: none;
    padding: .35rem .65rem;
    width: 100%;
    box-sizing: border-box;
    transition: border-color .2s;
}
.bonfire-options-search:focus { border-color: var(--ember); }

.bonfire-options-filter-btn {
    background: var(--bg0);
    border: 1px solid var(--stroke);
    border-radius: 6px;
    color: var(--muted);
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
    padding: 0 .75rem;
    display: flex;
    align-items: center;
    gap: .4rem;
    white-space: nowrap;
    transition: all .2s;
}
.bonfire-options-filter-btn:hover { border-color: var(--ember); color: var(--text); }
.bonfire-options-filter-btn.active { background: var(--ember); color: #fff; border-color: var(--ember); }

.bonfire-options-filters-area {
    background: var(--bg1);
    border-bottom: 1px solid var(--stroke);
    display: none;
    padding: .75rem;
}
.bonfire-options-filters-area.open { display: block; }
.bonfire-options-filter-group { margin-bottom: .75rem; }
.bonfire-options-filter-group:last-child { margin-bottom: 0; }
.bonfire-options-filter-label {
    color: var(--muted);
    display: block;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: .1em;
    margin-bottom: .4rem;
    text-transform: uppercase;
}
.bonfire-options-chips {
    display: flex;
    flex-wrap: wrap;
    gap: .4rem;
}
.bonfire-options-chip {
    background: var(--bg0);
    border: 1px solid var(--stroke);
    border-radius: 4px;
    color: var(--muted);
    cursor: pointer;
    font-size: 10px;
    padding: .2rem .5rem;
    transition: all .15s;
}
.bonfire-options-chip:hover { border-color: var(--ember); color: var(--text); }
.bonfire-options-chip.active { background: var(--ember); color: #fff; border-color: var(--ember); }


.bonfire-options-workspace {
    display: flex;
    flex-direction: column;
    min-height: 400px;
    max-height: 600px;
}
@media (min-width: 1101px) {
    .bonfire-options-workspace { flex-direction: row; }
}

.bonfire-options-list-panel {
    flex: 0 0 300px;
    border-right: 1px solid var(--stroke);
    overflow-y: auto;
    background: var(--bg0);
}
@media (max-width: 1100px) {
    .bonfire-options-list-panel { flex: 1; border-right: 0; border-bottom: 1px solid var(--stroke); max-height: 250px; }
}

.bonfire-options-detail-panel {
    flex: 1;
    overflow-y: auto;
    padding: 1.25rem;
    background: var(--bg0);
}


.bonfire-options-item {
    padding: .75rem;
    cursor: pointer;
    border-bottom: 1px solid var(--stroke);
    transition: all .15s;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: .5rem;
}
.bonfire-options-item:hover { background: var(--bg1); }
.bonfire-options-item.selected { background: var(--bg1); border-left: 3px solid var(--ember); padding-left: calc(.75rem - 3px); }

.bonfire-options-item-name {
    color: var(--muted);
    font-size: 13px;
    font-weight: 700;
    transition: color .15s;
}
.bonfire-options-item.selected .bonfire-options-item-name { color: var(--text); }

.bonfire-options-item-prereq {
    border: 1px solid rgba(234, 179, 8, 0.3);
    color: rgba(234, 179, 8, 0.8);
    border-radius: 4px;
    font-size: 9px;
    font-weight: 700;
    padding: 1px 6px;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: fit-content;
}

.bonfire-options-item-badge {
    border: 1px solid var(--stroke);
    border-radius: 4px;
    color: var(--muted);
    font-size: 9px;
    font-weight: 900;
    padding: 1px 6px;
    text-transform: uppercase;
    white-space: nowrap;
}


.bonfire-options-detail-empty {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    gap: 1rem;
    opacity: .5;
}
.bonfire-options-detail-header {
    margin-bottom: 1rem;
}
.bonfire-options-detail-tipo {
    display: inline-block;
    border: 1px solid var(--flame);
    color: var(--flame);
    border-radius: 4px;
    font-size: 10px;
    font-weight: 900;
    padding: 2px 8px;
    text-transform: uppercase;
    margin-bottom: .75rem;
}
.bonfire-options-detail-title {
    color: var(--text);
    font-family: 'Cinzel', serif;
    font-size: 1.25rem;
    font-weight: 700;
    text-transform: uppercase;
}
.bonfire-options-detail-prereq-row {
    display: flex;
    justify-content: flex-end;
    margin-top: -1.5rem;
    margin-bottom: 1rem;
}
.bonfire-options-detail-prereq-tag {
    border: 1px solid var(--stroke);
    border-radius: 4px;
    color: var(--muted);
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    text-transform: uppercase;
}
.bonfire-options-detail-prereq-val {
    color: var(--text);
    text-transform: none;
    font-weight: 500;
    margin-left: .25rem;
}

.bonfire-options-empty {
    color: var(--muted);
    font-size: 12px;
    padding: 1.5rem;
    text-align: center;
}
.bonfire-options-loading {
    background: var(--bg1);
    border: 1px solid var(--stroke);
    border-radius: 8px;
    color: var(--muted);
    display: block;
    font-size: 12px;
    padding: 1.5rem;
    text-align: center;
}
`;

    
    if (!document.getElementById('bonfire-options-widget-styles')) {
        const style = document.createElement('style');
        style.id = 'bonfire-options-widget-styles';
        style.textContent = WIDGET_CSS;
        document.head.appendChild(style);
    }

    
    const _cache = {};

    async function fetchOpcoes(tipo) {
        const key = tipo.toLowerCase();
        if (_cache[key]) return _cache[key];
        try {
            const url = `/api/opcoes/?tipo=${encodeURIComponent(tipo)}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(res.statusText);
            const json = await res.json();
            _cache[key] = json.opcoes || [];
        } catch (e) {
            console.warn('[options-widget] Erro ao carregar:', e);
            _cache[key] = [];
        }
        return _cache[key];
    }

    
    function renderWidget(container, tipo, opcoes) {
        const label = tipo.charAt(0).toUpperCase() + tipo.slice(1);
        
        
        const categories = [...new Set(opcoes.map(o => o.tipo).filter(Boolean))].sort();
        
        const isLevelPrereq = (s) => /nível/i.test(s) || /\d+(º|ª)/.test(s);
        const prereqs = [...new Set(opcoes.flatMap(o => 
            (o.pre_requisito || '')
            .split(/,|\sou\s/i)
            .map(s => s.trim())
            .filter(s => s && s.toLowerCase() !== 'nenhum' && !isLevelPrereq(s))
        ))].sort();

        const tagsRaw = opcoes.flatMap(o => (o.etiquetas_adicionais || '').split(',').map(t => t.trim()).filter(Boolean));
        const tags = [...new Set(tagsRaw)].sort();

        let activeCategory = '';
        let activePrereq = '';
        let activeTag = '';
        let selectedId = null;

        container.innerHTML = `
            <div class="bonfire-options-widget-header">
                <span class="bonfire-options-widget-title">⚔ ${label}</span>
                <div class="bonfire-options-controls">
                    <input
                        class="bonfire-options-search"
                        placeholder="Buscar…"
                        type="search"
                        aria-label="Buscar em ${label}"
                    >
                    <button class="bonfire-options-filter-btn" type="button">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/></svg>
                        Filtros
                    </button>
                </div>
            </div>
            <div class="bonfire-options-filters-area">
                ${categories.length > 1 ? `
                <div class="bonfire-options-filter-group">
                    <span class="bonfire-options-filter-label">Categoria</span>
                    <div class="bonfire-options-chips" data-filter="category">
                        ${categories.map(c => `<button class="bonfire-options-chip" data-val="${c}">${c}</button>`).join('')}
                    </div>
                </div>` : ''}
                ${tags.length > 0 ? `
                <div class="bonfire-options-filter-group">
                    <span class="bonfire-options-filter-label">Tags Adicionais</span>
                    <div class="bonfire-options-chips" data-filter="tag">
                        ${tags.map(t => `<button class="bonfire-options-chip" data-val="${t}">${t}</button>`).join('')}
                    </div>
                </div>` : ''}
                ${prereqs.length > 0 ? `
                <div class="bonfire-options-filter-group">
                    <span class="bonfire-options-filter-label">Pré-requisitos</span>
                    <div class="bonfire-options-chips" data-filter="prereq">
                        ${prereqs.map(p => `<button class="bonfire-options-chip" data-val="${p}">${p}</button>`).join('')}
                    </div>
                </div>` : ''}
            </div>
            <div class="bonfire-options-workspace">
                <div class="bonfire-options-list-panel"></div>
                <div class="bonfire-options-detail-panel">
                    <div class="bonfire-options-detail-empty">
                        <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="1"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18s-3.332.477-4.5 1.253"/></svg>
                        <span>Selecione uma opção</span>
                    </div>
                </div>
            </div>
        `;

        const searchInput = container.querySelector('.bonfire-options-search');
        const filterBtn = container.querySelector('.bonfire-options-filter-btn');
        const filtersArea = container.querySelector('.bonfire-options-filters-area');
        const listEl = container.querySelector('.bonfire-options-list-panel');
        const detailEl = container.querySelector('.bonfire-options-detail-panel');

        filterBtn.addEventListener('click', () => {
            filtersArea.classList.toggle('open');
            filterBtn.classList.toggle('active', filtersArea.classList.contains('open'));
        });

        
        container.querySelectorAll('.bonfire-options-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const type = chip.parentElement.dataset.filter;
                const val = chip.dataset.val;

                if (type === 'category') {
                    activeCategory = activeCategory === val ? '' : val;
                } else if (type === 'prereq') {
                    activePrereq = activePrereq === val ? '' : val;
                } else if (type === 'tag') {
                    activeTag = activeTag === val ? '' : val;
                }

                
                container.querySelectorAll(`.bonfire-options-chips[data-filter="${type}"] .bonfire-options-chip`).forEach(c => {
                    let compareActive = '';
                    if (type === 'category') compareActive = activeCategory;
                    else if (type === 'prereq') compareActive = activePrereq;
                    else if (type === 'tag') compareActive = activeTag;
                    
                    c.classList.toggle('active', c.dataset.val === compareActive);
                });

                renderList(searchInput.value);
            });
        });

        function renderList(query) {
            const q = (query || '').toLowerCase();
            const filtered = opcoes.filter(o => {
                const matchesSearch = !q || (
                    (o.nome || '').toLowerCase().includes(q) ||
                    (o.pre_requisito || '').toLowerCase().includes(q) ||
                    (o.descricao || '').toLowerCase().includes(q)
                );
                const matchesCategory = !activeCategory || o.tipo === activeCategory;
                const matchesPrereq = !activePrereq || (o.pre_requisito || '').split(/,|\sou\s/i).map(s => s.trim()).includes(activePrereq);
                const matchesTag = !activeTag || (o.etiquetas_adicionais || '').split(',').map(s => s.trim()).includes(activeTag);

                return matchesSearch && matchesCategory && matchesPrereq && matchesTag;
            });

            if (!filtered.length) {
                listEl.innerHTML = `<p class="bonfire-options-empty">Nenhuma opção encontrada.</p>`;
                return;
            }

            listEl.innerHTML = filtered.map(o => {
                const isSelected = o.id === selectedId;
                const prereq = o.pre_requisito ? escapeHtml(o.pre_requisito) : '';
                const hasPrereq = o.pre_requisito && o.pre_requisito.toLowerCase() !== 'nenhum';
                const prereqTag = hasPrereq ? `<span class="bonfire-options-item-prereq" title="${prereq}">${prereq}</span>` : '';
                
                const itemTags = (o.etiquetas_adicionais || '').split(',').map(t => t.trim()).filter(Boolean);
                const tagBadges = itemTags.map(t => `<span class="bonfire-options-item-badge" style="border-color:var(--ember); color:var(--ember)">${escapeHtml(t)}</span>`).join('');
                
                return `
                <div class="bonfire-options-item ${isSelected ? 'selected' : ''}" data-id="${o.id}">
                    <div style="flex:1; min-width:0">
                        <div class="bonfire-options-item-name">${escapeHtml(o.nome)}</div>
                        <div style="display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .5rem;">
                            <span class="bonfire-options-item-badge">${escapeHtml(o.tipo || '')}</span>
                            ${tagBadges}
                            ${prereqTag}
                        </div>
                    </div>
                </div>`;
            }).join('');

            
            listEl.querySelectorAll('.bonfire-options-item').forEach(item => {
                item.addEventListener('click', () => {
                    const id = parseInt(item.dataset.id);
                    selectedId = id;
                    renderList(searchInput.value);
                    showDetail(opcoes.find(o => o.id === id));
                });
            });
        }

        function showDetail(o) {
            if (!o) return;

            const descHtml = (o.descricao || '').trim()
                ? (window.marked && typeof window.marked.parse === 'function'
                    ? window.marked.parse(normalizeMarkdown(o.descricao), { breaks: true, gfm: true })
                    : `<p>${escapeHtml(o.descricao)}</p>`)
                : '<em style="color:var(--muted)">Sem descrição.</em>';

            const hasPrereq = o.pre_requisito && o.pre_requisito.toLowerCase() !== 'nenhum';

            detailEl.innerHTML = `
                <div class="bonfire-options-detail-header">
                    <span class="bonfire-options-detail-tipo">${escapeHtml(o.tipo || '')}</span>
                    ${hasPrereq ? `
                        <div class="bonfire-options-detail-prereq-row">
                            <div class="bonfire-options-detail-prereq-tag">
                                PRÉ-REQ:<span class="bonfire-options-detail-prereq-val">${escapeHtml(o.pre_requisito)}</span>
                            </div>
                        </div>
                    ` : ''}
                    <h2 class="bonfire-options-detail-title">${escapeHtml(o.nome)}</h2>
                </div>

                <div class="bonfire-markdown" style="font-size:13px; color:var(--muted)">
                    ${descHtml}
                </div>
            `;
            
            
            if (window.innerWidth < 768) {
                detailEl.scrollIntoView({ behavior: 'smooth' });
            }
        }

        renderList('');
        searchInput.addEventListener('input', () => renderList(searchInput.value));
    }

    
    async function hydrateAll() {
        const widgets = document.querySelectorAll('.bonfire-options-widget[data-tipo]:not([data-hydrated])');
        if (!widgets.length) return;

        
        const byTipo = {};
        widgets.forEach(el => {
            const tipo = el.dataset.tipo || '';
            if (!byTipo[tipo]) byTipo[tipo] = [];
            byTipo[tipo].push(el);
        });

        await Promise.all(
            Object.entries(byTipo).map(async ([tipo, els]) => {
                const opcoes = await fetchOpcoes(tipo);
                els.forEach(el => {
                    if (el.dataset.hydrated) return; 
                    renderWidget(el, tipo, opcoes);
                    el.dataset.hydrated = '1';
                });
            })
        );
    }

    

    
    function init() {
        hydrateAll();

        
        document.addEventListener('toggle', (e) => {
            const details = e.target;
            if (details.tagName !== 'DETAILS' || !details.open) return;
            const pending = details.querySelectorAll('.bonfire-options-widget[data-tipo]:not([data-hydrated])');
            if (pending.length) hydrateAll();
        }, true);

        
        const observer = new MutationObserver((mutations) => {
            let hasNew = false;
            mutations.forEach(m => {
                m.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {
                        if (node.classList.contains('bonfire-options-widget') || node.querySelector('.bonfire-options-widget')) {
                            hasNew = true;
                        }
                    }
                });
            });
            if (hasNew) hydrateAll();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function normalizeMarkdown(text) {
        return (text || '').replace(/\\n/g, '\n');
    }

    
    window.bonfireOptionsWidget = { hydrate: hydrateAll };
})();