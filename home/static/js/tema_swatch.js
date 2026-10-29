/* =====================================================================
   tema_swatch.js — aplicação CLIENT-SIDE do tema escolhido no cartão-prévia.

   Pedido do PO: "ao escolher muda em tempo real". Este módulo lê os data-*
   que `tema_swatch_card.html` já emite (vindos de TbCosmetico.definicao_json,
   sanitizados server-side) e pinta o alvo NA HORA, sem round-trip.

   ESPELHO DO BACKEND: as vars emitidas aqui são exatamente as de
   `_theme_vars_style` (views.py) — os DOIS namespaces (--profile-* e
   --sheet-*), com o accent virando linear-gradient quando `gradiente` é true,
   e o *-solid mantendo a cor chapada. Se um dia o builder mudar, muda nos dois.

   NADA É PERSISTIDO: isto é só pintura. O que vale é o POST do formulário
   (mesmo name/value de sempre). Recarregar a página volta ao estado salvo.

   Limite conhecido: o <link> do CSS avançado do tema (TbCosmetico.css_file)
   não é trocado aqui — no perfil quem faz isso é a prévia viva pelo servidor
   (perfil_preview_view); na ficha ele só entra depois de salvar.
   ===================================================================== */
(function (global) {
    'use strict';

    var PREFIXO_TEMA = 'theme-';
    var MOTIFS = ['none', 'facets', 'runes', 'sun', 'leaves', 'flames',
                  'thorns', 'crystal', 'moon', 'eclipse', 'bats'];
    function motifValue(value) {
        return MOTIFS.indexOf(value) !== -1 ? value : 'none';
    }
    var PILOT_COMPOSITIONS = {
        'forja-de-brasas': 'collection-forja-de-brasas',
        'aurora-glacial': 'collection-aurora-glacial',
        'circulo-arcano': 'collection-circulo-arcano'
    };
    // Catalog tokens identify skins on initial server roots and subsequent swaps.
    var knownThemeClasses = new Set();
    function classTokens(value) {
        var tokens = typeof value === 'string' ? value.trim().split(/\s+/).filter(Boolean) : [];
        return tokens.every(function (name) { return /^[A-Za-z_][A-Za-z0-9_-]*$/.test(name); })
            ? Array.from(new Set(tokens)) : [];
    }
    function rememberThemeClasses(value) {
        classTokens(value).forEach(function (name) { knownThemeClasses.add(name); });
    }
    function isThemeClass(name) {
        return name.indexOf(PREFIXO_TEMA) === 0 || name.indexOf('collection-') === 0 ||
            knownThemeClasses.has(name);
    }
    function readCatalogClasses() {
        if (typeof document === 'undefined') return;
        document.querySelectorAll('[data-tema-card][data-tema-classe]').forEach(function (card) {
            rememberThemeClasses(card.dataset.temaClasse);
        });
    }

    /* Lê o cartão-prévia dono de um elemento (o próprio radio serve).
       Devolve null quando não há cartão (defensivo: seletor antigo/ausente). */
    function leCartao(el) {
        var card = (el && el.closest) ? el.closest('[data-tema-card]') : null;
        if (!card) return null;
        var d = card.dataset;
        return {
            chave: d.temaCard || '',
            classe: d.temaClasse || '',
            accent: d.accent || '',
            accent2: d.accent2 || '',
            surface: d.surface || '',
            deep: d.deep || '',
            gradiente: d.gradiente === '1',
            particula: d.particula || '',
            vel: d.vel || '',
            motif: motifValue(d.motif)
        };
    }

    /* Cartão marcado dentro de um container (a grade de temas). */
    function cartaoMarcado(container, name) {
        if (!container) return null;
        var radio = container.querySelector('input[name="' + name + '"]:checked');
        return radio ? leCartao(radio) : null;
    }

    /* Mesmo mapa de vars do `_theme_vars_style` do backend. */
    function varsDe(t) {
        var accent = t.gradiente
            ? 'linear-gradient(120deg, ' + t.accent + ', ' + t.accent2 + ')'
            : t.accent;
        return {
            '--profile-accent': accent, '--sheet-accent': accent,
            '--profile-accent-solid': t.accent, '--sheet-accent-solid': t.accent,
            '--profile-accent-2': t.accent2, '--sheet-accent-2': t.accent2,
            '--profile-surface': t.surface, '--sheet-surface': t.surface,
            '--profile-deep': t.deep, '--sheet-deep': t.deep
        };
    }

    /* Troca a classe de tema do alvo preservando todas as outras
       (effect-*, ficha-has-bg, profile-has-bg, utilitárias do Tailwind...). */
    function trocaClasseTema(alvo, classe) {
        readCatalogClasses();
        var mantidas = String(alvo.className).split(/\s+/).filter(function (c) {
            return c && !isThemeClass(c);
        });
        rememberThemeClasses(classe);
        if (classe) mantidas.push(classe);
        alvo.className = mantidas.join(' ');
    }

    /* Pinta o alvo com o tema `t`. Espelha a decisão do `_appearance_context`:
       tema-dado → classe neutra 'theme-data' + vars; 'custom' → 'theme-custom'
       + vars; legado (sem definição) → classe legada e NENHUMA var inline. */
    function aplica(alvo, t) {
        if (!alvo || !t) return;
        var classe = t.accent ? (t.chave === 'custom' ? 'theme-custom' : 'theme-data')
                              : t.classe;
        if (t.accent && classe === 'theme-data' &&
                Object.prototype.hasOwnProperty.call(PILOT_COMPOSITIONS, t.chave)) {
            classe += ' ' + PILOT_COMPOSITIONS[t.chave];
        }
        if (t.accent && t.chave !== 'custom') {
            classe = Array.from(new Set(classTokens(classe).concat(classTokens(t.classe)))).join(' ');
        } else {
            classe = classTokens(classe).join(' ');
        }
        trocaClasseTema(alvo, classe);
        alvo.setAttribute('data-theme-motif', t.accent && t.chave !== 'custom'
                          ? motifValue(t.motif) : 'none');
        var v = varsDe(t);
        Object.keys(v).forEach(function (k) {
            if (t.accent) alvo.style.setProperty(k, v[k]);
            else alvo.style.removeProperty(k);
        });
        // Contrato data-fx-* das partículas (perfil-fx.css).
        if (t.accent && t.particula) {
            alvo.setAttribute('data-fx-particula', t.particula);
            alvo.setAttribute('data-fx-vel', t.vel || 'media');
        } else {
            alvo.removeAttribute('data-fx-particula');
            alvo.removeAttribute('data-fx-vel');
        }
    }

    /* Cartão 'custom' não tem definicao_json: as cores são as dos <input
       type=color> do formulário, lidas AO VIVO. */
    function comCoresDoFormulario(t, inputs) {
        if (!t || t.chave !== 'custom' || !inputs || !inputs.accent) return t;
        return {
            chave: t.chave, classe: t.classe,
            accent: inputs.accent.value,
            accent2: inputs.accent2 ? inputs.accent2.value : t.accent2,
            surface: inputs.surface ? inputs.surface.value : t.surface,
            deep: inputs.deep ? inputs.deep.value : t.deep,
            gradiente: !!(inputs.gradiente && inputs.gradiente.checked),
            particula: t.particula || 'subir',
            vel: t.vel || 'media',
            motif: 'none'
        };
    }

    /* Call only with the server-authorized preview, after its renderer mounts. */
    function syncAuthorizedPreview(source, target) {
        if (!source || !target) return;
        function classes(from, to, accepts) {
            Array.from(to.classList).forEach(function (name) {
                if (accepts(name)) to.classList.remove(name);
            });
            Array.from(from.classList).forEach(function (name) {
                if (accepts(name)) to.classList.add(name);
            });
        }
        function variables(from, to, names) {
            names.forEach(function (name) {
                var value = from.style.getPropertyValue(name);
                if (value) to.style.setProperty(name, value);
                else to.style.removeProperty(name);
            });
        }
        function layers(from, to) {
            if (!from || !to) return;
            Array.from(to.children).forEach(function (child) {
                if (child.matches('[data-cosmetic-layers]')) child.remove();
            });
            Array.from(from.children).forEach(function (child) {
                if (!child.matches('[data-cosmetic-layers]')) return;
                var clone = child.cloneNode(true);
                clone.classList.add('is-visible');
                to.appendChild(clone);
            });
        }
        readCatalogClasses();
        classes(source, target, function (name) { return isThemeClass(name) || /^effect-/.test(name); });
        ['data-theme-motif', 'data-fx-particula', 'data-fx-vel'].forEach(function (name) {
            if (source.hasAttribute(name)) target.setAttribute(name, source.getAttribute(name));
            else target.removeAttribute(name);
        });
        variables(source, target, Object.keys(varsDe({})));
        var fromAvatar = source.querySelector('.public-profile-avatar');
        var toAvatar = target.querySelector('#profile-avatar-main');
        if (fromAvatar && toAvatar) {
            classes(fromAvatar, toAvatar, function (name) {
                return /^frame-/.test(name) || name === 'is-packaged' || name === 'has-calibrated-portrait';
            });
            variables(fromAvatar, toAvatar, ['--portrait-x', '--portrait-y', '--portrait-size']);
            layers(fromAvatar, toAvatar);
        }
        layers(source.querySelector('.public-profile-banner'), target.querySelector('.profile-header'));
        if (global.CosmeticRenderer && global.CosmeticRenderer.mount) {
            global.CosmeticRenderer.mount(target);
        }
    }

    global.TemaSwatch = {
        leCartao: leCartao,
        cartaoMarcado: cartaoMarcado,
        varsDe: varsDe,
        aplica: aplica,
        comCoresDoFormulario: comCoresDoFormulario,
        syncAuthorizedPreview: syncAuthorizedPreview
    };
})(window);
