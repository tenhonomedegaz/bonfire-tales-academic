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
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from django.core.cache import cache

# Cor hex validada (#rrggbb). NUNCA injetar string livre em style inline — mesmo
# contrato de _sanitize_custom_theme em views.py.
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

# Defaults do tema basal 'bonfire' (ver docs/agentes/arquitetura_temas_dinamicos.md §4).
# Usados quando uma cor da definicao_json é inválida/ausente.
_DEFINICAO_DEFAULT = {
    'accent': '#f27007',
    'accent2': '#d21717',
    'surface': '#101012',
    'deep': '#09090a',
}
_PARTICULA_CHOICES = ('subir', 'cair', 'flutuar', 'nenhuma')
_VEL_CHOICES = ('lenta', 'media', 'rapida')
THEME_MOTIFS = ('none', 'facets', 'runes', 'sun', 'leaves', 'flames',
                'thorns', 'crystal', 'moon', 'eclipse', 'bats')
THEME_CATEGORIES = ('classico', 'especial')


def theme_category(item):
    """Presentation metadata never changes the item's entitlement."""
    definition = item.get('definicao')
    category = item.get('categoria')
    if category not in THEME_CATEGORIES and isinstance(definition, dict):
        category = definition.get('categoria')
    if category in THEME_CATEGORIES:
        return category
    return ('especial' if 'skin-illustrated' in (item.get('class') or '') or
            item.get('css_url') else 'classico')


def sanitize_definicao_tema(raw):
    """Normaliza a `definicao_json` de um tema-dado (schema §1 do doc normativo).

    - cores accent/accent2/surface/deep: só ^#[0-9a-fA-F]{6}$; inválida → default bonfire.
    - gradiente: bool.
    - particula: {subir,cair,flutuar,nenhuma} (default 'subir').
    - vel: {lenta,media,rapida} (default 'media').
    - glow: bool (default True).

    Dict vazio/None → retorna {} (significa "sem definição": o render cai no legado,
    regressão zero). Blindado contra injeção — nenhuma string livre sobrevive daqui."""
    if not isinstance(raw, dict) or not raw:
        return {}
    out = {}
    for key in ('accent', 'accent2', 'surface', 'deep'):
        val = str(raw.get(key, '') or '').strip()
        out[key] = val if _HEX_COLOR_RE.match(val) else _DEFINICAO_DEFAULT[key]
    grad = raw.get('gradiente')
    out['gradiente'] = grad in (True, 'true', 'on', '1', 1)
    particula = str(raw.get('particula', '') or '').strip().lower()
    out['particula'] = particula if particula in _PARTICULA_CHOICES else 'subir'
    vel = str(raw.get('vel', '') or '').strip().lower()
    out['vel'] = vel if vel in _VEL_CHOICES else 'media'
    glow = raw.get('glow', True)
    out['glow'] = glow in (True, 'true', 'on', '1', 1)
    motif = raw.get('motif', 'none')
    out['motif'] = motif if isinstance(motif, str) and motif in THEME_MOTIFS else 'none'
    return out

def sanitize_catalog_theme_definition(raw):
    """Validate stored metadata separately from the CSS-only presentation schema."""
    from django.core.exceptions import ValidationError
    result = sanitize_definicao_tema(raw)
    if isinstance(raw, dict) and 'categoria' in raw:
        if raw['categoria'] not in THEME_CATEGORIES:
            raise ValidationError('Categoria de tema invalida; use classico ou especial.')
        result['categoria'] = raw['categoria']
    if isinstance(raw, dict) and 'desbloqueio' in raw:
        from .rank_cosmetic_rewards import rank_unlock_metadata
        metadata, _ = rank_unlock_metadata(raw)
        if not metadata:
            raise ValidationError('Metadados de desbloqueio invalidos; corrija-os antes de salvar.')
        result['desbloqueio'] = {key: metadata[key] for key in (
            'schema_version', 'metric', 'rank', 'min_level', 'min_adventures', 'permanent')}
    return result


# Mapeia o "tipo interno" de aparência (usado por perfil/ficha) para o `tipo` do
# catálogo. Permite falar a mesma língua dos helpers antigos (theme/frame/effect).
APPEARANCE_TIPO = {
    'theme': 'tema',
    'frame': 'moldura',
    'effect': 'efeito',
}

_CACHE_TTL = 60  # segundos — TTL curto; invalida no save/delete do admin (signal).
_CACHE_PREFIX = 'cosmeticos:catalogo:'
_READ_CONTEXT = ContextVar('cosmetic_read_context', default=None)


@contextmanager
def cosmetic_read_context():
    """One rendered read, never a user/global cache. SQL writes discard snapshots."""
    from django.db import connection
    if _READ_CONTEXT.get() is not None:
        yield
        return
    state = {}
    token = _READ_CONTEXT.set(state)

    def invalidate_on_write(execute, sql, params, many, context):
        parts = sql.split(None, 1) if isinstance(sql, str) else ()
        command = parts[0].upper() if parts else None
        # Unknown/commented/non-text SQL is not assumed to be read-only.
        if command not in {'SELECT', 'SHOW', 'EXPLAIN', 'SAVEPOINT', 'RELEASE', 'BEGIN'}:
            state.clear()
        return execute(sql, params, many, context)

    try:
        with connection.execute_wrapper(invalidate_on_write):
            yield
    finally:
        _READ_CONTEXT.reset(token)


def cosmetic_read_scope(view=None, *, preview=False):
    """Do not retain read snapshots across profile-saving POST actions."""
    def decorate(function):
        @wraps(function)
        def wrapped(request, *args, **kwargs):
            if request.method != 'GET' and not preview:
                return function(request, *args, **kwargs)
            with cosmetic_read_context():
                return function(request, *args, **kwargs)
        return wrapped
    return decorate(view) if view is not None else decorate


def _cosmetic_read_memo(key, load):
    from django.db import connection
    state = _READ_CONTEXT.get()
    if state is None:
        return load()
    transaction_key = (tuple(id(block) for block in connection.atomic_blocks),
                       tuple(connection.savepoint_ids))
    key = (transaction_key, key)
    if key not in state:
        state[key] = load()
    return state[key]


def _sync_rank_once(user):
    from .rank_cosmetic_rewards import sync_rank_cosmetics
    # Store the marker after the service's transaction has finished invalidating reads.
    return _cosmetic_read_memo(('rank_sync', user.pk), lambda: sync_rank_cosmetics(user))


def _read_inventory(user):
    from .models import TbUsuarioCosmetico
    return _cosmetic_read_memo(('inventory', user.pk), lambda: {
        slug: (kind, origin) for slug, kind, origin in TbUsuarioCosmetico.objects.filter(
            user=user, cosmetico__ativo=True, suspenso_em__isnull=True,
        ).exclude(origem__startswith='colaborador').values_list(
            'cosmetico__slug', 'cosmetico__tipo', 'origem')})


def _read_colab_tier(user):
    from .permissions import colab_tier
    return _cosmetic_read_memo(('colab_tier', getattr(user, 'pk', None)), lambda: colab_tier(user))


def _cache_key(tipo):
    return _CACHE_PREFIX + tipo


def invalidate_cosmetic_cache():
    """Chamada pelo signal post_save/post_delete de TbCosmetico (admin-save)."""
    for tipo in ('tema', 'moldura', 'efeito', 'titulo', 'badge', 'banner_preset'):
        cache.delete(_cache_key(tipo))
    state = _READ_CONTEXT.get()
    if state is not None:
        state.clear()


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
    return _cosmetic_read_memo(('catalog', tipo), lambda: _load_catalog(tipo))


def _load_catalog(tipo):
    key = _cache_key(tipo)
    cached = cache.get(key)
    if cached is not None:
        return cached
    from .models import TbCosmetico
    from .rank_cosmetic_rewards import rank_unlock_metadata
    catalogo = {}
    qs = (TbCosmetico.objects.filter(tipo=tipo, ativo=True)
          .order_by('ordem', 'nome'))
    for c in qs:
        desbloqueio, requisito = rank_unlock_metadata(c.definicao_json)
        valor = _valor_de_slug(tipo, c.slug)
        # css_url do tema (só temas com css_file). Degrada em '' se o storage
        # não tiver base_url (ex.: dev sem MEDIA configurado).
        css_url = ''
        try:
            if c.css_file:
                css_url = c.css_file.url
        except Exception:
            css_url = ''
        catalogo[valor] = {
            'slug': c.slug,
            'label': c.nome,
            'class': c.css_class,
            'raridade': c.raridade,
            'animado': c.animado,
            # asset_url efetivo (arquivo enviado > url/glyph) — o seletor com prévia
            # e badges/conquistas consomem já resolvido.
            'asset_url': c.asset_efetivo,
            'origem': c.origem,
            'preco': c.preco,
            'requer_plano': c.requer_plano,
            'escopo': c.escopo,
            'descricao': c.descricao,
            'desbloqueio': desbloqueio,
            'requisito': requisito,
            'unlock_hint': requisito,
            # Tema como dado: definição sanitizada ({} = sem definição, cai no legado)
            # + url do CSS avançado, quando houver.
            'definicao': sanitize_definicao_tema(c.definicao_json) if c.tipo == 'tema' else {},
            'css_url': css_url,
        }
        if c.tipo == 'tema':
            category = (c.definicao_json.get('categoria')
                        if isinstance(c.definicao_json, dict) else None)
            # Keep inferred defaults out of authored metadata: the picker may use its registry.
            catalogo[valor]['categoria'] = category if category in THEME_CATEGORIES else ''
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
    if _READ_CONTEXT.get() is not None:
        from .cosmetic_entitlements import permanent_cosmetic_slugs
        return {_valor_de_slug(tipo, slug) for slug, (kind, _) in _read_inventory(user).items()
                if kind == tipo} | {_valor_de_slug(tipo, slug) for slug in permanent_cosmetic_slugs(user, tipo)}
    from .models import TbUsuarioCosmetico
    slugs = (
        TbUsuarioCosmetico.objects
        .filter(user=user, cosmetico__tipo=tipo, cosmetico__ativo=True,
                suspenso_em__isnull=True)
        .exclude(origem__startswith='colaborador')
        .values_list('cosmetico__slug', flat=True)
    )
    from .cosmetic_entitlements import permanent_cosmetic_slugs
    return {_valor_de_slug(tipo, s) for s in
            set(slugs) | permanent_cosmetic_slugs(user, tipo)}


def _catalog_ownership(user, tipo):
    """Valores possuídos e origens comprovadas, sempre consultados para a conta atual."""
    if not user or not getattr(user, 'is_authenticated', False):
        return set(), {}
    if any(item.get('desbloqueio') for item in get_catalog(tipo).values()):
        _sync_rank_once(user)
    if _READ_CONTEXT.get() is not None:
        from .cosmetic_entitlements import _permanent_sources
        records = _permanent_sources(user)
        inventory = {slug: origin for slug, (kind, origin) in _read_inventory(user).items() if kind == tipo}
        paid, event, mm = ({slug for slug, kind in records[source].items() if kind == tipo}
                           for source in ('paid', 'event', 'mm'))
        return _ownership_labels(inventory, paid, event, mm, tipo)
    from .models import (CosmeticCheckoutPurchase, CosmeticMMRedemption,
                         EventCosmeticRedemption,
                         TbUsuarioCosmetico)

    inventory = dict(TbUsuarioCosmetico.objects.filter(
        user=user, cosmetico__tipo=tipo, cosmetico__ativo=True,
        suspenso_em__isnull=True,
    ).exclude(origem__startswith='colaborador').values_list('cosmetico__slug', 'origem'))
    paid = set(CosmeticCheckoutPurchase.objects.filter(
        beneficiary=user, cosmetico__tipo=tipo, cosmetico__ativo=True,
        granted_at__isnull=False,
    ).values_list('cosmetico__slug', flat=True))
    event = set(EventCosmeticRedemption.objects.filter(
        user=user, cosmetico__tipo=tipo, cosmetico__ativo=True,
    ).values_list('cosmetico__slug', flat=True))
    mm = set(CosmeticMMRedemption.objects.filter(
        user=user, cosmetico__tipo=tipo, cosmetico__ativo=True,
        reversed_at__isnull=True,
    ).values_list('cosmetico__slug', flat=True))
    return _ownership_labels(inventory, paid, event, mm, tipo)


def _ownership_labels(inventory, paid, event, mm, tipo):
    sources = {}
    for slug in set(inventory) | paid | event | mm:
        labels = []
        if slug in event:
            labels.append('Resgate de evento')
        if slug in paid:
            labels.append('Compra confirmada')
        if slug in mm:
            labels.append('Resgate em MM')
        if not labels:
            origin = inventory[slug]
            if origin.startswith('conquista:'):
                labels.append('Conquista')
            elif origin == 'compra_mm':
                labels.append('Loja de mestragem')
            elif origin == 'staff':
                labels.append('Concessão da equipe')
            else:
                labels.append('Concessão registrada')
        sources[_valor_de_slug(tipo, slug)] = ', '.join(labels)
    return set(sources), sources


def _tipo_db(tipo):
    """Aceita tanto o tipo interno de aparência (theme/frame/effect) quanto o tipo
    do catálogo (tema/moldura/efeito) e devolve sempre o tipo do catálogo."""
    return APPEARANCE_TIPO.get(tipo, tipo)


def _colab_allows(item, tier):
    """A catalog item must explicitly opt in to a supported minimum tier."""
    if item.get('origem') != 'colaborador' or not tier:
        return False
    from .permissions import COLAB_TIER_RANK
    minimum = str(item.get('requer_plano') or '').strip().lower()
    return bool(COLAB_TIER_RANK.get(minimum) and
                COLAB_TIER_RANK.get(tier, 0) >= COLAB_TIER_RANK[minimum])


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
    if _READ_CONTEXT.get() is not None:
        if value in _user_inventory_values(user, tipo):
            return True
        if item.get('desbloqueio') and getattr(user, 'is_authenticated', False):
            _sync_rank_once(user)
            if value in _user_inventory_values(user, tipo):
                return True
        return _colab_allows(item, _read_colab_tier(user)) if item.get('origem') == 'colaborador' else False
    if item.get('desbloqueio') and getattr(user, 'is_authenticated', False):
        from .models import TbUsuarioCosmetico
        # A persisted right needs no character scan, user lock or eligibility cache.
        if TbUsuarioCosmetico.objects.filter(
                user=user, cosmetico__slug=item['slug'], cosmetico__tipo=tipo,
                cosmetico__ativo=True, suspenso_em__isnull=True,
        ).exclude(origem__startswith='colaborador').exists():
            return True
        from .rank_cosmetic_rewards import sync_rank_cosmetics
        sync_rank_cosmetics(user)
    if value in _user_inventory_values(user, tipo):
        return True
    if item.get('origem') == 'colaborador':
        from .permissions import colab_tier
        return _colab_allows(item, colab_tier(user))
    return False


def catalog_options(user, tipo, escopo='ambos', selected=None):
    """Lista ordenada de opções pro seletor de aparência (perfil/ficha), já com o
    estado de desbloqueio por opção — pré-fiação da UI de cadeados de F4.

    Cada item: {key, label, class, raridade, animado, asset_url, origem, preco,
    requer_plano, descricao, estado, selected}. `estado` ∈ {'livre','possui','bloqueado'}.
    Em F1 tudo é 'livre' → nada aparece bloqueado."""
    tipo = _tipo_db(tipo)
    catalogo = get_catalog(tipo)
    inventario, ownership_sources = _catalog_ownership(user, tipo)
    colab = None
    if any(item.get('origem') == 'colaborador' for item in catalogo.values()):
        colab = _read_colab_tier(user)
    opcoes = []
    for valor, item in catalogo.items():
        if not _scope_ok(item, escopo):
            continue
        if item.get('origem') == 'livre':
            estado = 'livre'
        elif valor in inventario:
            estado = 'possui'
        elif _colab_allows(item, colab):
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
            'desbloqueio': item.get('desbloqueio', {}),
            'requisito': item.get('requisito', ''),
            'unlock_hint': item.get('unlock_hint', ''),
            # Prévia do seletor (WP3): definição sanitizada + css do tema-dado.
            'definicao': item.get('definicao', {}),
            'css_url': item.get('css_url', ''),
            'categoria': item.get('categoria', '') if tipo == 'tema' else '',
            'estado': estado,
            'posse_origem': (ownership_sources.get(valor) or 'Acesso Colab'
                            if estado == 'possui' else ''),
            'selected': valor == selected,
        })
    return opcoes
