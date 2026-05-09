

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
        const img = `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}"${classAttr}${styleAttr}>`;
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
        output = output.replace(/::options=([^\n\r]+)/gi, (_match, tipo) => {
            const tipoClean = tipo.trim();
            return `<div class="bonfire-options-widget" data-tipo="${tipoClean}"><span class="bonfire-options-loading">Carregando opcoes de <strong>${tipoClean}</strong>...</span></div>`;
        });
    }

    return output;
}

function buildBonfireMarkdownSource(value, options = {}) {
    const source = normalizeMarkdown(value, options);
    return source.replace(/::(?:click|toggle)\s+([^\n]+)\n([\s\S]*?)\n::end(?:click|toggle)/gi, (_match, title, content) => {
        const innerHtml = renderBonfireMarkdown(content, options);
        return `<details class="bonfire-toggle"><summary>${parseInlineMarkdown(title.trim())}</summary><div class="bonfire-toggle-content">${innerHtml}</div></details>`;
    });
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
    return applyMarkdownColorsToHtml(escapeHtml(source)).replace(/\n/g, '<br>');
}

function renderBonfireMarkdownElement(element, rawValue, options = {}) {
    if (!element) return;
    const raw = rawValue ?? element.dataset.markdownRaw ?? element.textContent;
    const mergedOptions = {
        ...options,
        enableOptions: element.dataset.markdownOptions === 'false' ? false : options.enableOptions
    };
    element.dataset.markdownRaw = raw;
    element.innerHTML = renderBonfireMarkdown(raw, mergedOptions);
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
        renderBonfireMarkdownElement,
        renderBonfireMarkdownElements
    };
}