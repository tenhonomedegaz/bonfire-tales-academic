/* Local catalogue UI; the existing wiki endpoint and rules payload are unchanged. */
(() => {
    'use strict';
    const page = document.querySelector('.option-page');
    const dataElement = document.getElementById('opcoes-data');
    if (!page || !dataElement) return;
    let opcoesData;
    try { opcoesData = JSON.parse(dataElement.textContent); } catch (_) { return; }
    if (!Array.isArray(opcoesData)) return;
    const canEditWiki = page.dataset.canEdit === 'true';
    const byId = id => document.getElementById(id);
    const listContainer = byId('opcoesList');
    const listItemsContainer = byId('opcoesListItems');
    const detailContainer = byId('opcaoDetail');
    const searchInput = byId('optionSearch');
    const category = byId('optionCategory');
    const results = byId('optionResults');
    const reset = byId('optionReset');
    const activeSummary = byId('optionActiveFilters');
    const filterToggle = byId('optionFilters');
    const filterModal = byId('optionFilterModal');
    const filterClose = byId('optionFilterClose');
    const filterCount = byId('optionFilterCount');
    const typeFilters = byId('optionTypeFilters');
    const tagFilters = byId('optionTagFilters');
    const openListButton = byId('optionOpenList');
    const closeListButton = byId('optionCloseList');
    const listBackdrop = byId('optionListBackdrop');
    const sort = byId('optionSort');
    const media = matchMedia('(max-width: 1100px)');
    let filterOptions = { type: [], tag: [] };
    let activeFilters = { type: '', tag: '' };
    let draftFilters = { ...activeFilters };
    let filteredOpcoes = [];
    let selectedOpcaoId = null;
    let isAscending = true;
    let drawerOpen = false;
    let modalOpen = false;
    let outsideInert = new Map();

    const normalizeSearch = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
    const canonicalTag = value => normalizeSearch(value).replace(/[.;:!?]+$/g, '').replace(/\s+/g, ' ').trim();
    const html = value => escapeHtml(String(value ?? ''));
    function getExtraTags(option) {
        const seen = new Set();
        return String(option.etiquetas_adicionais || '').split(',').map(tag => tag.trim().replace(/[.;:!?]+$/g, '').trim()).filter(tag => {
            const key = canonicalTag(tag);
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }
    function renderMarkdown(value) {
        if (typeof renderBonfireMarkdown === 'function' && typeof sanitizeBonfireMarkdownHtml === 'function') {
            return sanitizeBonfireMarkdownHtml(renderBonfireMarkdown(value));
        }
        return '<p>' + html(value).replace(/\r?\n/g, '<br>') + '</p>';
    }
    function formatCopy(container) {
        // Separate line-based rule blocks without changing their wording or emphasis.
        [...container.querySelectorAll('p')].forEach(paragraph => {
            if (!paragraph.querySelector('br') || paragraph.closest('table, .bonfire-md-image-box')) return;
            const fragment = document.createDocumentFragment();
            let line = document.createElement('p');
            [...paragraph.childNodes].forEach(node => {
                if (node.nodeName === 'BR') {
                    if (line.textContent.trim() || line.children.length) fragment.appendChild(line);
                    line = document.createElement('p');
                } else line.appendChild(node);
            });
            if (line.textContent.trim() || line.children.length) fragment.appendChild(line);
            paragraph.replaceWith(fragment);
        });
        container.querySelectorAll('p > strong:first-child, li > strong:first-child').forEach(label => {
            if (/[:.]\s*$/.test(label.textContent) && label.textContent.length <= 70) label.classList.add('option-rule-label');
        });
    }
    function renderFilterChips() {
        [[typeFilters, filterOptions.type, 'type'], [tagFilters, filterOptions.tag, 'tag']].forEach(([container, values, kind]) => {
            container.replaceChildren();
            if (!values.length) {
                const empty = document.createElement('p');
                empty.textContent = 'Nenhuma opção de filtro cadastrada.';
                container.appendChild(empty);
            }
            values.forEach(value => {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = value;
                button.setAttribute('aria-pressed', String(draftFilters[kind] === value));
                button.addEventListener('click', () => {
                    draftFilters[kind] = draftFilters[kind] === value ? '' : value;
                    container.querySelectorAll('button').forEach(chip => chip.setAttribute('aria-pressed', String(chip.textContent === draftFilters[kind])));
                });
                container.appendChild(button);
            });
        });
    }
    function populateFilters() {
        filterOptions.type = [...new Set(opcoesData.map(option => option.tipo).filter(Boolean))].sort((a,b) => a.localeCompare(b,'pt-BR'));
        const tags = new Map();
        opcoesData.flatMap(getExtraTags).forEach(tag => {
            if (!tags.has(canonicalTag(tag))) tags.set(canonicalTag(tag), tag);
        });
        filterOptions.tag = [...tags.values()].sort((a,b) => a.localeCompare(b,'pt-BR'));
        category.replaceChildren(new Option('Todas as categorias', ''));
        filterOptions.type.forEach(type => category.appendChild(new Option(type, type)));
        category.value = activeFilters.type;
        renderFilterChips();
    }
    function selectedFromHash() {
        const fragment = location.hash.replace(/^#(?:opcao-)?/, '');
        if (!fragment) return null;
        try { return opcoesData.find(option => option.slug === decodeURIComponent(fragment))?.id ?? null; }
        catch (_) { return null; }
    }
    function applyFilters() {
        const query = normalizeSearch(searchInput.value.trim());
        filteredOpcoes = opcoesData.filter(option => {
            const haystack = [option.nome, option.pre_requisito, option.tipo, option.etiquetas_adicionais, option.descricao,
                ...(option.acessos || []).flatMap(access => [access.nome, access.classe, access.nivel])].join(' ');
            return (!query || normalizeSearch(haystack).includes(query))
                && (!activeFilters.type || option.tipo === activeFilters.type)
                && (!activeFilters.tag || getExtraTags(option).some(tag => canonicalTag(tag) === canonicalTag(activeFilters.tag)));
        }).sort((a,b) => (a.tipo || '').localeCompare(b.tipo || '', 'pt-BR')
            || (isAscending ? 1 : -1) * (a.nome || '').localeCompare(b.nome || '', 'pt-BR'));
        if (selectedOpcaoId === null && !location.hash) selectedOpcaoId = filteredOpcoes[0]?.id ?? null;
        const count = [activeFilters.type, activeFilters.tag].filter(Boolean).length;
        filterCount.textContent = count;
        filterCount.hidden = count === 0;
        reset.hidden = !query && !count;
        results.textContent = filteredOpcoes.length + (filteredOpcoes.length === 1 ? ' opção' : ' opções') + ' de ' + opcoesData.length;
        const labels = [activeFilters.type, activeFilters.tag].filter(Boolean);
        activeSummary.textContent = labels.join(' · ');
        activeSummary.hidden = !labels.length;
        category.value = activeFilters.type;
        renderList();
        const selected = opcoesData.find(option => option.id === selectedOpcaoId);
        if (selected) {
            renderOpcaoDetail(selected);
            if (!filteredOpcoes.some(option => option.id === selectedOpcaoId)) {
                const notice = document.createElement('div');
                notice.className = 'option-notice';
                const message = document.createElement('p');
                message.textContent = 'Esta opção está fora da busca ou dos filtros atuais.';
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = 'Mostrar na lista';
                button.addEventListener('click', resetFilters);
                notice.append(message, button);
                detailContainer.prepend(notice);
            }
        } else {
            detailContainer.innerHTML = '<div class="option-empty"><h2>' + (location.hash ? 'Opção não encontrada' : 'Nenhuma opção encontrada') + '</h2><p>' + (location.hash ? 'O link não corresponde a uma opção deste catálogo. Escolha outra na lista.' : 'Tente outra busca ou limpe os filtros do catálogo.') + '</p></div>';
        }
    }
    function renderList() {
        listItemsContainer.replaceChildren();
        if (!filteredOpcoes.length) {
            const empty = document.createElement('p');
            empty.className = 'option-list-empty';
            empty.textContent = 'Nenhuma opção encontrada. Tente outra busca ou limpe os filtros.';
            listItemsContainer.appendChild(empty);
            return;
        }
        const counts = new Map();
        filteredOpcoes.forEach(option => counts.set(option.tipo || 'Outras opções', (counts.get(option.tipo || 'Outras opções') || 0) + 1));
        let previous = null;
        filteredOpcoes.forEach(option => {
            const group = option.tipo || 'Outras opções';
            if (previous !== group) {
                const heading = document.createElement('h3');
                heading.className = 'option-group-title';
                const label = document.createElement('span');
                label.textContent = group;
                const count = document.createElement('small');
                count.textContent = counts.get(group);
                heading.append(label, count);
                listItemsContainer.appendChild(heading);
                previous = group;
            }
            const link = document.createElement('a');
            link.href = '#opcao-' + encodeURIComponent(option.slug);
            link.dataset.optionSlug = option.slug;
            if (option.id === selectedOpcaoId) link.setAttribute('aria-current', 'true');
            const name = document.createElement('span');
            name.textContent = option.nome;
            const tags = document.createElement('small');
            tags.textContent = getExtraTags(option).join(' · ');
            link.appendChild(name);
            if (tags.textContent) link.appendChild(tags);
            link.addEventListener('click', event => {
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
                event.preventDefault();
                selectOpcao(option.id);
            });
            listItemsContainer.appendChild(link);
        });
    }
    function selectOpcao(id) {
        const option = opcoesData.find(item => item.id === id);
        if (!option) return;
        const wasDrawerOpen = drawerOpen;
        selectedOpcaoId = id;
        const fragment = '#opcao-' + encodeURIComponent(option.slug);
        if (location.hash !== fragment) history.pushState(null, '', fragment);
        applyFilters();
        closeDrawer(false);
        const heading = detailContainer.querySelector('[data-option-title]');
        if (wasDrawerOpen) heading?.focus({preventScroll:true});
        else [...listItemsContainer.querySelectorAll('a')].find(link => link.dataset.optionSlug === option.slug)?.focus({preventScroll:true});
        if (detailContainer.getBoundingClientRect().top < 70) heading?.scrollIntoView({block:'start'});
    }
    function renderOpcaoDetail(option) {
        const tags = getExtraTags(option);
        const accesses = (option.acessos || []).map(access => '<li><strong>' + html(access.nome) + '</strong>'
            + (access.tipo === 'Subclasse' ? ' <span>(' + html(access.classe) + ')</span>' : '')
            + ' <span>· nível ' + html(access.nivel) + '</span></li>').join('');
        const prerequisite = String(option.pre_requisito || '').trim();
        detailContainer.innerHTML =
            '<header class="option-detail-header"><div class="option-emblem" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="1.25"><path d="M20 2 36 11v18L20 38 4 29V11Z"/><path d="m20 2 8 18-8 18-8-18Zm-16 9 24 9-24 9m32-18-24 9 24 9"/></svg></div><div class="option-detail-heading"><p class="option-eyebrow">' + html(option.tipo || 'Opção adicional') + '</p><h2 data-option-title tabindex="-1">' + html(option.nome) + '</h2></div>'
            + (canEditWiki && option.id !== null ? '<button type="button" class="wiki-edit-button" aria-expanded="false" aria-controls="opcao-editor">Editar wiki</button>' : '') + '</header>'
            + '<div class="option-detail-body">' + (tags.length ? '<div class="option-tags" aria-label="Etiquetas">' + tags.map(tag => '<span>' + html(tag) + '</span>').join('') + '</div>' : '')
            + '<dl class="option-meta"><div><dt>Pré-requisitos</dt><dd>' + html(prerequisite || 'Não informado no cadastro.') + '</dd></div><div><dt>Acesso por classe e subclasse</dt><dd>' + (accesses ? '<ul>' + accesses + '</ul>' : 'Não informado no cadastro. Consulte as regras da sua classe.') + '</dd></div></dl>'
            + '<div id="opcao-editor" data-option-editor></div><div data-option-preview class="option-copy bonfire-markdown">' + renderMarkdown(option.descricao) + '</div>'
            + '<details class="option-guidance"><summary>Como usar estas opções?</summary><p>Consulte os pré-requisitos e o acesso por classe ou subclasse antes de escolher. A disponibilidade e a quantidade de escolhas seguem as regras da sua classe e das suas habilidades. Este catálogo serve para consulta; clicar em uma opção não a adiciona à sua ficha.</p></details></div>';
        formatCopy(detailContainer.querySelector('[data-option-preview]'));
        detailContainer.querySelector('.wiki-edit-button')?.addEventListener('click', () => openOpcaoEditor(option.id));
    }
    function resetFilters() {
        searchInput.value = '';
        activeFilters = { type:'', tag:'' };
        draftFilters = { ...activeFilters };
        applyFilters();
    }

    function syncIsolation() {
        outsideInert.forEach((wasInert, element) => { element.inert = wasInert; });
        outsideInert = new Map();
        const target = modalOpen ? filterModal : drawerOpen ? listContainer : null;
        if (target) {
            let current = target;
            while (current && current !== document.body) {
                [...current.parentElement.children].forEach(sibling => {
                    if (sibling === current || /^(SCRIPT|STYLE|LINK)$/.test(sibling.tagName)) return;
                    outsideInert.set(sibling, sibling.inert);
                    sibling.inert = true;
                });
                current = current.parentElement;
            }
        }
        document.body.classList.toggle('option-overlay-open', Boolean(target));
    }
    function openDrawer() {
        if (!media.matches) return;
        drawerOpen = true;
        document.body.classList.add('option-menu-open');
        openListButton.setAttribute('aria-expanded','true');
        listContainer.setAttribute('role','dialog');
        listContainer.setAttribute('aria-modal','true');
        listBackdrop.hidden = false;
        syncIsolation();
        searchInput.focus();
    }
    function closeDrawer(restoreFocus = true) {
        drawerOpen = false;
        document.body.classList.remove('option-menu-open');
        openListButton.setAttribute('aria-expanded','false');
        listContainer.removeAttribute('role');
        listContainer.removeAttribute('aria-modal');
        listBackdrop.hidden = true;
        syncIsolation();
        if (restoreFocus && media.matches) openListButton.focus();
    }
    function openFilterModal() {
        draftFilters = { ...activeFilters };
        renderFilterChips();
        modalOpen = true;
        filterModal.hidden = false;
        filterToggle.setAttribute('aria-expanded','true');
        syncIsolation();
        filterClose.focus();
    }
    function closeFilterModal() {
        modalOpen = false;
        filterModal.hidden = true;
        filterToggle.setAttribute('aria-expanded','false');
        syncIsolation();
        filterToggle.focus();
    }
    function handleLayout() {
        const sidebarHadFocus = modalOpen || listContainer.contains(document.activeElement);
        if (modalOpen) closeFilterModal();
        closeDrawer(false);
        openListButton.hidden = !media.matches;
        closeListButton.hidden = !media.matches;
        if (media.matches && sidebarHadFocus) openListButton.focus();
    }
    function trapFocus(event, target) {
        const controls = [...target.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], textarea:not([disabled]), [tabindex="0"]')]
            .filter(control => control.tabIndex >= 0 && control.getAttribute('aria-hidden') !== 'true'
                && !control.closest('[inert]') && control.getClientRects().length);
        if (!controls.length) { event.preventDefault(); target.focus(); return; }
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || !target.contains(document.activeElement))) {
            event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !target.contains(document.activeElement))) {
            event.preventDefault(); first.focus();
        }
    }
    function getCookie(name) {
        const cookie = document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith(name + '='));
        return cookie ? cookie.slice(name.length + 1) : '';
    }
    function openOpcaoEditor(id) {
        const opcao = opcoesData.find(t => t.id === id);
        const mount = detailContainer.querySelector('[data-option-editor]');
        const preview = detailContainer.querySelector('[data-option-preview]');
        if (!canEditWiki || !opcao || !mount || !preview) return;
        if (mount.querySelector('form')) {
            mount.querySelector('input[name="nome"]')?.focus();
            return;
        }

        mount.innerHTML = `
            <form class="wiki-editor" data-option-edit-form>
                <div class="wiki-editor-grid">
                    <label>Nome
                        <input name="nome" value="${escapeHtml(opcao.nome)}">
                    </label>
                    <label>Tipo
                        <input name="tipo" value="${escapeHtml(opcao.tipo || '')}">
                    </label>
                    <label class="wide">Etiquetas Adicionais
                        <input name="etiquetas_adicionais" value="${escapeHtml(opcao.etiquetas_adicionais || '')}" placeholder="Separadas por vírgula">
                    </label>
                    <label class="wide">Pré-requisito
                        <input name="pre_requisito" value="${escapeHtml(opcao.pre_requisito || '')}">
                    </label>
                    <label class="wide">Descrição
                        <textarea name="descricao">${escapeHtml(opcao.descricao || '')}</textarea>
                    </label>
                </div>
                <p class="wiki-save-error" role="alert" tabindex="-1" hidden></p>
                <div class="wiki-editor-actions">
                    <button type="button" class="wiki-cancel" data-option-cancel>Cancelar</button>
                    <button type="submit" class="wiki-save">Salvar</button>
                </div>
            </form>
        `;

        const form = mount.querySelector('[data-option-edit-form]');
        detailContainer.querySelector('.wiki-edit-button')?.setAttribute('aria-expanded', 'true');
        form.querySelector('[data-option-cancel]').addEventListener('click', closeOpcaoEditor);
        const textarea = form.elements.descricao;
        textarea.addEventListener('input', () => {
            preview.innerHTML = renderMarkdown(textarea.value);
            formatCopy(preview);
        });
        form.addEventListener('submit', event => saveOpcaoEditor(event, opcao.id));
        form.addEventListener('keydown', event => {
            if (event.key === 'Escape' && form.getAttribute('aria-busy') !== 'true') {
                event.preventDefault();
                closeOpcaoEditor();
            }
        });
        form.elements.nome.focus();
    }

    function closeOpcaoEditor() {
        const mount = detailContainer.querySelector('[data-option-editor]');
        const form = mount?.querySelector('form');
        if (!form || form.getAttribute('aria-busy') === 'true') return;
        const opcao = opcoesData.find(item => item.id === selectedOpcaoId);
        const preview = detailContainer.querySelector('[data-option-preview]');
        if (opcao && preview) { preview.innerHTML = renderMarkdown(opcao.descricao); formatCopy(preview); }
        mount.innerHTML = '';
        const trigger = detailContainer.querySelector('.wiki-edit-button');
        trigger?.setAttribute('aria-expanded', 'false');
        trigger?.focus();
    }

    async function saveOpcaoEditor(event, id) {
        event.preventDefault();
        const form = event.currentTarget;
        if (form.getAttribute('aria-busy') === 'true') return;
        const data = Object.fromEntries(new FormData(form).entries());
        const error = form.querySelector('.wiki-save-error');
        const save = form.querySelector('.wiki-save');
        const cancel = form.querySelector('.wiki-cancel');
        error.hidden = true;
        form.setAttribute('aria-busy', 'true');
        save.disabled = true;
        cancel.disabled = true;

        try {
            const response = await fetch(`/wiki/opcoes/${id}/editar/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': decodeURIComponent(getCookie('csrftoken'))
                },
                body: JSON.stringify(data)
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok || !result.ok || !result.opcao) {
                throw new Error(result.error || 'Não foi possível salvar esta opção.');
            }
            const index = opcoesData.findIndex(o => o.id === id);
            if (index >= 0) opcoesData[index] = { ...result.opcao, acessos: opcoesData[index].acessos || [] };
            // O tipo ou as tags editados podem deixar a opção fora dos filtros ativos.
            searchInput.value = '';
            activeFilters = { type: '', tag: '' };
            draftFilters = { ...activeFilters };
            populateFilters();
            selectedOpcaoId = id;
            applyFilters(false);
            selectOpcao(id);
            detailContainer.querySelector('.wiki-edit-button')?.focus();
        } catch (failure) {
            error.textContent = failure.message || 'Não foi possível salvar esta opção.';
            error.hidden = false;
            error.focus();
        } finally {
            form.removeAttribute('aria-busy');
            save.disabled = false;
            cancel.disabled = false;
        }
    }


    document.body.classList.add('options-enhanced');
    [searchInput, category, filterToggle, sort].forEach(control => { control.disabled = false; });
    populateFilters();
    selectedOpcaoId = selectedFromHash();
    applyFilters();
    handleLayout();
    searchInput.addEventListener('input', applyFilters);
    category.addEventListener('change', () => { activeFilters.type = category.value; applyFilters(); });
    reset.addEventListener('click', resetFilters);
    sort.addEventListener('click', () => {
        isAscending = !isAscending;
        byId('optionSortLabel').textContent = isAscending ? 'A–Z' : 'Z–A';
        sort.setAttribute('aria-label', 'Ordem alfabética: ' + (isAscending ? 'A a Z' : 'Z a A') + '. Inverter ordem.');
        applyFilters();
    });
    filterToggle.addEventListener('click', openFilterModal);
    [byId('optionFilterBackdrop'), filterClose].forEach(control => control.addEventListener('click', closeFilterModal));
    byId('optionFilterApply').addEventListener('click', () => {
        activeFilters = { ...draftFilters };
        applyFilters();
        closeFilterModal();
    });
    byId('optionFilterClear').addEventListener('click', () => { resetFilters(); renderFilterChips(); });
    openListButton.addEventListener('click', openDrawer);
    [closeListButton, listBackdrop].forEach(control => control.addEventListener('click', () => closeDrawer()));
    media.addEventListener('change', handleLayout);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            if (modalOpen) { event.preventDefault(); closeFilterModal(); }
            else if (drawerOpen) { event.preventDefault(); closeDrawer(); }
        } else if (event.key === 'Tab' && (modalOpen || drawerOpen)) {
            trapFocus(event, modalOpen ? filterModal : listContainer);
        }
    });
    const restoreFromURL = () => { selectedOpcaoId = selectedFromHash(); applyFilters(); };
    window.addEventListener('popstate', restoreFromURL);
    window.addEventListener('hashchange', restoreFromURL);
})();

