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
    var PILOT_COMPOSITIONS = {
        'forja-de-brasas': 'collection-forja-de-brasas',
        'aurora-glacial': 'collection-aurora-glacial',
        'circulo-arcano': 'collection-circulo-arcano'
    };

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
            vel: d.vel || ''
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
        var mantidas = String(alvo.className).split(/\s+/).filter(function (c) {
            return c && c.indexOf(PREFIXO_TEMA) !== 0 && c.indexOf('collection-') !== 0;
        });
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
        trocaClasseTema(alvo, classe);
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
            vel: t.vel || 'media'
        };
    }

    global.TemaSwatch = {
        leCartao: leCartao,
        cartaoMarcado: cartaoMarcado,
        varsDe: varsDe,
        aplica: aplica,
        comCoresDoFormulario: comCoresDoFormulario
    };
})(window);
