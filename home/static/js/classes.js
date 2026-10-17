/* Presentation-only class explorer. Original Markdown, subclass resources and wiki writes retained. */
(function () {
  'use strict';
  document.body.classList.add('classes-ready');
  function renderMarkdownContent(value, element) {
    if (typeof renderBonfireMarkdown === 'function' && typeof sanitizeBonfireMarkdownHtml === 'function') {
      const card = element?.closest('[data-feature-card]');
      const isManifestation = card?.hasAttribute('data-manifestation-feature');
      // These three source blocks contain the same four choices. Render them
      // as readable sections; the independent selector below controls all three.
      // The original Markdown/textarea is never rewritten or saved by this layer.
      const source = isManifestation
        ? String(value || '').replace(/::toggle\s*\n([\s\S]*?)\n::endtoggle/gi, '$1')
        : value;
      const body = document.createElement('div');
      body.innerHTML = sanitizeBonfireMarkdownHtml(renderBonfireMarkdown(source));
      if (!card) return body.innerHTML;

      // A source soft break often separates a quotation, rule, or formula.
      // Give each its own paragraph without splitting lists or inline markup.
      body.querySelectorAll('p').forEach(paragraph => {
        if (paragraph.closest('li,blockquote') || ![...paragraph.children].some(child => child.tagName === 'BR')) return;
        const fragment = document.createDocumentFragment();
        let part = document.createElement('p');
        [...paragraph.childNodes].forEach(node => {
          if (node.nodeName === 'BR') {
            if (part.textContent.trim() || part.children.length) fragment.append(part);
            part = document.createElement('p');
          } else part.append(node);
        });
        if (part.textContent.trim() || part.children.length) fragment.append(part);
        paragraph.replaceWith(fragment);
      });

      const title = card.querySelector('[data-feature-title]')?.textContent.replace(/^NÃ­vel\s+\d+:\s*/, '').trim();
      body.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(heading => {
        if (heading.textContent.trim() === title) heading.remove();
      });
      // The page is h1, Habilidades h2 and each feature h3. Source subsections
      // therefore begin at h4, including legacy ##### headings such as Truques.
      const headings = [...body.querySelectorAll('h1,h2,h3,h4,h5,h6')];
      const firstLevel = Math.min(...headings.map(heading => Number(heading.tagName.slice(1))));
      headings.forEach(heading => {
        const level = Math.min(6, 4 + Number(heading.tagName.slice(1)) - firstLevel);
        const replacement = document.createElement(`h${level}`);
        replacement.append(...heading.childNodes);
        heading.replaceWith(replacement);
      });
      body.querySelectorAll('p').forEach(paragraph => {
        const onlyChild = paragraph.firstElementChild;
        const text = paragraph.textContent.trim();
        if (onlyChild?.tagName === 'STRONG' && paragraph.childElementCount === 1
            && onlyChild.textContent.trim() === text && text.length <= 100
            && !paragraph.closest('li,blockquote')) {
          const heading = document.createElement(isManifestation ? 'h5' : 'h4');
          heading.append(...onlyChild.childNodes);
          paragraph.replaceWith(heading);
        } else if (onlyChild?.tagName === 'EM' && paragraph.childElementCount === 1
                   && onlyChild.textContent.trim() === text && /^["â€œ]/.test(text)) {
          paragraph.classList.add('bonfire-class-flavor');
        }
      });

      if (isManifestation) {
        // The revised familiar rules contain six definitions in a single
        // paragraph. Lay out those exact source labels as separate list items.
        const familiarTypes = ['AberraÃ§Ã£o', 'Celestial', 'DragÃ£o', 'Fada', 'Ãnfero', 'Morto-Vivo'];
        body.querySelectorAll('p').forEach(paragraph => {
          const labels = [...paragraph.children].filter(child => child.tagName === 'STRONG'
            && familiarTypes.includes(child.textContent.trim()));
          if (labels.length !== familiarTypes.length
              || !labels.every((label, index) => label.textContent.trim() === familiarTypes[index])) return;
          const intro = document.createElement('p');
          const list = document.createElement('ul');
          let item = null;
          [...paragraph.childNodes].forEach(node => {
            if (labels.includes(node)) {
              item = document.createElement('li');
              list.append(item);
            }
            (item || intro).append(node);
          });
          paragraph.replaceWith(intro, list);
        });
        const choices = new Map([['Arma MÃ­stica', 'arma'], ['Contrato MÃ­stico', 'contrato'],
          ['Livro MÃ­stico', 'livro'], ['Marca MÃ­stica', 'marca']]);
        let section = null;
        [...body.childNodes].forEach(node => {
          const slug = /^H[4-6]$/.test(node.nodeName) && choices.get(node.textContent.trim());
          if (slug) {
            section = document.createElement('section');
            section.className = 'bonfire-class-manifestation';
            section.dataset.manifestationSlug = slug;
            body.insertBefore(section, node);
          }
          if (section) section.append(node);
        });
      }
      return body.innerHTML;
    }
    const source = typeof normalizeMarkdown === 'function' ? normalizeMarkdown(value) : String(value || '');
    return escapeHtml(source).replace(/\n/g, '<br>');
  }

  function initPage() {
    // Attribute chips belong to the catalogue, not a hidden sidebar filter.
    if (document.querySelector('[data-class-page]')) classAttribute = '';
    // Markdown & Toggles
    document.querySelectorAll('[data-markdown]').forEach(element => {
      element.innerHTML = renderMarkdownContent(element.textContent, element);
    });

    // Fix trait bullet points
    document.querySelectorAll('.trait-value').forEach(el => {
      // Handle both start of string and after <br>
      el.innerHTML = el.innerHTML.replace(/(^|<br>\s*)-\s+/g, '$1â€¢ ');
    });

    const subclassButtons = Array.from(document.querySelectorAll('[data-subclass-toggle]'));
    const subclassContents = Array.from(document.querySelectorAll('.subclass-content'));
    const subclassFeatures = Array.from(document.querySelectorAll('.subclass-feature'));
    const subclassResourceEmptyCells = Array.from(document.querySelectorAll('.subclass-resource-empty'));
    const subclassColumns = Array.from(document.querySelectorAll('[data-subclass-column]'));
    const spellSlotsHeader = document.querySelector('[data-spell-slots-header]');
    const spellSlotsRow = document.querySelector('[data-spell-slots-row]');
    const spellSlotColumns = Array.from(document.querySelectorAll('[data-spell-slot-column]'));
    const subclassAnchor = document.querySelector('[data-subclass-anchor]');
    const subclassPresentations = [...document.querySelectorAll('[data-subclass-presentation]')];
    const featureList = document.querySelector('[data-feature-list]');
    const baseFeatures = Array.from(document.querySelectorAll('[data-base-feature]'));
    const subclassOnlyToggle = document.querySelector('[data-subclass-only-toggle]');
    const subclassOnlyCheck = document.querySelector('[data-subclass-only-check]');
    let subclassOnlyMode = false;
    let currentSlug = '';
    let currentManifestation = '';
    const manifestationButtons = [...document.querySelectorAll('[data-manifestation-toggle]')];
    const manifestationStatus = document.querySelector('[data-manifestation-status]');
    if (document.querySelector('[data-manifestation-slug]')) {
      document.querySelector('[data-manifestation-controls]')?.removeAttribute('hidden');
    }

    function updateSpecializationOnlyToggle() {
      const selected = Boolean(currentSlug || currentManifestation);
      subclassOnlyToggle?.classList.toggle('hidden', !selected);
      subclassOnlyToggle?.classList.toggle('flex', selected);
      if (!selected) {
        subclassOnlyMode = false;
        if (subclassOnlyCheck) subclassOnlyCheck.checked = false;
        subclassOnlyToggle?.classList.remove('border-[var(--spark)]', 'bg-[var(--spark)]/10', 'text-[var(--spark)]');
      }
    }

    if (subclassOnlyCheck) {
      subclassOnlyCheck.addEventListener('change', () => {
        subclassOnlyMode = subclassOnlyCheck.checked;
        if (subclassOnlyToggle) {
          subclassOnlyToggle.classList.toggle('border-[var(--spark)]', subclassOnlyMode);
          subclassOnlyToggle.classList.toggle('bg-[var(--spark)]/10', subclassOnlyMode);
          subclassOnlyToggle.classList.toggle('text-[var(--spark)]', subclassOnlyMode);
        }
        applyBaseFeatureVisibility();
      });
    }

    const featureSearch = document.querySelector('[data-class-feature-search]');
    const featureLevel = document.querySelector('[data-class-feature-level]');
    const featureCards = [...document.querySelectorAll('[data-feature-card]')];
    const featureStatus = document.querySelector('[data-class-feature-status]');
    const featureEmpty = document.querySelector('[data-class-feature-empty]');
    const normalizeSearch = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
    const levels = [...new Set(featureCards.map(card => Number(card.dataset.featureLevel)))].sort((a,b) => a-b);
    levels.forEach(level => { const option = document.createElement('option'); option.value = String(level); option.textContent = `NÃ­vel ${level}`; featureLevel?.append(option); });
    document.querySelector('[data-class-feature-filters]')?.removeAttribute('hidden');
    featureSearch?.addEventListener('input', applyBaseFeatureVisibility);
    featureLevel?.addEventListener('change', applyBaseFeatureVisibility);
    document.querySelector('[data-class-feature-clear]')?.addEventListener('click', () => {
      featureSearch.value = ''; featureLevel.value = ''; applyBaseFeatureVisibility(); featureSearch.focus();
    });
    function applyBaseFeatureVisibility() {
      document.querySelectorAll('[data-manifestation-slug]').forEach(section => {
        section.hidden = Boolean(currentManifestation && section.dataset.manifestationSlug !== currentManifestation);
      });
      const query = normalizeSearch(featureSearch?.value).trim();
      let count = 0;
      featureCards.forEach(card => {
        const sub = card.dataset.subclassSlug;
        const available = sub ? sub === currentSlug : !(subclassOnlyMode && (currentSlug || currentManifestation))
          || Boolean(currentManifestation && card.hasAttribute('data-manifestation-feature'));
        const readableNodes = [...(card.querySelector('[data-markdown]')?.childNodes || [])]
          .filter(node => !node.hidden).map(node => node.textContent).join(' ');
        const text = normalizeSearch(card.querySelector('[data-feature-title]')?.textContent + ' ' + readableNodes);
        const levelMatch = !featureLevel?.value || card.dataset.featureLevel === featureLevel.value;
        const visible = available && levelMatch && (!query || text.includes(query));
        card.classList.toggle('hidden', !visible);
        if (visible) count++;
      });
      if (featureStatus) featureStatus.textContent = `${count} habilidade${count === 1 ? '' : 's'}`;
      if (featureEmpty) featureEmpty.hidden = count > 0 || !featureCards.length;
    }

    function setSubclass(slug, initial = false) {
      currentSlug = slug;
      // Controls are below the table. Preserve their position when new columns
      // change the naturally-sized table's height, without temporary spacers.
      const anchorTop = !initial && subclassAnchor ? subclassAnchor.getBoundingClientRect().top : null;

      subclassButtons.forEach(button => {
        const active = button.dataset.subclassToggle === slug;
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
        button.classList.toggle('is-active', active);
        button.classList.toggle('border-[var(--spark)]', active && slug);
        button.classList.toggle('bg-[var(--spark)]/10', active && slug);
        button.classList.toggle('text-[var(--spark)]', active && slug);
        button.classList.toggle('border-[var(--flame)]', active && !slug);
        button.classList.toggle('bg-[var(--flame)]/10', active && !slug);
        button.classList.toggle('text-[var(--text)]', active);
        button.classList.toggle('border-[var(--stroke)]', !active);
        button.classList.toggle('text-[var(--muted)]', !active);
      });

      updateSpecializationOnlyToggle();

      subclassPresentations.forEach(panel => {
        panel.hidden = !slug || panel.dataset.subclassPresentation !== slug;
        if (panel.hidden) panel.querySelector('details')?.removeAttribute('open');
      });

      subclassContents.forEach(element => {
        element.classList.toggle('hidden', !slug || element.dataset.subclassSlug !== slug);
      });

      subclassFeatures.forEach(element => {
        element.classList.toggle('hidden', !slug || element.dataset.subclassSlug !== slug);
      });

      subclassResourceEmptyCells.forEach(element => {
        element.classList.toggle('hidden', Boolean(slug));
      });

      subclassColumns.forEach(element => {
        const allowedSlugs = (element.dataset.subclassColumn || '').split(/\s+/).filter(Boolean);
        element.classList.toggle('is-collapsed-column', !slug || !allowedSlugs.includes(slug));
      });

      if (spellSlotsHeader) {
        const visibleSpellSlots = spellSlotColumns.filter(element => !element.classList.contains('is-collapsed-column')).length;
        spellSlotsHeader.classList.toggle('hidden', visibleSpellSlots === 0);
        spellSlotsRow?.classList.toggle('hidden', visibleSpellSlots === 0);
        spellSlotsHeader.colSpan = Math.max(visibleSpellSlots, 1);
      }

      // Apply base feature visibility based on subclass-only mode
      applyBaseFeatureVisibility();

      if (!initial && anchorTop !== null) {
        requestAnimationFrame(() => {
          const nextTop = subclassAnchor.getBoundingClientRect().top;
          window.scrollBy({ top: nextTop - anchorTop, left: 0, behavior: 'auto' });
        });
      }

      const url = new URL(window.location.href);
      if (slug) {
        url.searchParams.set('subclasse', slug);
      } else {
        url.searchParams.delete('subclasse');
      }
      window.history.replaceState({}, '', url);
      classRenderedRoute = url.pathname + url.search;
    }

    subclassButtons.forEach(button => {
      button.addEventListener('click', () => setSubclass(button.dataset.subclassToggle || ''));
    });

    const urlParams = new URLSearchParams(window.location.search);
    function setManifestation(slug, initial = false) {
      const anchorTop = !initial && subclassAnchor ? subclassAnchor.getBoundingClientRect().top : null;
      currentManifestation = slug;
      manifestationButtons.forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.manifestationToggle === slug));
      });
      if (manifestationStatus) manifestationStatus.textContent = slug
        ? `${manifestationButtons.find(button => button.dataset.manifestationToggle === slug)?.textContent.trim()} Â· nÃ­veis 1, 3 e 18`
        : 'Comparando as quatro manifestaÃ§Ãµes Â· nÃ­veis 1, 3 e 18';
      updateSpecializationOnlyToggle();
      applyBaseFeatureVisibility();
      if (!initial && anchorTop !== null) requestAnimationFrame(() => {
        window.scrollBy({top: subclassAnchor.getBoundingClientRect().top - anchorTop, left: 0, behavior: 'auto'});
      });
      const url = new URL(window.location.href);
      if (slug) url.searchParams.set('manifestacao', slug);
      else url.searchParams.delete('manifestacao');
      window.history.replaceState({}, '', url);
      classRenderedRoute = url.pathname + url.search;
    }
    manifestationButtons.forEach(button => button.addEventListener('click', () => setManifestation(button.dataset.manifestationToggle || '')));
    if (manifestationButtons.length) {
      const requested = urlParams.get('manifestacao') || '';
      setManifestation(manifestationButtons.some(button => button.dataset.manifestationToggle === requested) ? requested : '', true);
    }
    const requestedSubclass = urlParams.get('subclasse') || '';
    setSubclass(subclassButtons.some(button => button.dataset.subclassToggle === requestedSubclass)
      ? requestedSubclass : '', true);

    bindCatalogControls();
    filterClasses();

    // Wiki Editor
    document.querySelectorAll('[data-feature-card]').forEach(card => {
      const edit = card.querySelector('[data-feature-edit]');
      const form = card.querySelector('[data-feature-form]');
      const cancel = card.querySelector('[data-feature-cancel]');
      const preview = card.querySelector('[data-markdown]');
      const title = card.querySelector('[data-feature-title]');
      const textarea = form?.elements?.descricao;
      if (!edit || !form || !preview || !textarea) return;
      form.id = `class-feature-editor-${card.dataset.featureId}`;
      edit.setAttribute('aria-controls', form.id);
      edit.setAttribute('aria-expanded', 'false');
      const error = document.createElement('p');
      error.className = 'wiki-inline-error';
      error.setAttribute('role', 'alert');
      error.tabIndex = -1;
      error.hidden = true;
      form.querySelector('.wiki-inline-actions').before(error);
      const closeEditor = () => {
        if (form.getAttribute('aria-busy') === 'true') return;
        form.reset();
        preview.innerHTML = renderMarkdownContent(textarea.value, preview);
        applyBaseFeatureVisibility();
        error.hidden = true;
        form.classList.remove('is-open');
        edit.setAttribute('aria-expanded', 'false');
        edit.focus();
      };

      edit.addEventListener('click', () => {
        form.classList.add('is-open');
        edit.setAttribute('aria-expanded', 'true');
        textarea.focus();
      });
      cancel?.addEventListener('click', closeEditor);
      form.addEventListener('keydown', event => {
        if (event.key === 'Escape' && form.getAttribute('aria-busy') !== 'true') {
          event.preventDefault();
          closeEditor();
        }
      });
      textarea.addEventListener('input', () => {
        preview.innerHTML = renderMarkdownContent(textarea.value, preview);
        applyBaseFeatureVisibility();
      });
      form.addEventListener('submit', async event => {
        event.preventDefault();
        if (form.getAttribute('aria-busy') === 'true') return;
        const featureId = card.dataset.featureId;
        const data = Object.fromEntries(new FormData(form).entries());
        if ('tags_json_text' in data) {
          data.tags_json = data.tags_json_text.split('\n').map(t => t.trim()).filter(Boolean);
          delete data.tags_json_text;
        }
        const controls = Array.from(form.querySelectorAll('input, textarea, button'));
        error.hidden = true;
        form.setAttribute('aria-busy', 'true');
        controls.forEach(control => { control.disabled = true; });
        try {
          const response = await fetch(`/wiki/habilidades-classe/${featureId}/editar/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': decodeURIComponent(wikiCookie('csrftoken'))
            },
            body: JSON.stringify(data)
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok || !result.ok || !result.feature) {
            throw new Error(result.error || 'NÃ£o foi possÃ­vel salvar a habilidade.');
          }
          title.textContent = `NÃ­vel ${result.feature.niveladquirido}: ${result.feature.nome}`;
          preview.innerHTML = renderMarkdownContent(result.feature.descricao, preview);
          form.elements.nome.defaultValue = result.feature.nome;
          form.elements.niveladquirido.defaultValue = result.feature.niveladquirido;
          textarea.defaultValue = result.feature.descricao;
          form.elements.tags_json_text.defaultValue = (result.feature.tags_json || []).join('\n');
          card.dataset.featureLevel = String(result.feature.niveladquirido);
          if (featureLevel && ![...featureLevel.options].some(option => option.value === card.dataset.featureLevel)) {
            const option = document.createElement('option');
            option.value = card.dataset.featureLevel;
            option.textContent = `NÃ­vel ${result.feature.niveladquirido}`;
            featureLevel.append(option);
          }
          if (featureSearch) featureSearch.value = '';
          if (featureLevel?.value) featureLevel.value = card.dataset.featureLevel;
          applyBaseFeatureVisibility();
          form.classList.remove('is-open');
          edit.setAttribute('aria-expanded', 'false');
          edit.focus();
        } catch (failure) {
          error.textContent = failure.message || 'NÃ£o foi possÃ­vel salvar a habilidade.';
          error.hidden = false;
          error.focus();
        } finally {
          form.removeAttribute('aria-busy');
          controls.forEach(control => { control.disabled = false; });
        }
      });
    });
  }

  // Sidebar Search
  const classSearch = document.getElementById('classSearch');
  const classSearchClear = document.getElementById('classSearchClear');
  const classSearchStatus = document.getElementById('classSearchStatus');
  const classItems = Array.from(document.querySelectorAll('.class-nav-item'));
  const classNav = document.getElementById('classNav');
  const classMenuToggle = document.querySelector('[data-class-menu-toggle]');
  const classMenuClosers = document.querySelectorAll('[data-class-menu-close]');
  let classFilterTimer = null;
  let classRequestId = 0;
  let classRenderedRoute = window.location.pathname + window.location.search;
  let classAttribute = '';
  const classMobile = window.matchMedia('(max-width:1100px)');
  const classSidebar = document.getElementById('classSidebar');

  function setClassMenuOpen(isOpen, restoreFocus = false) {
    isOpen = isOpen && classMobile.matches;
    document.body.classList.toggle('class-menu-open', isOpen);
    classMenuToggle?.setAttribute('aria-expanded', String(isOpen));
    classMenuToggle?.setAttribute('aria-label', isOpen ? 'Fechar lista de classes' : 'Abrir lista de classes');
    if(classSidebar) classSidebar.inert = classMobile.matches && !isOpen;
    document.querySelector('[data-class-main]').inert = isOpen;
    if(isOpen) classSearch?.focus();
    else if(restoreFocus) classMenuToggle?.focus();
  }
  setClassMenuOpen(false);
  classMobile.addEventListener('change', () => setClassMenuOpen(false));
  classMenuToggle?.addEventListener('click', () => setClassMenuOpen(!document.body.classList.contains('class-menu-open')));
  classMenuClosers.forEach(closer => closer.addEventListener('click', () => setClassMenuOpen(false, true)));
  document.addEventListener('keydown', event => {
    if(!document.body.classList.contains('class-menu-open')) return;
    if(event.key === 'Escape') setClassMenuOpen(false, true);
    if(event.key === 'Tab') {
      const controls = [...classSidebar.querySelectorAll('a,button,input,select,summary')].filter(el => el.getClientRects().length && !el.disabled && !el.closest('.hidden'));
      controls.push(classMenuToggle);
      const index = controls.indexOf(document.activeElement);
      event.preventDefault();
      controls[(index + (event.shiftKey ? -1 : 1) + controls.length) % controls.length]?.focus();
    }
  });
  document.addEventListener('click', event => {
    if(event.target.closest('a[href="#class-essentials"]') && document.body.classList.contains('class-menu-open')) setClassMenuOpen(false);
  });
  function bindCatalogControls() {
    const search = document.querySelector('[data-class-catalog-search]');
    if(search) {
      search.value = classSearch.value;
      search.addEventListener('input', () => { classSearch.value = search.value; filterClasses(); });
      search.addEventListener('keydown', event => {
        if(event.key === 'Enter') { const first = classItems.find(item => !item.classList.contains('hidden')); if(first) { event.preventDefault(); first.click(); } }
      });
    }
    document.querySelector('[data-class-catalog-tools]')?.removeAttribute('hidden');
    document.querySelectorAll('[data-class-attribute]').forEach(button => button.addEventListener('click', () => { classAttribute = button.dataset.classAttribute; filterClasses(); }));
    document.querySelector('[data-class-catalog-clear]')?.addEventListener('click', () => { classSearch.value = ''; if(search) search.value = ''; classAttribute = ''; filterClasses(); search?.focus(); });
  }

  function filterClasses() {
    const searchable = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
    const query = searchable((classSearch?.value || '').trim());
    let visibleCount = 0;
    classItems.forEach(item => {
      const text = searchable(item.dataset.search || '');
      const matches = (!query || text.includes(query)) && (!classAttribute || searchable(item.dataset.attribute || '').includes(classAttribute));
      item.classList.toggle('hidden', !matches);
      if (matches) visibleCount += 1;
    });
    const catalogSearch = document.querySelector('[data-class-catalog-search]');
    if(catalogSearch && catalogSearch.value !== classSearch.value) catalogSearch.value = classSearch.value;
    document.querySelectorAll('[data-class-card]').forEach(card => {
      card.hidden = (query && !searchable(card.dataset.search || '').includes(query)) || (classAttribute && !searchable(card.dataset.attribute || '').includes(classAttribute));
    });
    document.querySelectorAll('[data-class-attribute]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.classAttribute === classAttribute)));
    const catalogStatus = document.querySelector('[data-class-catalog-status]');
    if(catalogStatus) catalogStatus.textContent = `${visibleCount} classe${visibleCount === 1 ? '' : 's'}`;
    const empty = document.querySelector('[data-class-catalog-empty]');
    if(empty) empty.hidden = visibleCount > 0;
    classSearchClear?.classList.toggle('hidden', !query);
    if (classSearchStatus) {
      classSearchStatus.textContent = query || classAttribute
        ? (visibleCount ? `${visibleCount} classe${visibleCount === 1 ? '' : 's'} encontrada${visibleCount === 1 ? '' : 's'}.` : 'Nenhuma classe encontrada. Limpe a busca para tentar novamente.')
        : `${visibleCount} classe${visibleCount === 1 ? '' : 's'} disponÃ­ve${visibleCount === 1 ? 'l' : 'is'}.`;
    }
    classNav?.classList.remove('class-nav-filtering');
    void classNav?.offsetWidth;
    classNav?.classList.add('class-nav-filtering');
    if (classFilterTimer) clearTimeout(classFilterTimer);
    classFilterTimer = setTimeout(() => {
      classNav?.classList.remove('class-nav-filtering');
      classFilterTimer = null;
    }, 240);
  }

  classSearch?.addEventListener('input', filterClasses);
  classSearch?.addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    const firstMatch = classItems.find(item => !item.classList.contains('hidden'));
    if (!firstMatch) return;
    event.preventDefault();
    firstMatch.click();
  });
  classSearchClear?.addEventListener('click', () => {
    classSearch.value = '';
    filterClasses();
    classSearch.focus();
  });
  filterClasses();

  // AJAX Loading
  const contentArea = document.querySelector('[data-class-main]');

  document.addEventListener('click', event => {
    const link = event.target.closest('.class-nav-item, [data-class-route]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setClassMenuOpen(false);

    const url = link.href;
    loadContent(url);
  });

  async function loadContent(url, updateHistory = true) {
    const requestId = ++classRequestId;
    contentArea.setAttribute('aria-busy', 'true');
    contentArea.style.opacity = '0.5';
    contentArea.style.pointerEvents = 'none';

    try {
      const destination = new URL(url, window.location.origin);
      const requestUrl = new URL(destination);
      requestUrl.hash = '';
      requestUrl.searchParams.set('ajax', '1');
      const response = await fetch(requestUrl);
      if (!response.ok) throw new Error('Failed to load');

      const html = await response.text();
      if (requestId !== classRequestId) return;
      const temp = document.createElement('div');
      temp.innerHTML = html;

      const newMain = temp.querySelector('#ajax-content-inner');
      if (!newMain) throw new Error('ConteÃºdo de classe indisponÃ­vel.');
      contentArea.replaceChildren(newMain);

      // Update sidebar active state
      classItems.forEach(item => {
          const isActive = new URL(item.href).pathname === destination.pathname;
          item.classList.toggle('border-[var(--flame)]', isActive);
          item.classList.toggle('bg-[var(--flame)]/5', isActive);
          item.classList.toggle('text-[var(--text)]', isActive);
          item.classList.toggle('border-transparent', !isActive);
          item.classList.toggle('text-[var(--muted)]', !isActive);
          if (isActive) item.setAttribute('aria-current', 'page');
          else item.removeAttribute('aria-current');
      });

      if (updateHistory && window.location.href !== url) window.history.pushState({}, '', url);
      initPage();
      const heading = contentArea.querySelector('h1');
      document.title = `${contentArea.querySelector('[data-class-catalog]') ? 'Classes' : heading?.textContent.trim()} Â· Bonfire Tales RPG`;
      if(heading) {
        heading.tabIndex = -1;
        heading.focus({preventScroll:true});
        // Keep the mobile class-list control above the new title. Page changes
        // are immediate; section anchors can still use the site's native scroll.
        document.querySelector('.class-shell').scrollIntoView({block:'start',behavior:'instant'});
      }
    } catch (err) {
      if (requestId !== classRequestId) return;
      console.error(err);
      window.location.href = url; // Fallback to normal load
    } finally {
      if (requestId === classRequestId) {
        contentArea.removeAttribute('aria-busy');
        contentArea.style.opacity = '1';
        contentArea.style.pointerEvents = '';
      }
    }
  }

  window.addEventListener('popstate', () => {
    if(/^\/jogador\/classes(?:\/|$)/.test(window.location.pathname)) {
      // Native section anchors must not replace the page or reset its filters.
      if(window.location.pathname + window.location.search !== classRenderedRoute) loadContent(window.location.href, false);
    }
    else window.location.reload();
  });

  function wikiCookie(name) {
    return document.cookie
      .split('; ')
      .find(row => row.startsWith(`${name}=`))
      ?.split('=')[1] || '';
  }

  // Toggle animation
  function toggleAnimatedDetails(details) {
    const content = details.querySelector('.bonfire-toggle-content');
    if (!content || details.dataset.animating === 'true') return;

    if(matchMedia('(prefers-reduced-motion: reduce)').matches) { details.open = !details.open; return; }
    details.dataset.animating = 'true';
    if (!details.open) {
      details.open = true;
      content.style.maxHeight = '0px';
      content.style.opacity = '0';
      content.style.transform = 'translateY(-12px)';
      requestAnimationFrame(() => {
        content.style.maxHeight = `${content.scrollHeight}px`;
        content.style.opacity = '1';
        content.style.transform = 'translateY(0)';
      });
      setTimeout(() => {
        content.style.maxHeight = 'none';
        content.style.opacity = '';
        content.style.transform = '';
        details.dataset.animating = 'false';
      }, 560);
      return;
    }

    content.style.maxHeight = `${content.scrollHeight}px`;
    content.style.opacity = '1';
    content.style.transform = 'translateY(0)';
    requestAnimationFrame(() => {
      content.style.maxHeight = '0px';
      content.style.opacity = '0';
      content.style.transform = 'translateY(-12px)';
    });
    setTimeout(() => {
      details.open = false;
      content.style.maxHeight = '';
      content.style.opacity = '';
      content.style.transform = '';
      details.dataset.animating = 'false';
    }, 560);
  }

  document.addEventListener('click', event => {
    const summary = event.target.closest('.bonfire-toggle > summary');
    if (!summary) return;
    const details = summary.parentElement;
    if (!details || !details.classList.contains('bonfire-toggle')) return;
    event.preventDefault();
    toggleAnimatedDetails(details);
  });

  initPage();
})();
