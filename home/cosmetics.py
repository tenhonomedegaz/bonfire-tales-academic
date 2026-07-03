# -*- coding: utf-8 -*-
"""Catálogo de cosméticos (F1) — carregamento com cache + validação por posse.

Fonte de verdade: TbCosmetico (catálogo em banco) + TbUsuarioCosmetico (inventário).
Substitui os dicts hardcoded APPEARANCE_* de views.py (que viraram seed do catálogo).

Contrato mantido idêntico ao antigo (`_appearance_choice`/`_appearance_context`):
como TODOS os cosméticos do seed são origem='livre', a validação por posse devolve
os mesmos resultados de antes — zero mudança visual. O gate real (cadeados/preços)
entra em fases posteriores (F4).

Ver docs/agentes/arquitetura_personalizacao_perfil.md §4.
"""
from django.core.cache import cache

# Mapeia o "tipo interno" de aparência (usado por perfil/ficha) para o `tipo` do
# catálogo. Permite falar a mesma língua dos helpers antigos (theme/frame/effect).
APPEARANCE_TIPO = {
    'theme': 'tema',
    'frame': 'moldura',
    'effect': 'efeito',
}

_CACHE_TTL = 60  # segundos — TTL curto; invalida no save/delete do admin (signal).
_CACHE_PREFIX = 'cosmeticos:catalogo:'


def _cache_key(tipo):
    return _CACHE_PREFIX + tipo


def invalidate_cosmetic_cache():
    """Chamada pelo signal post_save/post_delete de TbCosmetico (admin-save)."""
    for tipo in ('tema', 'moldura', 'efeito', 'titulo', 'badge', 'banner_preset'):
        cache.delete(_cache_key(tipo))


def _valor_de_slug(tipo, slug):
    """Recupera o VALOR bruto (o que perfil/ficha guardam) a partir do slug global
    prefixado pelo tipo. 'moldura-verdant' → 'verdant'; 'efeito-none' → 'none'.
    Se o slug não vier prefixado (cosmético cadastrado à mão), usa o slug como está."""
    prefixo = tipo + '-'
    return slug[len(prefixo):] if slug.startswith(prefixo) else slug


def get_catalog(tipo):
    """Retorna o catálogo ATIVO de um `tipo` como dict {valor: {campos...}},
    já ordenado por (ordem, nome). A chave é o VALOR bruto que perfil/ficha
    armazenam (não o slug global prefixado). Cacheado por TTL curto.

    Cada valor traz os campos que os templates/validação precisam:
    slug, label, class, raridade, animado, asset_url, origem, preco, requer_plano,
    escopo, descricao.
    """
    key = _cache_key(tipo)
    cached = cache.get(key)
    if cached is not None:
        return cached
    from .models import TbCosmetico
    catalogo = {}
    qs = (TbCosmetico.objects.filter(tipo=tipo, ativo=True)
          .order_by('ordem', 'nome'))
    for c in qs:
        valor = _valor_de_slug(tipo, c.slug)
        catalogo[valor] = {
            'slug': c.slug,
            'label': c.nome,
            'class': c.css_class,
            'raridade': c.raridade,
            'animado': c.animado,
            'asset_url': c.asset_url,
            'origem': c.origem,
            'preco': c.preco,
            'requer_plano': c.requer_plano,
            'escopo': c.escopo,
            'descricao': c.descricao,
        }
    cache.set(key, catalogo, _CACHE_TTL)
    return catalogo


def _scope_ok(item, escopo):
    """Escopo do catálogo compatível com o contexto (perfil|ficha)."""
    if not escopo or escopo == 'ambos':
        return True
    return item.get('escopo') in ('ambos', escopo)


def _user_inventory_values(user, tipo):
    """Conjunto de VALORES (deste tipo) que o usuário TEM no inventário — já com o
    prefixo '<tipo>-' removido, pra bater com as chaves de get_catalog."""
    if not user or not getattr(user, 'is_authenticated', False):
        return set()
    from .models import TbUsuarioCosmetico
    slugs = (
        TbUsuarioCosmetico.objects
        .filter(user=user, cosmetico__tipo=tipo, cosmetico__ativo=True)
        .values_list('cosmetico__slug', flat=True)
    )
    return {_valor_de_slug(tipo, s) for s in slugs}


def _tipo_db(tipo):
    """Aceita tanto o tipo interno de aparência (theme/frame/effect) quanto o tipo
    do catálogo (tema/moldura/efeito) e devolve sempre o tipo do catálogo."""
    return APPEARANCE_TIPO.get(tipo, tipo)


def cosmetic_allowed(user, tipo, value, escopo='ambos'):
    """True se o cosmético `value` existe no catálogo ativo do `tipo`, é compatível
    com o `escopo`, E (origem=='livre' OU o user o possui no inventário). `tipo`
    aceita o nome interno (theme/frame/effect) ou o do catálogo (tema/moldura/efeito).

    Não concede badges derivadas (staff/colaborador) ainda — isso é F2. Em F1 todo
    cosmético do seed é 'livre', então isto devolve os mesmos resultados de antes."""
    tipo = _tipo_db(tipo)
    catalogo = get_catalog(tipo)
    item = catalogo.get(value)
    if not item or not _scope_ok(item, escopo):
        return False
    if item.get('origem') == 'livre':
        return True
    return value in _user_inventory_values(user, tipo)


def catalog_options(user, tipo, escopo='ambos', selected=None):
    """Lista ordenada de opções pro seletor de aparência (perfil/ficha), já com o
    estado de desbloqueio por opção — pré-fiação da UI de cadeados de F4.

    Cada item: {key, label, class, raridade, animado, asset_url, origem, preco,
    requer_plano, descricao, estado, selected}. `estado` ∈ {'livre','possui','bloqueado'}.
    Em F1 tudo é 'livre' → nada aparece bloqueado."""
    tipo = _tipo_db(tipo)
    catalogo = get_catalog(tipo)
    inventario = _user_inventory_values(user, tipo)
    opcoes = []
    for valor, item in catalogo.items():
        if not _scope_ok(item, escopo):
            continue
        if item.get('origem') == 'livre':
            estado = 'livre'
        elif valor in inventario:
            estado = 'possui'
        else:
            estado = 'bloqueado'
        opcoes.append({
            'key': valor,
            'label': item['label'],
            'class': item['class'],
            'raridade': item['raridade'],
            'animado': item['animado'],
            'asset_url': item['asset_url'],
            'origem': item['origem'],
            'preco': item['preco'],
            'requer_plano': item['requer_plano'],
            'descricao': item['descricao'],
            'estado': estado,
            'selected': valor == selected,
        })
    return opcoes
