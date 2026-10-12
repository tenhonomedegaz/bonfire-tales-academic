

const markdownColorAliases = {
    red: 'red',
    blue: 'blue',
    green: 'green',
    cyan: 'aqua',
    aqua: 'aqua',
    yellow: 'yellow',
    gold: 'gold',
    purple: 'light-purple',
    'light-purple': 'light-purple',
    'dark-blue': 'dark-blue',
    'dark-green': 'dark-green',
    'dark-aqua': 'dark-aqua',
    'dark-cyan': 'dark-aqua',
    'dark-red': 'dark-red',
    'dark-purple': 'dark-purple',
    black: 'black',
    white: 'white',
    gray: 'gray',
    grey: 'gray',
    'dark-gray': 'dark-gray',
    ember: 'ember',
    flame: 'flame',
    spark: 'spark',
    muted: 'muted',
    page: 'page'
};

const bonfireMarkdownColorOptions = [
    { name: 'red', value: 'red', swatch: '#ef4444' },
    { name: 'blue', value: 'blue', swatch: '#60a5fa' },
    { name: 'cyan', value: 'cyan', swatch: '#22d3ee' },
    { name: 'green', value: 'green', swatch: '#22c55e' },
    { name: 'yellow', value: 'yellow', swatch: '#facc15' },
    { name: 'gold', value: 'gold', swatch: '#f59e0b' },
    { name: 'purple', value: 'purple', swatch: '#c084fc' },
    { name: 'dark-blue', value: 'dark-blue', swatch: '#2563eb' },
    { name: 'dark-green', value: 'dark-green', swatch: '#16a34a' },
    { name: 'dark-cyan', value: 'dark-cyan', swatch: '#0891b2' },
    { name: 'dark-red', value: 'dark-red', swatch: '#dc2626' },
    { name: 'dark-purple', value: 'dark-purple', swatch: '#9333ea' },
    { name: 'white', value: 'white', swatch: '#ffffff' },
    { name: 'gray', value: 'gray', swatch: '#9ca3af' },
    { name: 'dark-gray', value: 'dark-gray', swatch: '#6b7280' },
    { name: 'black', value: 'black', swatch: '#111827' },
    { name: 'ember', value: 'ember', swatch: '#f27007' },
    { name: 'flame', value: 'flame', swatch: '#d21717' },
    { name: 'spark', value: 'spark', swatch: '#f7b113' },
    { name: 'muted', value: 'muted', swatch: '#a1a1aa' }
];

if (typeof document !== 'undefined' && !document.getElementById('bonfireMarkdownImageStyles')) {
    const style = document.createElement('style');
    style.id = 'bonfireMarkdownImageStyles';
    style.textContent = `
        .bonfire-markdown,.markdown-preview,.editor-preview{position:relative;max-width:100%;overflow-wrap:anywhere;word-break:break-word}
        .bonfire-markdown::after,.markdown-preview::after,.editor-preview::after{content:"";display:block;clear:both}
        .bonfire-markdown ul,.markdown-preview ul,.editor-preview ul{list-style:disc outside;padding-left:1.45rem;margin:.55rem 0 .85rem}
        .bonfire-markdown ul ul,.markdown-preview ul ul,.editor-preview ul ul{list-style:circle outside;margin:.3rem 0 .35rem}
        .bonfire-markdown ol,.markdown-preview ol,.editor-preview ol{list-style:decimal outside;padding-left:1.45rem;margin:.55rem 0 .85rem}
        .bonfire-markdown li,.markdown-preview li,.editor-preview li{display:list-item;margin:.18rem 0}
        .bonfire-md-image{max-width:100%;height:auto;border-radius:4px}
        .bonfire-md-image-box{clear:both;display:flex;gap:1rem;margin:.75rem 0;max-width:100%;min-width:0;overflow:hidden;position:relative;width:100%}
        .bonfire-md-image-box-right{justify-content:flex-end}
        .bonfire-md-image-box-left{justify-content:flex-start}
        .bonfire-md-image-box-center{justify-content:center}
        .bonfire-md-image-box-inline{clear:none;display:inline-flex;margin:.15rem .35rem;vertical-align:middle;width:auto}
        .bonfire-md-image-float-right{float:right;margin:0 0 1rem 1rem}
        .bonfire-md-image-float-left{float:left;margin:0 1rem 1rem 0}
        .bonfire-md-image-inline{display:inline-block;margin:.15rem .35rem;vertical-align:middle}
        .bonfire-md-image-break{display:block;margin-top:.75rem;margin-bottom:.75rem}
        .bonfire-md-image-no-break{display:inline-block}
        .bonfire-md-image-align-upper{vertical-align:top}
        .bonfire-md-image-align-middle{vertical-align:middle}
        .bonfire-md-image-align-lower{vertical-align:bottom}
        .bonfire-md-image-layer-front{position:relative;z-index:3}
        .bonfire-md-image-layer-same{position:relative;z-index:1}
        .bonfire-md-image-layer-back{position:relative;z-index:0}
        .bonfire-md-text-over-image{position:relative;z-index:2}
        .bonfire-color-menu{position:fixed;z-index:10000;width:260px;background:#101012;border:1px solid #27272a;border-radius:8px;box-shadow:0 18px 45px rgba(0,0,0,.45);padding:.65rem;color:#ededed}
        .bonfire-color-menu-title{font-size:.68rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#a1a1aa;margin:0 0 .5rem}
        .bonfire-color-menu-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem}
        .bonfire-color-menu button{align-items:center;background:#18181b;border:1px solid #27272a;border-radius:5px;color:#ededed;cursor:pointer;display:flex;font-size:.72rem;font-weight:800;gap:.45rem;padding:.45rem .5rem;text-align:left}
        .bonfire-color-menu button:hover{border-color:#f27007;color:#f27007}
        .bonfire-color-swatch{border:1px solid rgba(255,255,255,.35);border-radius:999px;display:inline-block;flex:0 0 auto;height:14px;width:14px}
        .bonfire-color-menu-custom{border-top:1px solid #27272a;display:grid;gap:.45rem;grid-template-columns:auto 1fr;margin-top:.55rem;padding-top:.55rem}
        .bonfire-color-menu-custom input[type="color"]{background:#18181b;border:1px solid #27272a;border-radius:5px;height:34px;padding:2px;width:48px}
        .bonfire-color-menu-custom button{justify-content:center}
    `;
    document.head.appendChild(style);
}

function escapeHtml(unsafe) {
    return String(unsafe || '')
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function markdownColorClass(value) {
    const key = String(value || '').trim().toLowerCase().replace(/_/g, '-');
    const color = markdownColorAliases[key];
    return color ? `bonfire-color-${color}` : '';
}

function markdownColorStyle(value) {
    const color = String(value || '').trim();
    return /^#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(color) ? `color:${color}` : '';
}

function applyMarkdownColorsToHtml(value) {
    return String(value || '').replace(/\[color=(#[0-9a-f]{3}|#[0-9a-f]{6}|#[0-9a-f]{8}|[a-z][a-z0-9_-]*)\]([\s\S]*?)\[\/color\]/gi, (_match, color, content) => {
        const colorClass = markdownColorClass(color);
        if (colorClass) return `<span class="${colorClass}">${content}</span>`;
        const colorStyle = markdownColorStyle(color);
        return colorStyle ? `<span style="${colorStyle}">${content}</span>` : content;
    });
}

function parseInlineMarkdown(value) {
    return applyMarkdownColorsToHtml(escapeHtml(value))
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

function bonfireImageStyleFromModifiers(modifiers) {
    const allowed = new Set([
        'position', 'bottom', 'top', 'left', 'right', 'width', 'height', 'max-width', 'max-height',
        'min-width', 'min-height', 'z-index', 'float', 'clear', 'display', 'margin', 'margin-top',
        'margin-right', 'margin-bottom', 'margin-left', 'object-fit', 'object-position',
        'vertical-align', 'opacity'
    ]);
    const aliases = {
        length: 'width',
        len: 'width',
        largura: 'width',
        comprimento: 'width',
        zindex: 'z-index',
        z: 'z-index',
        align: 'vertical-align',
        alinhamento: 'vertical-align',
        valign: 'vertical-align',
        'break-line': 'break',
        quebra: 'break'
    };
    const classNames = ['bonfire-md-image'];
    const styles = [];
    const meta = {
        breakLine: false,
        side: '',
        inline: false
    };

    String(modifiers || '').split(',').forEach(part => {
        const [rawKey, ...rawValue] = part.split(':');
        if (!rawKey || rawValue.length === 0) return;
        const key = rawKey.trim().toLowerCase().replace(/_/g, '-');
        const value = rawValue.join(':').trim().replace(/[;"<>]/g, '');
        if (!value) return;
        const normalizedValue = value.toLowerCase();
        const cssKey = aliases[key] || key;

        if (key === 'position') {
            if (['left', 'right'].includes(normalizedValue)) {
                styles.push(`float:${normalizedValue}`);
                styles.push(normalizedValue === 'left' ? 'margin: 0.5rem 1.5rem 1.5rem 0' : 'margin: 0.5rem 0 1.5rem 1.5rem');
                classNames.push(`bonfire-md-image-float-${normalizedValue}`);
                meta.side = normalizedValue;
            } else if (['center', 'centre', 'centro'].includes(normalizedValue)) {
                styles.push('display:block', 'margin-left:auto', 'margin-right:auto');
                meta.side = 'center';
            } else if (['inline', 'line'].includes(normalizedValue)) {
                styles.push('display:inline-block');
                classNames.push('bonfire-md-image-inline');
                meta.inline = true;
            } else if (['front', 'frente'].includes(normalizedValue)) {
                styles.push('position:relative', 'z-index:3');
                classNames.push('bonfire-md-image-layer-front');
            } else if (['back', 'atras', 'behind'].includes(normalizedValue)) {
                styles.push('position:relative', 'z-index:0');
                classNames.push('bonfire-md-image-layer-back');
            } else if (['absolute', 'relative', 'static'].includes(normalizedValue)) {
                styles.push(`position:${normalizedValue}`);
            }
            return;
        }

        if (key === 'layer') {
            if (['front', 'frente', 'above', 'over'].includes(normalizedValue)) {
                classNames.push('bonfire-md-image-layer-front');
            } else if (['back', 'atras', 'behind', 'under'].includes(normalizedValue)) {
                classNames.push('bonfire-md-image-layer-back');
            } else if (['same', 'mesmo', 'texto'].includes(normalizedValue)) {
                classNames.push('bonfire-md-image-layer-same');
            }
            return;
        }

        if (cssKey === 'break') {
            classNames.push(normalizedValue === 'true' ? 'bonfire-md-image-break' : 'bonfire-md-image-no-break');
            meta.breakLine = normalizedValue === 'true';
            return;
        }

        if (cssKey === 'vertical-align') {
            if (['upper', 'top', 'superior', 'upper-margin'].includes(normalizedValue)) {
                styles.push('vertical-align:top');
                classNames.push('bonfire-md-image-align-upper');
            } else if (['middle', 'center', 'meio'].includes(normalizedValue)) {
                styles.push('vertical-align:middle');
                classNames.push('bonfire-md-image-align-middle');
            } else if (['lower', 'bottom', 'inferior', 'lower-margin'].includes(normalizedValue)) {
                styles.push('vertical-align:bottom');
                classNames.push('bonfire-md-image-align-lower');
            } else {
                styles.push(`vertical-align:${value}`);
            }
            return;
        }

        if (key === 'text' || key === 'text-wrap') {
            classNames.push(normalizedValue === 'behind' ? 'bonfire-md-text-over-image' : `bonfire-md-text-${normalizedValue}`);
            return;
        }

        if (key === 'legenda') {
            meta.legenda = normalizedValue === 'true';
            return;
        }

        if (allowed.has(cssKey)) styles.push(`${cssKey}:${value}`);
    });

    return {
        className: classNames.join(' '),
        style: styles.join(';'),
        styles,
        meta
    };
}

function safeImageStyleForLayout(image) {
    if (!image.meta.breakLine) return image.style;
    return image.styles
        .filter(style => !/^(position|float|left|right|top|bottom|clear)\s*:/i.test(style))
        .join(';');
}

function applyBonfireImageModifiers(value) {
    return String(value || '').replace(/(!?)\[([^\]]*)\]\(([^)\s]+(?:\s+"[^"]*")?)\)\s*\{([^}]*)\}/g, (_match, bang, alt, src, modifiers) => {
        const url = src.replace(/\s+"[^"]*"$/, '').trim();
        const image = bonfireImageStyleFromModifiers(modifiers);
        const imageStyle = safeImageStyleForLayout(image);
        const styleAttr = imageStyle ? ` style="${escapeHtml(imageStyle)}"` : '';
        const classAttr = ` class="${escapeHtml(image.className)}"`;
        
        let img;
        if (image.meta.legenda && alt) {
            const figureClass = image.className ? ` class="${escapeHtml(image.className)} bonfire-md-image-container"` : ` class="bonfire-md-image-container"`;
            img = `<figure${figureClass}${styleAttr}><img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" style="width: 100%; height: auto; margin: 0;"><figcaption class="bonfire-md-image-caption">${escapeHtml(alt)}</figcaption></figure>`;
        } else {
            img = `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}"${classAttr}${styleAttr}>`;
        }

        if (image.meta.breakLine) {
            const side = image.meta.inline ? 'inline' : (image.meta.side || 'center');
            return `\n\n<div class="bonfire-md-image-box bonfire-md-image-box-${escapeHtml(side)}">${img}</div>\n\n`;
        }
        return img;
    });
}

function normalizeBonfireBulletLines(value) {
    return String(value || '').split('\n').map(line => {
        const subBullet = line.match(/^\s*--\s*(.*)$/);
        if (subBullet) return `  - ${subBullet[1].trimStart()}`;

        const doubleBullet = line.match(/^\s*-\s+-\s*(.*)$/);
        if (doubleBullet) return `  - ${doubleBullet[1].trimStart()}`;

        return line.replace(/^(\s*)-([^\s\-\+\*])/, '$1- $2');
    }).join('\n');
}

function insertBonfireColor(textarea, color) {
    if (!textarea || !color) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = textarea.value.substring(start, end);
    const prefix = `[color=${color}]`;
    const suffix = '[/color]';
    const replacement = prefix + selectedText + suffix;
    textarea.value = textarea.value.substring(0, start) + replacement + textarea.value.substring(end);
    textarea.selectionStart = start + prefix.length;
    textarea.selectionEnd = start + prefix.length + selectedText.length;
    textarea.focus();
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
}

function closeBonfireColorMenu() {
    const existing = document.getElementById('bonfireColorMenu');
    if (existing) existing.remove();
}

function openBonfireColorMenu(anchor, textarea) {
    if (typeof document === 'undefined' || !anchor || !textarea) return;
    closeBonfireColorMenu();

    const menu = document.createElement('div');
    menu.id = 'bonfireColorMenu';
    menu.className = 'bonfire-color-menu';
    menu.innerHTML = `
        <p class="bonfire-color-menu-title">Cores predefinidas</p>
        <div class="bonfire-color-menu-grid">
            ${bonfireMarkdownColorOptions.map(color => `
                <button type="button" data-color="${escapeHtml(color.value)}">
                    <span class="bonfire-color-swatch" style="background:${escapeHtml(color.swatch)}"></span>
                    ${escapeHtml(color.name)}
                </button>
            `).join('')}
            <button type="button" data-color="page">
                <span class="bonfire-color-swatch" style="background:var(--territory-color, var(--ember, #f27007))"></span>
                page
            </button>
        </div>
        <div class="bonfire-color-menu-custom">
            <input type="color" value="#f27007" aria-label="Cor hexadecimal">
            <button type="button" data-hex-apply>Aplicar hex</button>
        </div>
    `;

    menu.addEventListener('click', event => {
        const colorButton = event.target.closest('[data-color]');
        if (colorButton) {
            insertBonfireColor(textarea, colorButton.dataset.color);
            closeBonfireColorMenu();
            return;
        }
        if (event.target.closest('[data-hex-apply]')) {
            const colorInput = menu.querySelector('input[type="color"]');
            insertBonfireColor(textarea, colorInput?.value || '#f27007');
            closeBonfireColorMenu();
        }
    });

    document.body.appendChild(menu);
    const rect = anchor.getBoundingClientRect();
    const left = Math.min(rect.left, window.innerWidth - menu.offsetWidth - 12);
    const top = Math.min(rect.bottom + 8, window.innerHeight - menu.offsetHeight - 12);
    menu.style.left = `${Math.max(12, left)}px`;
    menu.style.top = `${Math.max(12, top)}px`;

    setTimeout(() => {
        const outsideHandler = event => {
            if (!menu.contains(event.target) && event.target !== anchor) {
                closeBonfireColorMenu();
                document.removeEventListener('mousedown', outsideHandler);
            }
        };
        document.addEventListener('mousedown', outsideHandler);
    }, 0);
}

function normalizeMarkdown(value, options = {}) {
    const enableOptions = options.enableOptions !== false;
    let output = applyBonfireImageModifiers(normalizeBonfireBulletLines(String(value || '').replace(/\r\n/g, '\n')))
        .replace(/^\s*---\s*$/gm, '\n\n---\n\n')
        .replace(/(^|[^\!])\[([^\]]*)\]\(([^)]+\.(?:png|jpg|jpeg|gif|webp)(?:\?[^)]*)?)\)/gi, '$1![$2]($3)')
        .replace(/::center\s*\n([\s\S]*?)\n::/g, (_match, content) => {
            const html = content
                .trim()
                .split('\n')
                .map(line => parseInlineMarkdown(line.trim()))
                .join('<br>');
            return `<div class="bonfire-center">${html}</div>`;
        });

    if (enableOptions) {
        output = output.replace(/::(?:options|opcoes)(?:=|\s+)([^\n\r]+)/gi, (_match, config) => {
            const parts = config.split(';');
            const tipoClean = parts[0].trim();
            let attrs = `data-tipo="${tipoClean}"`;
            for (let i = 1; i < parts.length; i++) {
                const part = parts[i].trim();
                if (!part) continue;
                const match = part.match(/^([a-zA-Z0-9_\-]+)[\s=]+(.*)$/);
                if (match) {
                    const key = match[1].toLowerCase();
                    const val = match[2].trim();
                    attrs += ` data-${key}="${val}"`;
                }
            }
            return `<div class="bonfire-options-widget" ${attrs}><span class="bonfire-options-loading">Carregando opcoes de <strong>${tipoClean}</strong>...</span></div>`;
        });
    }

    // Explicit inline creature sheet. Raw creature:slug is not parsed in normal
    // markdown; use ::creature-preview slug where a statblock must be embedded.
    output = output.replace(/::creature-preview\s+([a-z0-9_-]+)/gi, (_match, slug) => {
        const cleanSlug = escapeHtml(slug.toLowerCase());
        return `<div class="bonfire-creature-widget" data-slug="${cleanSlug}"><span class="bonfire-options-loading">Carregando ficha de criatura...</span></div>`;
    });

    // Parse the normal markdown-shaped card form first: [texto](tabela, args).
    // This prevents prose parentheses from being mistaken for legacy card text
    // when the prose contains a card link inside it.
    output = output.replace(/\[([^\]\n]+)\]\(\s*((?:tb[A-Za-z0-9_\s]+)|creature|bestiario|criatura|monster)([^\)]*)\)/gi, (_match, text, table, argsStr) => {
        const args = argsStr.split(',').map(s => s.trim()).filter(Boolean);
        return `<a href="#" class="bonfire-card-trigger" data-table="${escapeHtml(table)}" data-args="${escapeHtml(args.join(','))}">${text}</a>`;
    });

    // Parse preview cards: (texto)[tabela, arg1, arg2) or [texto](tabela, arg1, arg2)
    output = output.replace(/([\[\(])([^\]\)]+)[\]\)]\s*([\[\(])\s*((?:tb[A-Za-z0-9_á-úÁ-Ú\s]+)|creature|bestiario|criatura|monster)([^\]\)]*)[\]\)]/gi, (_match, _o1, text, _o2, table, argsStr) => {
        const args = argsStr.split(',').map(s => s.trim()).filter(Boolean);
        return `<a href="#" class="bonfire-card-trigger" data-table="${escapeHtml(table)}" data-args="${escapeHtml(args.join(','))}">${text}</a>`;
    });

    return output;
}

function slugify(text) {
    if (!text) return '';
    return text.toString().toLowerCase().trim()
        .replace(/\s+/g, '-')
        .replace(/[^\w\-]+/g, '')
        .replace(/\-\-+/g, '-');
}

function parseToggleBlock(content, options = {}) {
    const lines = content.split(/\r?\n/);
    let title = '';
    let introLines = [];
    let subtopics = [];
    let currentSubtopic = null;
    
    for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('# ')) {
            title = trimmed.substring(2).trim();
        } else if (trimmed.startsWith('### ')) {
            if (currentSubtopic) {
                subtopics.push(currentSubtopic);
            }
            const stTitle = trimmed.substring(4).trim();
            currentSubtopic = {
                title: stTitle,
                slug: slugify(stTitle),
                contentLines: []
            };
        } else {
            if (currentSubtopic) {
                currentSubtopic.contentLines.push(line);
            } else {
                introLines.push(line);
            }
        }
    }
    if (currentSubtopic) {
        subtopics.push(currentSubtopic);
    }
    
    // Generate unique ID for this toggle group
    const groupId = 'toggle-' + Math.random().toString(36).substring(2, 9);
    
    // Render intro and subtopics
    const introHtml = renderBonfireMarkdown(introLines.join('\n'), options);
    
    let buttonsHtml = '';
    let panelsHtml = '';
    
    subtopics.forEach((st, idx) => {
        const activeClass = idx === 0 ? 'is-active' : '';
        const visibleClass = idx === 0 ? 'is-visible' : '';
        const stContentHtml = renderBonfireMarkdown(st.contentLines.join('\n'), options);
        
        buttonsHtml += `<button type="button" class="subtopic-btn ${activeClass}" data-group-id="${groupId}" data-subtopic-toggle="${st.slug}">${parseInlineMarkdown(st.title)}</button>`;
        panelsHtml += `<div class="h1-group-panel ${visibleClass}" data-group-parent="${groupId}" data-sub-slug="${st.slug}"><div class="bonfire-markdown"><strong class="subtopic-body-title">${parseInlineMarkdown(st.title)}</strong><br>${stContentHtml}</div></div>`;
    });
    
    return `<div class="h1-section-group mb-12" id="${groupId}"><h1 class="bonfire-h1-lore">${parseInlineMarkdown(title)}</h1><div class="bonfire-markdown mb-6">${introHtml}</div>${subtopics.length > 0 ? `<div class="subtopic-nav mb-6 flex flex-wrap gap-2">${buttonsHtml}</div>` : ''}<div class="h1-group-body">${panelsHtml}</div></div>`;
}

function buildBonfireMarkdownSource(value, options = {}) {
    let source = normalizeMarkdown(value, options);
    
    // Process new ::toggle ... ::endtoggle blocks
    source = source.replace(/::toggle\s*\n([\s\S]*?)\n::endtoggle/gi, (_match, content) => {
        return parseToggleBlock(content, options);
    });

    // Process legacy ::click ... ::endclick blocks (keep ::toggle support for legacy title tag lines)
    return source.replace(/::(?:click|toggle)\s+([^\n]+)\n([\s\S]*?)\n::end(?:click|toggle)/gi, (_match, title, content) => {
        const innerHtml = renderBonfireMarkdown(content, options);
        return `<details class="bonfire-toggle"><summary>${parseInlineMarkdown(title.trim())}</summary><div class="bonfire-toggle-content">${innerHtml}</div></details>`;
    });
}

function sanitizeBonfireMarkdownHtml(html) {
    const source = document.createElement('template');
    source.innerHTML = String(html || '');
    const safeTags = new Set([
        'a', 'b', 'blockquote', 'br', 'button', 'code', 'del', 'details', 'div', 'em', 'h1', 'h2', 'h3',
        'h4', 'h5', 'h6', 'hr', 'img', 'li', 'ol', 'p', 'pre', 's', 'span', 'strong',
        'summary', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
    ]);
    const discardedTags = new Set([
        'base', 'embed', 'form', 'iframe', 'input', 'link', 'math', 'meta',
        'object', 'script', 'style', 'svg', 'template', 'textarea'
    ]);
    const safeUrl = value => {
        try {
            const url = new URL(value, window.location.href);
            return ['http:', 'https:', 'mailto:'].includes(url.protocol) ? value : '';
        } catch (_error) {
            return '';
        }
    };
    const clean = node => {
        if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.textContent);
        if (node.nodeType !== Node.ELEMENT_NODE) return document.createDocumentFragment();
        const tag = node.localName.toLowerCase();
        if (discardedTags.has(tag)) return document.createDocumentFragment();
        const groupId = node.getAttribute('data-group-id') || '';
        const subtopicSlug = node.getAttribute('data-subtopic-toggle') || '';
        const isSubtopicButton = tag === 'button' && node.classList.contains('subtopic-btn') &&
            /^toggle-[a-z0-9]+$/.test(groupId) && /^[a-z0-9-]+$/.test(subtopicSlug);
        if (tag === 'button' && !isSubtopicButton) return document.createDocumentFragment();
        const element = safeTags.has(tag) ? document.createElement(tag) : document.createDocumentFragment();
        if (element.nodeType === Node.ELEMENT_NODE) {
            const classes = [...node.classList].filter(name =>
                /^(?:(?:bonfire|atlas)-[a-z0-9_-]+|md-ref|ab|sc|h1-section-group|h1-group-body|h1-group-panel|subtopic-nav|subtopic-btn|subtopic-body-title|is-active|is-visible)$/.test(name));
            if (classes.length) element.className = classes.join(' ');
            if (isSubtopicButton) {
                element.type = 'button';
                element.setAttribute('data-group-id', groupId);
                element.setAttribute('data-subtopic-toggle', subtopicSlug);
            }
            if (tag === 'div' && classes.includes('h1-section-group') && /^toggle-[a-z0-9]+$/.test(node.id)) {
                element.id = node.id;
            }
            if (tag === 'div' && classes.includes('h1-group-panel') &&
                /^toggle-[a-z0-9]+$/.test(node.getAttribute('data-group-parent') || '') &&
                /^[a-z0-9-]+$/.test(node.getAttribute('data-sub-slug') || '')) {
                element.setAttribute('data-group-parent', node.getAttribute('data-group-parent'));
                element.setAttribute('data-sub-slug', node.getAttribute('data-sub-slug'));
            }
            if (node.hasAttribute('title')) element.title = node.getAttribute('title');
            if (tag === 'a') {
                const href = safeUrl(node.getAttribute('href') || '');
                if (href) element.setAttribute('href', href);
                if (classes.includes('bonfire-card-trigger')) {
                    for (const attr of ['data-table', 'data-args']) {
                        if (node.hasAttribute(attr)) element.setAttribute(attr, node.getAttribute(attr));
                    }
                }
            }
            if (tag === 'img') {
                const src = safeUrl(node.getAttribute('src') || '');
                if (!src || new URL(src, window.location.href).protocol === 'mailto:') return document.createDocumentFragment();
                element.setAttribute('src', src);
                element.alt = node.getAttribute('alt') || '';
                element.loading = 'lazy';
            }
            if (tag === 'div' && classes.includes('bonfire-creature-widget') && node.hasAttribute('data-slug')) {
                element.setAttribute('data-slug', node.getAttribute('data-slug'));
            }
            if (tag === 'div' && classes.includes('bonfire-options-widget') && node.hasAttribute('data-tipo')) {
                for (const attr of ['data-tipo', 'data-classe', 'data-subclasse', 'data-nivel']) {
                    if (node.hasAttribute(attr)) element.setAttribute(attr, node.getAttribute(attr));
                }
            }
            if (tag === 'span' && /^color:#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test((node.getAttribute('style') || '').replace(/\s/g, ''))) {
                element.style.color = node.style.color;
            }
            if ((tag === 'th' || tag === 'td') && /^[1-9]\d?$/.test(node.getAttribute('colspan') || '')) {
                element.setAttribute('colspan', node.getAttribute('colspan'));
            }
        }
        for (const child of node.childNodes) element.appendChild(clean(child));
        return element;
    };
    const result = document.createElement('div');
    for (const child of source.content.childNodes) result.appendChild(clean(child));
    return result.innerHTML;
}

function renderBonfireMarkdown(value, options = {}) {
    const source = buildBonfireMarkdownSource(value, options);
    if (!source) return '';
    if (typeof window !== 'undefined' && window.marked && typeof window.marked.parse === 'function') {
        return applyMarkdownColorsToHtml(window.marked.parse(source, { breaks: true, gfm: true }));
    }
    if (typeof marked !== 'undefined' && marked && typeof marked.parse === 'function') {
        return applyMarkdownColorsToHtml(marked.parse(source, { breaks: true, gfm: true }));
    }
    // Fallback offline: se a CDN do `marked` falhar, formata o subconjunto da ficha.
    // A entrada e escapada antes da formatacao.
    const inline = text => text
        .replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span class="md-ref" title="$2">$1</span>');
    const lines = escapeHtml(source).split(/\r?\n/);
    let html = '', inList = false;
    lines.forEach(line => {
        const item = line.match(/^\s*[-*]\s+(.+)$/);
        if (item) {
            if (!inList) { html += '<ul>'; inList = true; }
            html += '<li>' + inline(item[1]) + '</li>';
            return;
        }
        if (inList) { html += '</ul>'; inList = false; }
        if (!line.trim()) return;
        const heading = line.match(/^(#{1,6})\s+(.+)$/);
        html += heading
            ? '<h' + heading[1].length + '>' + inline(heading[2]) + '</h' + heading[1].length + '>'
            : '<p>' + inline(line) + '</p>';
    });
    if (inList) html += '</ul>';
    return applyMarkdownColorsToHtml(html);
}

/* ═══════════════════════════════════════════════
   Atlas Newspaper Layout Engine
   ═══════════════════════════════════════════════ */

function buildAtlasHeaderHtml(content) {
    const lines = content.split('\n').map(l => l.trim()).filter(Boolean);
    const data = {};
    for (const line of lines) {
        const colonIdx = line.indexOf(':');
        if (colonIdx > 0) {
            const key = line.substring(0, colonIdx).trim().toLowerCase();
            const val = line.substring(colonIdx + 1).trim();
            data[key] = val;
        }
    }
    const numero = data['no'] || data['numero'] || '';
    const dateStr = data['data'] || '';
    const assunto = data['assunto'] || '';
    const preco = data['preço'] || data['preco'] || '';
    const dateHtml = escapeHtml(dateStr).replace(/,\s*/g, ',<br>');

    return '<div class="atlas-header">'
        + '<div class="atlas-header-top">'
        +   '<img src="/static/assets/logo.png" alt="O Atlas" class="atlas-header-logo">'
        +   '<div class="atlas-header-title-block">'
        +     '<div class="atlas-header-title">O Atlas</div>'
        +     '<div class="atlas-header-subtitle">O Jornal Oficial do Reino</div>'
        +   '</div>'
        +   '<div class="atlas-header-date">' + dateHtml + '</div>'
        + '</div>'
        + '<div class="atlas-header-bar">'
        +   '<span>' + escapeHtml(numero) + '</span>'
        +   '<span>Bonfire Tales RPG</span>'
        +   '<span>' + escapeHtml(assunto) + '</span>'
        +   '<span>' + escapeHtml(preco) + '</span>'
        + '</div>'
        + '</div>';
}

function buildAtlasCabecalhoHtml(content) {
    const title = content.trim();
    let sectionHtml = '';
    if (title) {
        sectionHtml = '<div class="atlas-cabecalho-section-title">' + escapeHtml(title) + '</div>';
    }
    return '<div class="atlas-cabecalho">'
        + '<div class="atlas-cabecalho-top">'
        +   '<img src="/static/assets/pena_preta.png" alt="" class="atlas-cabecalho-pena">'
        +   '<div class="atlas-cabecalho-title">O Atlas</div>'
        +   '<img src="/static/assets/pena_preta.png" alt="" class="atlas-cabecalho-pena atlas-cabecalho-pena--right">'
        + '</div>'
        + '<div class="atlas-cabecalho-subtitle">Consciência, verdade e dever</div>'
        + sectionHtml
        + '</div>';
}

function parseAtlasBlocks(text) {
    const blocks = [];
    const lines = text.split('\n');
    let buffer = [];
    let i = 0;

    function flushBuffer() {
        const content = buffer.join('\n').trim();
        if (content) blocks.push({ type: 'content', content: content });
        buffer = [];
    }

    while (i < lines.length) {
        const line = lines[i];
        const trimLine = line.trim();

        if (/^::header$/i.test(trimLine)) {
            flushBuffer();
            const inner = [];
            i++;
            while (i < lines.length && !/^::$/.test(lines[i].trim())) { inner.push(lines[i]); i++; }
            blocks.push({ type: 'header', content: inner.join('\n').trim() });
            i++;
            continue;
        }

        if (/^::cabe[cç]alho$/i.test(trimLine)) {
            flushBuffer();
            const inner = [];
            i++;
            while (i < lines.length && !/^::$/.test(lines[i].trim())) { inner.push(lines[i]); i++; }
            blocks.push({ type: 'cabecalho', content: inner.join('\n').trim() });
            i++;
            continue;
        }

        if (/^::no-column$/i.test(trimLine)) {
            flushBuffer();
            const inner = [];
            i++;
            while (i < lines.length && !/^::$/.test(lines[i].trim())) { inner.push(lines[i]); i++; }
            blocks.push({ type: 'no-column', content: inner.join('\n').trim() });
            i++;
            continue;
        }

        if (/^\s*----\s*$/.test(line)) {
            flushBuffer();
            blocks.push({ type: 'separator' });
            i++;
            continue;
        }

        buffer.push(line);
        i++;
    }
    flushBuffer();
    return blocks;
}

function renderAtlasLayout(rawValue, options) {
    options = options || {};
    const text = String(rawValue || '').replace(/\r\n/g, '\n');
    const blocks = parseAtlasBlocks(text);
    let html = '';
    let inColumns = false;

    for (let b = 0; b < blocks.length; b++) {
        var block = blocks[b];
        switch (block.type) {
            case 'header':
                if (inColumns) { html += '</div>'; inColumns = false; }
                html += buildAtlasHeaderHtml(block.content);
                break;
            case 'cabecalho':
                if (inColumns) { html += '</div>'; inColumns = false; }
                html += buildAtlasCabecalhoHtml(block.content);
                break;
            case 'separator':
                if (inColumns) { html += '</div>'; inColumns = false; }
                html += '<hr class="atlas-separator">';
                break;
            case 'no-column':
                if (inColumns) { html += '</div>'; inColumns = false; }
                var ncHtml = renderBonfireMarkdown(block.content, options);
                html += '<div class="atlas-no-column">' + ncHtml + '</div>';
                break;
            case 'content':
                if (!inColumns) { html += '<div class="atlas-columns">'; inColumns = true; }
                var contentMd = block.content.replace(/^\/column\s*$/gm, '\n\n<div class="atlas-column-break"></div>\n\n');
                html += renderBonfireMarkdown(contentMd, options);
                break;
        }
    }
    if (inColumns) html += '</div>';
    return html;
}

function renderBonfireMarkdownElement(element, rawValue, options = {}) {
    if (!element) return;
    const raw = (rawValue ?? element.dataset.markdownRaw ?? element.textContent).trim();
    const mergedOptions = {
        ...options,
        enableOptions: element.dataset.markdownOptions === 'false' ? false : options.enableOptions
    };
    element.dataset.markdownRaw = raw;

    if (element.dataset.atlasMode === 'true') {
        element.innerHTML = sanitizeBonfireMarkdownHtml(renderAtlasLayout(raw, mergedOptions));
    } else {
        element.innerHTML = sanitizeBonfireMarkdownHtml(renderBonfireMarkdown(raw, mergedOptions));
    }
    element.dataset.markdownRendered = 'true';
}

function renderBonfireMarkdownElements(root = document, selector = '[data-markdown-source]', options = {}) {
    if (!root || typeof root.querySelectorAll !== 'function') return;
    root.querySelectorAll(selector).forEach(element => {
        if (element.dataset.markdownManual === 'true') return;
        renderBonfireMarkdownElement(element, undefined, options);
    });
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        renderBonfireMarkdownElements(document);

        // Add global handler for subtopic-btn (used in ::toggle and regions)
        document.addEventListener('click', (e) => {
            const subtopicBtn = e.target.closest('[data-subtopic-toggle]');
            if (subtopicBtn) {
                const slug = subtopicBtn.dataset.subtopicToggle;
                const groupId = subtopicBtn.dataset.groupId;
                const container = subtopicBtn.closest('.h1-section-group') || document.getElementById(groupId);
                if (container) {
                    container.querySelectorAll('.subtopic-btn').forEach(b => b.classList.toggle('is-active', b === subtopicBtn));
                    container.querySelectorAll('.h1-group-panel').forEach(s => s.classList.toggle('is-visible', s.dataset.subSlug === slug));
                }
            }
        });
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        applyMarkdownColorsToHtml,
        parseInlineMarkdown,
        markdownColorClass,
        markdownColorStyle,
        escapeHtml,
        applyBonfireImageModifiers,
        normalizeBonfireBulletLines,
        insertBonfireColor,
        openBonfireColorMenu,
        normalizeMarkdown,
        buildBonfireMarkdownSource,
        renderBonfireMarkdown,
        sanitizeBonfireMarkdownHtml,
        renderAtlasLayout,
        renderBonfireMarkdownElement,
        renderBonfireMarkdownElements
    };
}
