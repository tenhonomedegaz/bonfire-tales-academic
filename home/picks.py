# -*- coding: utf-8 -*-
"""Sistema genérico de escolhas `pick:*` do criador/level-up (contrato em
scratchpad/picks/design_picks.md).

FONTE ÚNICA da gramática `pick:<kind>[:<sub>]:<count>[(<constraints>)]` e do
*resolvedor* que varre as features de um personagem/classe e devolve os grupos de
escolha (papel A do design). Um REGISTRY por `kind` diz de onde vem o universo, como
persistir, validar e reler — registrar um kind novo = 1 entrada, sem ramificação
espalhada por views/JS.

O que este módulo NÃO faz (por design, §0 do contrato):
  - pick-REFERÊNCIA (B): `match(pick:polo)`, `cast(...)`, `spell:pick{...}` — leitura de
    escolha já feita, resolvida pelo engine (`_resolve_match`/`_grants_de_tag`). Ignorado aqui.
  - pick-EFEITO (C): `pick:creature`, `pick:allies` — alvos de combate. Ignorado aqui.
A disambiguação é estrutural: só vira grupo o token que (i) tem contagem numérica
resolvível, (ii) tem `kind` registrado no REGISTRY e (iii) não está dentro de um span
de referência (`match(...)`/`cast(...)`/`spell:pick{...}`) nem de runtime
(`trigger=...`/`instant{...}`/`while_active{...}`).
"""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Gramática — UM parser balanceado (substitui as 5 regexes paralelas de views.py).
# ---------------------------------------------------------------------------
# `pick:<kind>` localiza o token; a CAUDA (segmentos `:<seg>` + grupos `(...)`) é
# consumida com casamento BALANCEADO de ()/{} — uma restrição pode conter `match(var)`
# e `{...}` aninhados (ex.: `pick:sangue:1(=match(vertente){undine:{frio|acido}, ...})`),
# que uma regex `[^)]*` truncaria no 1º `)` interno.
_PICK_HEAD_RE = re.compile(r'pick:([a-z0-9_]+)')
_PAIRS = {'(': ')', '{': '}', '[': ']'}


def _match_pair(text, i):
    """Índice do fechamento que casa o abridor em text[i] (pilha combinada de ()/{}/[])
    ou -1. Tolerante a par trocado (fecha o topo)."""
    if text[i] not in _PAIRS:
        return -1
    stack = []
    for k in range(i, len(text)):
        ch = text[k]
        if ch in _PAIRS:
            stack.append(_PAIRS[ch])
        elif ch in (')', '}', ']'):
            if not stack:
                return -1
            stack.pop()
            if not stack:
                return k
    return -1


def _consume_pick_tail(text, pos):
    """A partir de pos (logo após `pick:<kind>`), consome a cauda balanceada. Devolve
    (segs, constr_bodies, end_pos): `segs` = segmentos `:<seg>` (seg = `{..}` OU palavra);
    `constr_bodies` = interior de cada grupo `(...)`."""
    segs, constrs = [], []
    n = len(text)
    while pos < n:
        c = text[pos]
        if c == ':':
            j = pos + 1
            if j < n and text[j] == '{':
                close = _match_pair(text, j)
                segs.append(text[j:close + 1] if close >= 0 else text[j:])
                pos = (close + 1) if close >= 0 else n
            else:
                m = re.match(r'[A-Za-z0-9_+\-]+', text[j:])
                if not m:
                    break
                segs.append(m.group(0))
                pos = j + m.end()
        elif c == '(':
            close = _match_pair(text, pos)
            constrs.append(text[pos + 1:close] if close >= 0 else text[pos + 1:])
            pos = (close + 1) if close >= 0 else n
        else:
            break
    return segs, constrs, pos


def normalize_slug(s):
    """Ponte `_`↔`-` centralizada (hoje repetida em ≥5 lugares de views.py). Devolve a
    forma canônica com hífen p/ comparação; nunca destrói o valor original do caller."""
    return (s or '').strip().replace('_', '-')


def _seg_is_count(seg):
    seg = (seg or '').strip()
    if seg in ('N', '+', ''):
        return True
    if re.match(r'^[+-]?\d+$', seg):
        return True
    if seg.startswith('{') and 'classlvl' in seg:
        return True
    return False


def _resource_ref_from_text(text):
    """`=resource X` / `=recurso X` / `resource{X}` -> slug do recurso (ou None)."""
    m = re.search(r'=\s*(?:resource|recurso)\s+([a-z0-9_-]+)', str(text))
    if not m:
        m = re.search(r'(?:resource|recurso)\{([a-z0-9_-]+)\}', str(text))
    return m.group(1) if m else None


def _balanced_context_spans(text, patterns):
    """Spans balanceados iniciados pelos regexes de ``patterns``.

    Cada padrão deve terminar no delimitador de abertura. `_match_pair` usa a mesma
    pilha combinada da gramática de picks, portanto blocos aninhados não são truncados.
    """
    spans = []
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            opening = m.end() - 1
            closing = _match_pair(text, opening)
            spans.append((m.start(), closing if closing >= 0 else len(text) - 1))
    return spans


def _non_choice_spans(text):
    """Contextos em que ``pick:`` não declara estado permanente da ficha.

    Referências são papel B. Escolhas feitas ao resolver um gatilho/efeito ativo são
    papel C (runtime/VTT), mesmo quando têm contagem e um ``define{list}`` capaz de
    fazê-las parecer um menu persistível.
    """
    return _balanced_context_spans(text, (
        r'\bmatch\s*\(',
        r'\bcast\s*\(',
        r'\bspell:pick\s*\{',
        r'\binstant\s*\{',
        r'\bwhile_active\s*\{',
        r'\btrigger\s*=\s*[a-z0-9_.-]+\s*[\{\(]',
        r'\btrigger\s*[\{\(]',
    ))


class PickToken(object):
    """Um token `pick:` papel-A já parseado (independente de universo/registry)."""
    __slots__ = ('kind', 'sub', 'count_expr', 'resource_ref', 'constraints', 'raw', 'span')

    def __init__(self, kind, sub, count_expr, resource_ref, constraints, raw, span):
        self.kind = kind
        self.sub = sub                  # subuniverso (opcao:<tipo>) ou None
        self.count_expr = count_expr    # '3' | '{classlvl=..}' | 'N' | '+' | None
        self.resource_ref = resource_ref
        self.constraints = constraints  # dict com swap/reset/from/requires/... + 'raw'
        self.raw = raw
        self.span = span


def iter_pick_tokens(text):
    """Yields ``PickToken`` papel A; ignora referências e escolhas de runtime."""
    text = str(text)
    non_choices = _non_choice_spans(text)
    for m in _PICK_HEAD_RE.finditer(text):
        start = m.start()
        if any(a <= start <= b for a, b in non_choices):
            continue
        kind = m.group(1)
        # Snapshots antigos do Bardo usam este nome para a mesma escolha de arma.
        # Normalize na leitura: o snapshot e as escolhas `tipo=maestria` ficam intactos.
        if kind == 'arma_mastery':
            kind = 'arma'
        segs, constr_bodies, end = _consume_pick_tail(text, m.end())
        constr_raw = ' '.join('(%s)' % b for b in constr_bodies)
        # separa sub (1º segmento não-contagem) da contagem (1º segmento-contagem)
        sub = None
        count_expr = None
        for s in segs:
            if count_expr is None and _seg_is_count(s):
                count_expr = s
            elif sub is None and not _seg_is_count(s):
                sub = s
        constraints = _parse_constraints(constr_raw)
        resource_ref = _resource_ref_from_text(constr_raw) or _resource_ref_from_text(text)
        yield PickToken(kind, sub, count_expr, resource_ref, constraints,
                        text[start:end], (start, end))


# Marcador IRMÃO de troca: uma tag que é SÓ `swap:<escopo>` / `reset:<escopo>` ao lado do
# pick, na mesma feature (forma normativa do catálogo em Guerreiro 'Maestria em Armas',
# Bardo 'Segredos Místicos'…). O casamento é ANCORADO de propósito: `teleport:swap{...}`
# ou `uses{pb, reset:long_rest}` são efeito/recurso, não trocabilidade de escolha.
_SWAP_MARKER_RE = re.compile(r'^(?:swap|reset)\s*:\s*([a-z0-9_]+)$')


def swap_scope(token, source):
    """Escopo de TROCA que a TAG declara para um pick papel-A, ou None.

    Duas formas normativas, as mesmas que o engine já lê em
    `character_engine._pick_trocavel_no_descanso`: constraint no próprio token
    (`pick:arma:N(swap:long_rest)`, `pick:pilar_draconico:1(swap:short_or_long)`) e
    MARCADOR IRMÃO na mesma feature (`"swap:level_up"` como tag solta).

    Devolve o escopo CRU (`long_rest`, `level_up`, `short_or_long`, `rest`…): quem decide
    o que fica ativo agora e o que é passo do wizard é o gate da UI — aqui não há política,
    só leitura da tag. Sem marcador -> None (opção fixa, só leitura na ficha).
    """
    constraints = token.constraints or {}
    escopo = constraints.get('swap') or constraints.get('reset')
    if escopo:
        return escopo
    for tag in (getattr(source, 'tags_json', None) or []):
        m = _SWAP_MARKER_RE.match(str(tag).strip())
        if m:
            return m.group(1)
    tags = {str(tag).strip() for tag in (getattr(source, 'tags_json', None) or [])}
    description = str(getattr(source, 'descricao', '') or '')
    # Early sealed pages used paired rest triggers and described a repeatable
    # ritual, but had no swap marker. Require both triggers and explicit prose.
    if ({'trigger=short_rest', 'trigger=long_rest'} <= tags
            and re.search(r'\b(?:trocar|substituir|novo)\b', description, re.I)
            and re.search(r'\b(?:descanso|ritual)\b', description, re.I)):
        return 'short_or_long'
    return None


def _parse_constraints(raw):
    raw = raw or ''
    listed = re.search(r'\bde\s*:\s*\[([^\]]+)\]', raw)
    defaults = re.search(r'\bdefaults\s*:\s*\[([^\]]+)\]', raw)
    source_match = re.search(
        r'from\s*:\s*(classe|subclasse)\s*\{\s*([a-z0-9_\-]+)\s*\}',
        raw,
    )
    return {
        'raw': raw,
        'swap': (re.search(r'swap\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'on_gain': bool(re.search(r'\bon_gain\s*:\s*1\b', raw)),
        'reset': (re.search(r'reset\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'from': (re.search(r'from\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'from_menu': (re.search(r'from_menu\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'from_known': (re.search(r'from_known\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'seed_from': (re.search(r'seed_from\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'from_kind': source_match.group(1) if source_match else None,
        'from_slug': source_match.group(2) if source_match else None,
        'listed_slugs': [normalize_slug(value) for value in re.split(r'[,|]', listed.group(1))
                         if value.strip()] if listed else None,
        'add': int((re.search(r'\badd\s*:\s*(\d+)', raw) or [None, 0])[1]),
        'default_slugs': [normalize_slug(value) for value in re.split(r'[,|]', defaults.group(1))
                          if value.strip()] if defaults else [],
        'requires': (re.search(r'requires\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'define': [tok.strip() for body in re.findall(r'=\s*define\s*:\s*\{([^}]*)\}', raw)
                   for tok in body.split('|') if tok.strip()] or None,
    }


def _page_option_source(source, token):
    """Recover a missing ``from:classe`` only when page text names this option type.

    A sealed feature may predate the explicit source constraint while stating
    that its choice uses the options available to another class. Match the
    bold option-type label to the token before trusting the named class; the
    versioned option catalog still decides which options that class owns.
    """
    if token.kind != 'opcao' or not token.sub or token.constraints.get('from_kind'):
        return None
    from django.utils.text import slugify

    description = str(getattr(source, 'descricao', '') or '')
    pattern = (r'\*\*([^*]+)\*\*[^.\n]{0,100}?\bescolha\s+entre\s+as\s+'
               r'op\S+\s+dispon\S+\s+para\s+(?:o|a)\s+(\S+)')
    for match in re.finditer(pattern, description, re.I):
        if '\ufffd' in match.group(1) or '\ufffd' in match.group(2):
            continue
        if slugify(match.group(1)).replace('-', '_') == token.sub:
            return slugify(match.group(2))
    return None


# ---------------------------------------------------------------------------
# Contagem — fusão de _count_expr_for_level + _choice_resource_limit + _pick_count_expr
# ---------------------------------------------------------------------------
def _count_expr_cumulative(expr, level):
    """`{classlvl=X:n,...}` -> soma cumulativa dos n com limiar<=level (conhecidas)."""
    return sum(int(v) for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*([+-]?\d+)', expr)
               if int(lv) <= level)


def resource_limit(classe, nivel, resource_slug, *, ruleset=None):
    """Máximo de um recurso-de-escolha da classe no nível (ponte `_`↔`-`)."""
    if not classe or not resource_slug:
        return None
    from .models import TbRecursoclasse
    from .character_engine import RESOURCE_TIPO_CHOICE, _resource_max_at, _resource_tipo
    alvo = normalize_slug(resource_slug)
    if ruleset is not None:
        from .versioned_classes import VersionedClassCatalog
        todos = VersionedClassCatalog(ruleset, classe.pk).resources(nivel)
    else:
        todos = list(TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True))
    exatos = [r for r in todos if normalize_slug(r.slug) == alvo]
    parciais = [r for r in todos if alvo in normalize_slug(r.slug)]
    candidatos = exatos + [r for r in parciais if r not in exatos]
    r = next((rec for rec in candidatos if _resource_tipo(rec) == RESOURCE_TIPO_CHOICE), None)
    if r is None and candidatos:
        r = candidatos[0]
    return _resource_max_at(r, nivel) if r else None


def count_for(count_expr, nivel, classe=None, resource_ref=None, *, ruleset=None):
    """N de uma pick-ESCOLHA: literal -> int; `{classlvl=..}` -> soma cumulativa;
    'N'/'+'/vazio -> vem do recurso de tabela (`=resource`). None se indeterminado."""
    expr = (count_expr or '').strip()
    if expr.startswith('{') and 'classlvl' in expr:
        return _count_expr_cumulative(expr, nivel) or None
    if re.match(r'^[+-]?\d+$', expr):
        return int(expr)
    if expr in ('N', '+', ''):
        return resource_limit(classe, nivel, resource_ref, ruleset=ruleset)
    return None


# ---------------------------------------------------------------------------
# REGISTRY por kind — universe / persist / validate / readback.
# Registrar um kind novo = 1 entrada aqui (nenhuma ramificação em views/JS).
# ---------------------------------------------------------------------------
def _slug2tipo_map():
    """slug (hífen E underscore) -> TbOpcaojogo.tipo (rótulo exibido)."""
    from django.utils.text import slugify
    from .models import TbOpcaojogo
    out = {}
    for t in TbOpcaojogo.objects.values_list('tipo', flat=True).distinct():
        if not t:
            continue
        s = slugify(t)
        out[s] = t
        out[s.replace('-', '_')] = t
    return out


def _page_embedded_option_universe(ctx, options, tipo_display):
    """Use a page's explicit option embed when its legacy ACL has no entries."""
    constraints = ctx.get('constraints') or {}
    if not tipo_display or constraints.get('from_kind') or constraints.get('listed_slugs'):
        return []
    source = ctx.get('source')
    description = str(getattr(source, 'descricao', '') or '')
    if not re.search(r'(?im)^\s*::options\s*=\s*' + re.escape(tipo_display)
                     + r'\s*$', description):
        return []
    return [{'id': option['id_opcao'], 'slug': option['slug'],
             'nome': option['nome'], 'descricao': option.get('descricao') or '',
             'pre': option.get('pre_requisito') or ''}
            for option in sorted(options, key=lambda item: item['nome'])
            if option['tipo'] == tipo_display]


def _opcao_universe(ctx):
    """Opções acessíveis (TbOpcaojogo do tipo ∩ TbAcessoopcao p/ classe/subclasse/nível)."""
    from django.db.models import Q
    from .models import TbOpcaojogo, TbAcessoopcao, TbClasse, TbSubclasse
    if ctx.get('tipo') == 'item_magico':
        from .character_engine import _item_consumivel_meta
        from .versioned_items import resolved_inventory

        personagem = ctx.get('personagem')
        if personagem is None:
            return []
        infusions = personagem.escolhas.filter(tipo='infusao').select_related('id_opcao')
        if personagem.classes.count() > 1:
            infusions = infusions.filter(origem__startswith='%s:' % ctx['classe'].nome)
        infusions = list(infusions.order_by('slot'))
        replicas = [row for row in infusions
                    if (row.valor or '').startswith('item_magico:')]
        # Cada Infusao conhecida pode ceder seu proprio espaco a uma receita.
        replaceable = infusions
        if not replaceable:
            return []
        replacement_options = [
            {'slug': str(row.pk),
             'nome': 'Substituir %s' % (row.id_opcao.nome if row.id_opcao_id
                                      else row.valor or 'Infusao'),
             'descricao': 'Ocupa o mesmo espaco de Infusao conhecida.',
             'already_replica': (row.valor or '').startswith('item_magico:')}
            for row in replaceable]
        tags = ' '.join(str(tag) for tag in
                        (getattr(ctx.get('source'), 'tags_json', None) or []))
        limits = [(0, 'comum')]
        limits.extend((int(level), rarity) for level, rarity in re.findall(
            r'classlvl\s*>=\s*(\d+)\s*:\s*(comum|incomum|raro)', tags))
        maximum = max((rarity for level, rarity in limits
                       if level <= int(ctx.get('nivel') or 1)),
                      key={'comum': 0, 'incomum': 1, 'raro': 2}.get)
        rank = {'comum': 0, 'incomum': 1, 'raro': 2}
        inventory = personagem.inventario.filter(
            id_item_magico__isnull=False, qtd__gt=0).select_related('id_item_magico')
        if ctx.get('ruleset') is not None:
            inventory = resolved_inventory(ctx['ruleset'], inventory)
        out = {}
        for possession in inventory:
            item = possession.id_item_magico
            rarity = (item.raridade or '').split('_', 1)[0]
            if (rarity not in rank or rank[rarity] > rank[maximum]
                    or _item_consumivel_meta(possession, item)['consumivel']
                    or any(row.valor == 'item_magico:' + item.slug for row in replicas)):
                continue
            out[item.slug] = {'id': None, 'slug': item.slug, 'nome': item.nome,
                              'descricao': item.descricao_markdown or '',
                              'pre': item.get_raridade_display(),
                              'subopcoes': replacement_options}
        return sorted(out.values(), key=lambda option: option['nome'])
    constraints = ctx.get('constraints') or {}
    if ctx.get('ruleset') is not None:
        from .versioned_options import VersionedOptions
        catalog = VersionedOptions(ctx['ruleset'])
        universe = catalog.universe(ctx)
        if universe or constraints.get('subclass_only'):
            return universe
        tipo_disp = ctx.get('tipo_display') or catalog.type_map().get(ctx['tipo'])
        return _page_embedded_option_universe(ctx, catalog.data['options'], tipo_disp)
    tipo_disp = ctx.get('tipo_display') or _slug2tipo_map().get(ctx['tipo'])
    if not tipo_disp:
        return []
    listed = constraints.get('listed_slugs')
    if listed:
        return [{'id': o.id_opcao, 'slug': o.slug, 'nome': o.nome,
                 'descricao': o.descricao or '', 'pre': o.pre_requisito or ''}
                for o in TbOpcaojogo.objects.filter(tipo=tipo_disp).order_by('nome')
                if normalize_slug(o.slug) in listed]
    classe = ctx.get('classe')
    subclasse = ctx.get('subclasse')
    source_kind = constraints.get('from_kind')
    source_slug = constraints.get('from_slug')
    explicit_source = bool(source_kind and source_slug)
    if source_kind == 'classe':
        classe = TbClasse.objects.filter(slug=source_slug).first()
        subclasse = None
    elif source_kind == 'subclasse':
        subclasse = TbSubclasse.objects.filter(slug=source_slug).first()
        classe = subclasse.id_classe if subclasse else None
    nivel = int(ctx.get('nivel') or 1)
    acc = TbAcessoopcao.objects.filter(nivel_recebimento__lte=nivel).filter(
        (Q(id_classe=classe) if classe and not constraints.get('subclass_only')
         else Q(pk__in=[]))
        | (Q(id_subclasse=subclasse) if subclasse else Q(pk__in=[])))
    qs = TbOpcaojogo.objects.filter(tipo=tipo_disp)
    # ACL e por UNIVERSO. A classe pode ter acessos de outro tipo (por exemplo,
    # Estilos de Luta) sem que isso esconda um catalogo global sem ACL (Manobras).
    universe_ids = qs.values_list('id_opcao', flat=True)
    has_universe_acl = TbAcessoopcao.objects.filter(id_opcao_id__in=universe_ids).exists()
    acc_ids = set(acc.filter(id_opcao_id__in=universe_ids).values_list(
        'id_opcao_id', flat=True))
    if explicit_source or has_universe_acl or constraints.get('subclass_only'):
        qs = qs.filter(id_opcao__in=acc_ids)
    universe = [{'id': o.id_opcao, 'slug': o.slug, 'nome': o.nome,
             'descricao': o.descricao or '', 'pre': o.pre_requisito or ''}
            for o in qs.order_by('nome')]
    if universe or constraints.get('subclass_only'):
        return universe
    return _page_embedded_option_universe(
        ctx, TbOpcaojogo.objects.filter(tipo=tipo_disp).values(
            'id_opcao', 'slug', 'nome', 'tipo', 'descricao', 'pre_requisito'),
        tipo_disp)


def _opcao_origin(group):
    # origem IDÊNTICA à do editar-ficha (personagem_escolher_opcoes) p/ o update_or_create
    # casar entre criador e level-up: '<Classe>: <Tipo Exibido>'.
    disp = group.get('tipo_display') or _slug2tipo_map().get(group.get('tipo')) or group.get('tipo') or ''
    return '%s: %s' % (group.get('classe') or '', disp)


def _opcao_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha, TbOpcaojogo
    tipo = group['persist_tipo']
    origem = _opcao_origin(group)
    base = int(group.get('slot_base') or 0)
    if group.get('tipo') == 'item_magico':
        from django.db import transaction
        with transaction.atomic():
            for v in valores:
                item_slug, _, row_id = str(v).partition('|')
                candidate = next((u for u in group.get('universo', [])
                                  if u['slug'] == item_slug and any(
                                      sub['slug'] == row_id
                                      for sub in u.get('subopcoes', []))), None)
                if candidate is None:
                    raise ValueError('Selected item or infusion is no longer available.')
                infusion = TbPersonagemEscolha.objects.select_for_update().filter(
                    pk=int(row_id), id_personagem=personagem, tipo='infusao').first()
                if infusion is None:
                    raise ValueError('Known infusion no longer exists.')
                selected_id = group.get('selected_id')
                if selected_id is not None and int(selected_id) != infusion.pk:
                    raise ValueError('Selected infusion does not match the target slot.')
                if selected_id is None and (infusion.valor or '').startswith('item_magico:'):
                    raise ValueError('Already learned recipe cannot fill another slot.')
                if TbPersonagemEscolha.objects.filter(
                        id_personagem=personagem, tipo='infusao',
                        valor='item_magico:' + item_slug).exclude(pk=infusion.pk).exists():
                    raise ValueError('This item is already a known infusion.')
                infusion.id_opcao = None
                infusion.valor = 'item_magico:' + item_slug
                infusion.save(update_fields=['id_opcao', 'valor'])
        return
    for i, v in enumerate(valores):
        frozen = next((u for u in group.get('universo', [])
                       if str(v) in (str(u.get('id')), str(u.get('slug')))), None)
        if frozen is None:
            continue
        if group.get('ruleset') is not None:
            op = TbOpcaojogo.objects.only('pk').filter(pk=frozen['id']).first()
            if op is None:
                raise ValueError('Selected option no longer exists.')
        else:
            op = (TbOpcaojogo.objects.filter(id_opcao=v).first() if str(v).isdigit() else None) \
                or TbOpcaojogo.objects.filter(slug=v).first()
        if not op:
            continue
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem[:150], tipo=tipo, slot=base + i,
            defaults={'id_opcao': op,
                      'valor': (frozen['slug'] if group.get('ruleset') is not None else op.slug)})


def _opcao_readback(personagem, group):
    if personagem is None:
        return []
    tipo = group['persist_tipo']
    if group.get('tipo') == 'item_magico':
        choices = personagem.escolhas.filter(
            tipo='infusao', valor__startswith='item_magico:').order_by('slot')
        if personagem.classes.count() > 1:
            choices = choices.filter(origem__startswith='%s:' % group['classe'])
        names = {u['slug']: u['nome'] for u in group.get('universo', [])}
        return [{'id': row.pk, 'slot': row.slot,
                 'valor': '%s|%s' % (row.valor.split(':', 1)[1], row.pk),
                 'id_opcao': None,
                 'nome': names.get(row.valor.split(':', 1)[1], row.valor)}
                for row in choices]
    alt = normalize_slug(tipo)
    alt2 = tipo.replace('-', '_')
    out = []
    frozen_names = {str(u.get('id')): u.get('nome') for u in group.get('universo', [])}
    frozen_names.update({str(u.get('slug')): u.get('nome') for u in group.get('universo', [])})
    choices = (personagem.escolhas.all() if group.get('ruleset') is not None
               else personagem.escolhas.select_related('id_opcao').all())
    # Em multiclasse, o mesmo tipo tem orçamentos independentes por classe.
    # Classe única continua relendo linhas antigas sem origem padronizada.
    if group.get('classe') and personagem.classes.count() > 1:
        choices = choices.filter(origem=_opcao_origin(group)[:150])
    for e in choices:
        if e.tipo in (tipo, alt, alt2):
            name = None
            if tipo == 'infusao' and (e.valor or '').startswith('item_magico:'):
                from .models import TbItemMagico
                item = TbItemMagico.objects.filter(slug=e.valor.split(':', 1)[1]).first()
                name = 'Replicar: %s' % (item.nome if item else e.valor.split(':', 1)[1])
            out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor,
                        'id_opcao': e.id_opcao_id,
                        'nome': (name or frozen_names.get(str(e.id_opcao_id))
                                 or frozen_names.get(str(e.valor))
                                 or (e.valor if group.get('ruleset') is not None
                                     else (e.id_opcao.nome if e.id_opcao_id else e.valor)))})
    out.sort(key=lambda x: x['slot'])
    return out


# ---------------------------------------------------------------------------
# kind 'arma' — Maestria de Arma em DOIS NÍVEIS: por slot de `pick:arma` o jogador
# escolhe a ARMA e, dentre as maestrias{...} DAQUELA arma, UMA maestria. A tag
# `maestrias{...}` da própria arma mundana é a AUTORIDADE das maestrias (regra do
# projeto). O valor persistido é `'<arma-slug>|<maestria-slug>'` (1 linha por slot,
# TbPersonagemEscolha tipo='maestria'); o derive concede/mostra SÓ a maestria escolhida.
# A MESMA ARMA PODE ocupar mais de um slot para aprender uma 2ª maestria dela (regra da
# staff: p.ex. lentidão e exposição no mesmo arco — uma por ataque); a unicidade que se
# exige é a do PAR (arma, maestria), NÃO a da arma. O perfil de ataque lista TODAS as
# maestrias aprendidas de cada arma.
# Linhas LEGADAS só-arma (`'<arma-slug>'`, sem `|`) ficam com a maestria PENDENTE — a
# ficha não quebra e o painel de Maestria reabre a sub-escolha (nunca escolhemos por elas).
# ---------------------------------------------------------------------------
_MAESTRIA_TAG_RE = re.compile(r'maestrias\{([^}]*)\}')


def weapon_mastery_slugs(weapon):
    """Slugs das maestrias declaradas na tag `maestrias{...}` da arma (a arma mundana é a
    autoridade). [] se a arma não declara nenhuma (essa arma não pede sub-escolha)."""
    for t in (getattr(weapon, 'tags_json', None) or []):
        m = _MAESTRIA_TAG_RE.search(str(t))
        if m:
            return [x.strip() for x in m.group(1).split(',') if x.strip()]
    return []


def split_arma_maestria(valor):
    """Valor de um slot de Maestria de Arma -> (arma_slug, maestria_slug|None). Formato NOVO:
    `'<arma-slug>|<maestria-slug>'` (arma + A maestria dela escolhida). Linha LEGADA só-arma
    (`'<arma-slug>'`, sem `|`) -> maestria=None (a escolher)."""
    s = (valor or '').strip()
    if '|' in s:
        a, m = s.split('|', 1)
        return a.strip(), (m.strip() or None)
    return s, None


def _arma_prof_matchers(ctx):
    """Proficiência de arma do dono da escolha, no formato de matchers do motor. Vem do
    `character_engine` (a MESMA leitura que o perfil de ataque usa: categorias da
    classe/multiclasse + grants `prof:weapon{...}` das tags ativas), nunca de uma lista
    fixa de categorias por classe. `[]` = não há como saber (não filtra)."""
    from .character_engine import weapon_proficiency_matchers
    personagem = ctx.get('personagem')
    if personagem is not None:
        return weapon_proficiency_matchers(personagem=personagem, ruleset=ctx.get('ruleset'))
    classe = ctx.get('classe')
    if classe is None:
        return []
    # CRIADOR (nível 1, personagem ainda não existe): a classe é a principal e a própria
    # feature que declarou o pick pode conceder proficiência junto (Erudito da Guerra).
    source = ctx.get('source')
    sources = [('classe', getattr(source, 'nome', ''), source, int(ctx.get('nivel') or 1))] \
        if source is not None else []
    return weapon_proficiency_matchers(classe=classe, sources=sources, ruleset=ctx.get('ruleset'))


def _arma_universe(ctx):
    """Armas (TbItemMundano categoria='arma') EM QUE O PERSONAGEM TEM PROFICIÊNCIA — regra
    5e/PO: maestria só se aprende em arma que se sabe empunhar (era por isso que um Bárbaro
    via Bacamarte/Mosquete no seletor). O filtro lê a proficiência REAL do motor
    (`_arma_prof_matchers`); sem proficiência legível o universo fica inteiro, para a
    escolha nunca desaparecer em silêncio.

    Cada arma expõe `maestrias:[{slug,nome,efeito}]` como SUB-OPÇÕES da 2ª escolha (a
    maestria única que se ganha ao pegar a arma). `chips` fica para exibição resumida
    quando a arma não abre sub-escolha (sem maestrias)."""
    from .models import TbItemMundano, TbOpcaojogo
    from .character_engine import weapon_allowed
    from .item_mecanica import mecanica_de_tags, dano_display
    # tags `maestrias{...}` da arma usam '_' (minar_sap) e são a AUTORIDADE; o catálogo
    # TbOpcaojogo usa '-' (minar-sap) — normaliza '_'→'-' NO LOOKUP p/ nome/efeito legíveis.
    if ctx.get('ruleset') is not None:
        from .versioned_items import item_catalog
        from .versioned_options import VersionedOptions
        weapons = item_catalog(ctx['ruleset'], 'mundane-item-catalog', TbItemMundano).values()
        mast = {normalize_slug(o['slug']): o for o in VersionedOptions(ctx['ruleset']).data['options']
                if o['tipo'] == 'Maestria de Arma'}
    else:
        weapons = TbItemMundano.objects.filter(categoria='arma').order_by('subcategoria', 'nome')
        mast = {normalize_slug(o.slug): o for o in TbOpcaojogo.objects.filter(tipo='Maestria de Arma')}
    sub_label = {'arma_simples': 'Arma Simples', 'arma_simples_dist': 'Arma Simples à Distância',
                 'arma_marcial': 'Arma Marcial', 'arma_marcial_dist': 'Arma Marcial à Distância',
                 'arma_fogo': 'Arma de Fogo'}
    matchers = _arma_prof_matchers(ctx)
    todas, proficientes = [], []
    for w in sorted((w for w in weapons if w.categoria == 'arma'),
                    key=lambda w: (w.subcategoria or '', w.nome or '')):
        maestrias = []
        for s in weapon_mastery_slugs(w):
            o = mast.get(normalize_slug(s))               # 's' cru (autoridade); lookup normalizado
            maestrias.append({'slug': s, 'nome': ((o['nome'] if isinstance(o, dict) else o.nome) if o else s),
                              'efeito': (((o['descricao'] if isinstance(o, dict) else o.descricao) if o else '') or '')})
        _mec = mecanica_de_tags(w.tags_json, w.subcategoria)
        entrada = {'slug': w.slug, 'nome': w.nome, 'dano': dano_display(_mec),
                   'cat': sub_label.get(w.subcategoria, w.subcategoria or 'Arma'),
                   'maestrias': maestrias,
                   'chips': [m['nome'] for m in maestrias]}
        todas.append(entrada)
        if (not matchers and ctx.get('ruleset') is None) or weapon_allowed(
                matchers, w.subcategoria, w.slug, w.nome, _mec.get('propriedades')):
            proficientes.append(entrada)
    # FAIL-OPEN: proficiência declarada que não casa com arma nenhuma do catálogo (grant
    # opaco tipo `prof:weapon{bound}` sem categoria por trás) não pode ZERAR o grupo — a
    # pendência sumiria da ficha e do wizard. Aí volta o catálogo inteiro, como antes.
    return proficientes if ctx.get('ruleset') is not None else (proficientes or todas)


def _arma_persist(personagem, group, valores):
    """1 linha por SLOT (tipo='maestria', slot=i) com o valor combinado `'<arma>|<maestria>'`
    (arma + a maestria dela escolhida). Arma sem maestrias cadastradas grava só o slug da arma."""
    from .models import TbPersonagemEscolha
    # rótulo estável (independe de qual feature carregou o pick:arma) — compat com o
    # criador antigo, que gravava origem='Maestria de Arma (<Classe>)'.
    origem = 'Maestria de Arma (%s)' % (group.get('classe') or '')
    base = int(group.get('slot_base') or 0)
    for i, v in enumerate(valores):
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem[:150], tipo='maestria', slot=base + i,
            defaults={'valor': str(v)})


def _arma_readback(personagem, group):
    """Linhas de Maestria de Arma JÁ persistidas. Dado LEGADO (gravado antes do filtro de
    proficiência) continua listado: a arma some do UNIVERSO de escolha nova, não da ficha.
    `sem_proficiencia` marca essas linhas para a ficha avisar sem quebrar a exibição."""
    if personagem is None:
        return []
    from .models import TbItemMundano, TbOpcaojogo
    rows = personagem.escolhas.filter(tipo='maestria')
    # Uma maestria do Bardo não preenche o orçamento do Guerreiro em multiclasse.
    # Fichas de classe única continuam lendo registros legados sem origem.
    if personagem.classes.count() > 1:
        rows = rows.filter(origem='Maestria de Arma (%s)' % (group.get('classe') or ''))
    if group.get('ruleset') is not None:
        weapons = {str(u.get('slug')): u for u in group.get('universo', [])}
        mast = {normalize_slug(m['slug']): m['nome'] for u in weapons.values()
                for m in (u.get('maestrias') or [])}
        out = []
        for e in rows.order_by('slot'):
            arma, maestria = split_arma_maestria(e.valor)
            weapon = weapons.get(str(arma))
            pending = bool(weapon and weapon.get('maestrias') and maestria is None)
            name = (weapon or {}).get('nome', arma)
            name += (' — ' + (mast.get(normalize_slug(maestria)) or maestria) if maestria
                     else (' — (maestria a escolher)' if pending else ''))
            out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor, 'nome': name,
                        'arma': arma, 'maestria': maestria, 'pendente': pending,
                        'sem_proficiencia': weapon is None})
        return out
    # catálogo por slug NORMALIZADO ('-'); a maestria persistida vem da tag da arma ('_').
    mast = {normalize_slug(o.slug): o.nome for o in TbOpcaojogo.objects.filter(tipo='Maestria de Arma')}
    permitidas = {str(u.get('slug')) for u in (group.get('universo') or [])}
    out = []
    for e in rows.order_by('slot'):
        arma, maestria = split_arma_maestria(e.valor)
        w = (TbItemMundano.objects.filter(categoria='arma', slug=arma).first()
             or TbItemMundano.objects.filter(categoria='arma', nome__iexact=arma).first())
        arma_nome = w.nome if w else arma
        maest_nome = mast.get(normalize_slug(maestria)) if maestria else None
        pendente = bool(w and weapon_mastery_slugs(w) and maestria is None)
        # arma que EXISTE no catálogo mas ficou fora do universo = proficiência que o
        # personagem não tem (escolha legada). Arma inexistente não entra aqui: ali o
        # problema é outro (slug morto) e o rótulo já mostra o valor cru.
        sem_prof = bool(w) and str(w.slug) not in permitidas
        rot = arma_nome + (' — ' + (maest_nome or maestria) if maestria
                           else (' — (maestria a escolher)' if pendente else ''))
        out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor, 'nome': rot,
                    'arma': arma, 'maestria': maestria, 'pendente': pendente,
                    'sem_proficiencia': sem_prof})
    return out


def _default_validate(group, valores):
    """Validação genérica: contagem exata + pertinência ao universo."""
    erros = []
    n = int(group.get('n') or 0)
    universo = set()
    for option in group.get('universo', []):
        suboptions = option.get('subopcoes') or option.get('maestrias') or []
        if suboptions:
            universo.update('%s|%s' % (option['slug'], sub['slug'])
                            for sub in suboptions
                            if not (group.get('optional') and not group.get('selected_id')
                                    and sub.get('already_replica')))
        else:
            universo.add(str(option.get('slug')))
            if option.get('id') is not None:
                universo.add(str(option['id']))
    vals = list(dict.fromkeys([str(v) for v in (valores or [])]))
    fora = [v for v in vals if v not in universo]
    parents = [v.split('|', 1)[0] for v in vals]
    duplicate_parent = (group.get('unique_parent')
                        and len(parents) != len(set(parents)))
    if fora or len(vals) != n or duplicate_parent:
        erros.append(group.get('erro_label') or ('Escolha %d opção(ões) válida(s).' % n))
    return erros


def _arma_validate(group, valores):
    """Cada slot = ARMA + (se a arma tiver maestrias) UMA maestria DELA. A MESMA ARMA PODE
    repetir entre slots para aprender uma 2ª maestria dela (regra confirmada pela staff: p.ex.
    lentidão e exposição no mesmo arco, uma por ataque); o que NÃO pode repetir é o PAR
    `(arma, maestria)`. Valida contagem exata, arma no universo, a maestria pertencente à arma
    (formato `'<arma>|<maestria>'`) e a unicidade do PAR (a duplicata é do par, não da arma)."""
    n = int(group.get('n') or 0)
    by_slug = {str(u.get('slug')): u for u in group.get('universo', [])}
    ok, vistos = [], set()
    for v in (valores or []):
        arma, maestria = split_arma_maestria(v)
        u = by_slug.get(str(arma))
        if not u:
            continue
        masteries = {m['slug'] for m in (u.get('maestrias') or [])}
        par = (str(arma), maestria)      # a chave de duplicata é o PAR (arma+maestria)
        if par in vistos:                # par repetido: recusado (mas a arma pode repetir)
            continue
        if masteries:                    # arma com maestrias: exige UMA delas
            if maestria in masteries:
                vistos.add(par)
                ok.append(v)
        elif maestria is None:           # arma sem maestrias: só a arma já completa o slot
            vistos.add(par)
            ok.append(v)
    if len(ok) != n:
        return ['Escolha %d arma(s) para Maestria de Arma (a mesma arma pode repetir com '
                'maestrias diferentes; não repita o mesmo par arma+maestria).' % n]
    return []


# ---------------------------------------------------------------------------
# kind 'pericia' — escolha de proficiência em perícia. O universo é a lista da
# CLASSE da feature (skills_lvl1) menos as já proficientes, ou uma restrição
# explícita da própria tag; persiste em TbPersonagemEscolha (tipo='pericia') e é
# relido como proficiência no derive (_pericias_escolhidas em character_engine).
# ---------------------------------------------------------------------------
def _pericia_class_pool(classe):
    """Perícias da lista de nível 1 da classe (`skills_lvl1{ pick:N de [..] }`),
    slugs canônicos (hífen). [] se a classe não declara a lista."""
    from .character_engine import _norm_skill_slug
    for t in (getattr(classe, 'tags_json', None) or []):
        m = re.search(r'skills_lvl1\s*\{([^}]*)\}', str(t))
        if not m:
            continue
        ml = re.search(r'\[([^\]]*)\]', m.group(1))
        if ml:
            return [_norm_skill_slug(x) for x in ml.group(1).split(',') if x.strip()]
    return []


def _pericia_restrict_slugs(ctx):
    """Restrição explícita de universo declarada na tag (várias sintaxes vistas na
    base), ou None quando ausente:
      sub-lista    `pick:pericia:{a|b|c}:1`
      `(de:[a,b])` / `de:[a,b]` / `{ de:[a,b] }` / ` de [a,b]`
      `(=skill:{a | b})`
    Devolve os slugs canônicos na ordem da tag, ou None (herda a lista da classe)."""
    from .character_engine import _norm_skill_slug, _SKILL_INFO
    cand = None
    sub = (ctx.get('tipo') or '').strip()
    if sub.startswith('{'):                                    # pick:pericia:{a|b|c}:1
        cand = re.split(r'[|,]', sub.strip('{}'))
    tag = str(ctx.get('tag_text') or '')
    # Regra padrÃ£o "ganha X; se jÃ¡ tiver X, escolha qualquer outra perÃ­cia". Sem a
    # proficiÃªncia anterior, o universo Ã© somente X; com ela, cai no pool completo menos
    # as jÃ¡ possuÃ­das. Usado por PresenÃ§a Intimidante do Berserker.
    replacement = re.search(r'\breplace\s*:\s*([a-z0-9_-]+)', tag)
    if replacement:
        target = _norm_skill_slug(replacement.group(1))
        if not _pericia_owned_before_source(
                ctx.get('personagem'), target, ctx.get('source')):
            return [target] if target in _SKILL_INFO else None
        return list(_SKILL_INFO.keys())
    if cand is None:
        m = re.search(r'\bde\s*:?\s*\[([^\]]*)\]', tag)        # de:[..] / de [..] / (de:[..]) / { de:[..] }
        if m:
            cand = m.group(1).split(',')
    if cand is None:
        m = re.search(r'=\s*skill\s*:\s*\{([^}]*)\}', tag)     # =skill:{a | b}
        if m:
            cand = re.split(r'[|,]', m.group(1))
    if cand is None:
        return None
    out = []
    for c in cand:
        s = _norm_skill_slug(c.strip())
        if s in _SKILL_INFO and s not in out:
            out.append(s)
    return out or None


def _pericia_owned_slugs(personagem):
    """Perícias que o personagem JÁ possui (proficiência/expertise registrada em
    TbPersonagemPericia + escolhas pick:pericia já persistidas) — excluídas do
    universo de uma nova escolha (regra: a lista MENOS as já proficientes)."""
    from .character_engine import _slug, _norm_skill_slug, proficient_skill_slugs
    if personagem is None:
        return set()
    owned = set()
    for per in personagem.pericias.all():
        if per.proficiente or per.expertise:
            owned.add(_norm_skill_slug(_slug(per.nome)))
    for e in personagem.escolhas.filter(tipo='pericia'):
        if e.valor:
            owned.add(_norm_skill_slug(e.valor))
    # Bloqueio UNIVERSAL: perícias concedidas por tags (raça/essência/feature/antecedente
    # automáticas) não vivem em TbPersonagemPericia — só o derive as agrega. Sem isto o
    # level-up ofereceria uma perícia que o personagem já tinha por essas fontes.
    owned |= proficient_skill_slugs(personagem)
    return owned


def _pericia_owned_before_source(personagem, slug, source):
    """Se `slug` jÃ¡ era proficiente sem contar a feature `source` que oferece troca."""
    from .character_engine import (_norm_skill_slug, _slug, _features_do_personagem)
    if personagem is None:
        return False
    if any(_norm_skill_slug(_slug(p.nome)) == slug and (p.proficiente or p.expertise)
           for p in personagem.pericias.all()):
        return True
    if personagem.escolhas.filter(tipo='pericia', valor=slug).exists():
        return True
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse'))
    for (_origem, _fonte, obj, _classe) in _features_do_personagem(personagem, classes):
        if obj is source or (obj.__class__ is source.__class__ and obj.pk == source.pk):
            continue
        for tag in (getattr(obj, 'tags_json', None) or []):
            if re.search(r'(?<![a-z_-])prof:%s\b' % re.escape(slug), str(tag)):
                return True
    return False


def _pericia_universe(ctx):
    from .character_engine import _SKILL_INFO, _norm_skill_slug
    restrito = _pericia_restrict_slugs(ctx)
    classe = ctx.get('classe')
    if restrito:
        pool = list(restrito)
    else:
        pool = _pericia_class_pool(classe) if classe else []
        if not pool:
            pool = list(_SKILL_INFO.keys())
    owned = _pericia_owned_slugs(ctx.get('personagem'))
    replacement = re.search(r'\breplace\s*:\s*([a-z0-9_-]+)', str(ctx.get('tag_text') or ''))
    if replacement:
        target = _norm_skill_slug(replacement.group(1))
        if not _pericia_owned_before_source(ctx.get('personagem'), target, ctx.get('source')):
            # O avaliador genÃ©rico enxerga o alvo dentro do prÃ³prio token de replacement;
            # ele nÃ£o pode bloquear a opÃ§Ã£o que esta feature ainda precisa conceder.
            owned.discard(target)
    out = []
    for sl in pool:
        sl = _norm_skill_slug(sl)
        info = _SKILL_INFO.get(sl)
        if not info or sl in owned:
            continue
        out.append({'id': None, 'slug': sl, 'nome': info[0], 'descricao': '', 'pre': ''})
    return out


def _pericia_origem(group):
    """Origem estável POR FEATURE (separa múltiplas features pick:pericia da mesma
    classe, ex.: Conhecimento Primitivo vs. outra). Casa persist↔readback."""
    return str(group.get('origem') or group.get('classe') or 'Perícia')[:150]


def _pericia_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha
    from .character_engine import _norm_skill_slug
    origem = _pericia_origem(group)
    base = int(group.get('slot_base') or 0)
    for i, sl in enumerate(valores):
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem, tipo='pericia', slot=base + i,
            defaults={'valor': _norm_skill_slug(str(sl))})


def _pericia_readback(personagem, group):
    if personagem is None:
        return []
    from .character_engine import _SKILL_INFO, _norm_skill_slug
    origem = _pericia_origem(group)
    out = []
    for e in personagem.escolhas.filter(tipo='pericia', origem=origem).order_by('slot'):
        sl = _norm_skill_slug(e.valor or '')
        nome = _SKILL_INFO.get(sl, (e.valor,))[0]
        out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor, 'nome': nome})
    return out


# ---------------------------------------------------------------------------
# kind 'pericia_expertise' — escolha de ESPECIALIZAÇÃO (dobro do PB) entre as perícias em
# que o personagem já é PROFICIENTE. Universo opcionalmente restrito pela tag: `from:{a|b}`
# (Monge, Treinamento das Sombras), `de:[a,b]`, sub `{a|b}`, ou `<attr>_based`/`wis_based`
# (Batedor). Persiste em TbPersonagemEscolha(tipo='pericia_expertise'); relido como expertise
# no derive (_expertise_escolhidas em character_engine → dobro do PB). Complementa o campo
# manual TbPersonagemPericia.expertise (criador nv1).
# ---------------------------------------------------------------------------
_ATTR_BASED_RE = re.compile(r'\b(str|for|dex|des|con|int|wis|sab|cha|car)_based\b')


def _pericia_proficient_slugs(personagem):
    """Perícias em que o personagem é PROFICIENTE (campo TbPersonagemPericia + escolhas
    pick:pericia persistidas). Universo-base da escolha de expertise (só se especializa no
    que já se é proficiente)."""
    from .character_engine import _slug, _norm_skill_slug
    if personagem is None:
        return set()
    out = set()
    for per in personagem.pericias.all():
        if per.proficiente or per.expertise:
            out.add(_norm_skill_slug(_slug(per.nome)))
    for e in personagem.escolhas.filter(tipo='pericia'):
        if e.valor:
            out.add(_norm_skill_slug(e.valor))
    return out


def _expertise_owned_slugs(personagem):
    """Perícias JÁ especializadas (campo expertise + escolhas pick:pericia_expertise) —
    excluídas do universo de uma nova escolha (não se especializa duas vezes na mesma)."""
    from .character_engine import _slug, _norm_skill_slug
    if personagem is None:
        return set()
    from .character_engine import (_active_conditional_expertise_origins,
                                   _features_do_personagem)
    active_conditional = _active_conditional_expertise_origins(
        personagem, _features_do_personagem(personagem))
    out = set()
    for per in personagem.pericias.all():
        if per.expertise:
            out.add(_norm_skill_slug(_slug(per.nome)))
    for e in personagem.escolhas.filter(tipo='pericia_expertise'):
        if (e.origem.startswith('conditional-expertise:')
                and e.origem not in active_conditional):
            continue
        if e.valor:
            out.add(_norm_skill_slug(e.valor))
    return out


def _pericia_expertise_restrict(ctx):
    """Restrição de universo da tag de expertise: `from:{a|b}`, `de:[a,b]`, sub `{a|b}`, ou
    `<attr>_based`/`wis_based` (perícias cujo atributo-padrão é aquele). Slugs canônicos
    permitidos, ou None (sem restrição = qualquer perícia proficiente)."""
    from .character_engine import _norm_skill_slug, _SKILL_INFO, _EN_SIG, _SAVE_TOKEN_EN
    tag = str(ctx.get('tag_text') or '')
    cand = None
    sub = (ctx.get('tipo') or '').strip()
    if sub.startswith('{'):
        cand = re.split(r'[|,]', sub.strip('{}'))
    if cand is None:
        m = re.search(r'\bfrom\s*:\s*\{([^}]*)\}', tag)          # from:{a | b}
        if m:
            cand = re.split(r'[|,]', m.group(1))
    if cand is None:
        m = re.search(r'\bde\s*:?\s*\[([^\]]*)\]', tag)          # de:[a, b]
        if m:
            cand = m.group(1).split(',')
    if cand is not None:
        out = []
        for c in cand:
            s = _norm_skill_slug(c.strip())
            if s in _SKILL_INFO and s not in out:
                out.append(s)
        return out or None
    m = _ATTR_BASED_RE.search(tag)                               # wis_based / int_based …
    if m:
        sig = _EN_SIG.get(_SAVE_TOKEN_EN.get(m.group(1)))        # 'wis' -> 'SAB'
        if sig:
            return [sl for sl, info in _SKILL_INFO.items() if info[1] == sig] or None
    return None


def _prior_expertise(personagem, source, skill):
    """Check expertise granted before this source, including direct tag grants."""
    from .character_engine import (
        _expertise_escolhidas, _feature_identity, _feature_talent_attr_sig,
        _features_do_personagem, _norm_skill_slug, _pericias_escolhidas,
        _slug, _talent_attr_map,
    )
    from .tag_engine import evaluate_tags

    skill = _norm_skill_slug(skill)
    source_id = _feature_identity(source)
    features = [feature for feature in _features_do_personagem(personagem)
                if _feature_identity(feature[2]) != source_id]
    if any(_norm_skill_slug(_slug(row.nome)) == skill and row.expertise
           for row in personagem.pericias.all()):
        return True
    if skill in _expertise_escolhidas(personagem, features):
        return True
    prior_prof = {_norm_skill_slug(_slug(row.nome)) for row in personagem.pericias.all()
                  if row.proficiente or row.expertise}
    prior_prof |= _pericias_escolhidas(personagem)
    attrs = _talent_attr_map(personagem)
    operations = []
    for _origin, _name, other, _level in features:
        tags = [tag for tag in (getattr(other, 'tags_json', None) or [])
                if isinstance(tag, str)]
        if (any('attr:talent_attr_score+' in tag for tag in tags)
                and not _feature_talent_attr_sig(other, attrs)):
            continue
        operations.extend(op for op in evaluate_tags(tags).operations
                          if op.active and op.op == 'grant_proficiency')
    prior_prof.update(_norm_skill_slug(str(op.value)) for op in operations
                      if op.verb in {'prof', 'expertise'})
    return any(op.verb == 'expertise'
               and (_norm_skill_slug(str(op.value)) == skill
                    or (op.value == 'original_prof' and skill in prior_prof))
               for op in operations)


def _pericia_expertise_universe(ctx):
    from .character_engine import _SKILL_INFO, _norm_skill_slug
    personagem = ctx.get('personagem')
    conditional = (ctx.get('constraints') or {}).get('requires') == 'already_expertise'
    if conditional and personagem is not None:
        from .character_engine import derive
        prof = {_norm_skill_slug(row['nome']) for row in derive(personagem)['pericias']
                if row['proficiente'] or row['expertise']}
    else:
        prof = _pericia_proficient_slugs(personagem)
    owned = _expertise_owned_slugs(personagem)
    if conditional and personagem is not None:
        from .character_engine import _feature_identity
        source_id = _feature_identity(ctx.get('source'))
        own_origin = 'conditional-expertise:%s' % source_id
        own_choices = {_norm_skill_slug(value) for value in
                       personagem.escolhas.filter(tipo='pericia_expertise',
                                                 origem=own_origin).values_list('valor', flat=True)
                       if value}
        # Keep persisted selections visible in their source group after readback.
        owned -= own_choices
    restrito = _pericia_expertise_restrict(ctx)
    pool = list(restrito) if restrito is not None else (sorted(prof) if prof else list(_SKILL_INFO.keys()))
    out = []
    for sl in pool:
        sl = _norm_skill_slug(sl)
        info = _SKILL_INFO.get(sl)
        if not info or sl in owned:
            continue
        if prof and sl not in prof:          # expertise exige proficiência (quando há o dado)
            continue
        out.append({'id': None, 'slug': sl, 'nome': info[0], 'descricao': '', 'pre': ''})
    return out


def _pericia_expertise_origem(group):
    """Origem estável POR FEATURE (separa múltiplas features de expertise). Casa persist↔readback."""
    if (group.get('constraints') or {}).get('requires') == 'already_expertise':
        return 'conditional-expertise:%s' % group['source_identity']
    return str(group.get('origem') or group.get('classe') or 'Especialização')[:150]


def _pericia_expertise_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha
    from .character_engine import _norm_skill_slug
    origem = _pericia_expertise_origem(group)
    base = int(group.get('slot_base') or 0)
    for i, sl in enumerate(valores):
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem, tipo='pericia_expertise', slot=base + i,
            defaults={'valor': _norm_skill_slug(str(sl))})


def _pericia_expertise_readback(personagem, group):
    if personagem is None:
        return []
    from .character_engine import _SKILL_INFO, _norm_skill_slug
    origem = _pericia_expertise_origem(group)
    out = []
    for e in personagem.escolhas.filter(tipo='pericia_expertise', origem=origem).order_by('slot'):
        sl = _norm_skill_slug(e.valor or '')
        nome = _SKILL_INFO.get(sl, (e.valor,))[0]
        out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor, 'nome': nome})
    return out


# ---------------------------------------------------------------------------
# kind 'ferramenta' - a categoria fica no argumento, nao no nome do verbo.
# Ex.: pick:ferramenta:instrumento:1. O mesmo handler cobre instrumentos,
# ferramentas de artesao ou o catalogo inteiro.
# ---------------------------------------------------------------------------
def _ferramenta_universe(ctx):
    from .models import TbItemMundano
    from .character_engine import derive, _slug
    sub = normalize_slug(ctx.get('tipo') or '').replace('-', '_')
    if not sub and re.search(r'\btipo_de_artesao\b', (ctx.get('constraints') or {}).get('raw', '')):
        sub = 'ferramenta_artesao'
    if ctx.get('ruleset') is not None:
        from .versioned_items import item_catalog
        items = item_catalog(ctx['ruleset'], 'mundane-item-catalog', TbItemMundano).values()
    else:
        items = TbItemMundano.objects.filter(categoria='ferramenta')
    subcategorias = {
        'instrumento': {'instrumento'},
        'instrumento_musical': {'instrumento'},
        'ferramenta_artesao': {'ferramenta_artesao'},
        'ferramenta_artesao_ou_instrumento': {'ferramenta_artesao', 'instrumento'},
    }.get(sub)
    if subcategorias:
        items = [item for item in items if item.subcategoria in subcategorias]
    personagem = ctx.get('personagem')
    sheet = derive(personagem, ruleset=ctx.get('ruleset')) if personagem is not None else {}
    owned = {_slug(name) for name in sheet.get('ferramentas', [])
             + sheet.get('prof_multiclasse_ferramenta', [])}
    return [{'id': item.id_item, 'slug': item.slug, 'nome': item.nome,
             'descricao': item.descricao_markdown or '', 'pre': '',
             'ja_proficiente': _slug(item.nome) in owned or _slug(item.slug) in owned}
            for item in sorted((item for item in items if item.categoria == 'ferramenta'),
                               key=lambda item: item.nome or '')]


def _ferramenta_validate(group, valores):
    """Proficiência já possuída não consome uma nova escolha de ferramenta."""
    available = [item for item in group.get('universo', []) if not item.get('ja_proficiente')]
    aliases = {str(value): item['slug'] for item in available
               for value in (item.get('id'), item['slug']) if value is not None}
    normalized = [aliases.get(str(value), str(value)) for value in (valores or [])]
    return _default_validate(dict(group, universo=available), normalized)


def _ferramenta_origem(group):
    return str(group.get('origem') or group.get('classe') or 'Ferramenta')[:150]


def _ferramenta_persist(personagem, group, valores):
    from .models import TbItemMundano, TbPersonagemEscolha, TbPersonagemProficiencia
    origem = _ferramenta_origem(group)
    base = int(group.get('slot_base') or 0)
    for i, value in enumerate(valores):
        frozen = next((u for u in group.get('universo', [])
                       if str(value) in (str(u.get('id')), str(u.get('slug')))), None)
        if frozen is None:
            continue
        if group.get('ruleset') is not None:
            if not TbItemMundano.objects.filter(pk=frozen['id']).exists():
                raise ValueError('Selected tool no longer exists.')
            slug, name = frozen['slug'], frozen['nome']
        else:
            item = (TbItemMundano.objects.filter(id_item=value).first()
                    if str(value).isdigit() else None)
            item = item or TbItemMundano.objects.filter(categoria='ferramenta', slug=value).first()
            if item is None:
                continue
            slug, name = item.slug, item.nome
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem, tipo='ferramenta',
            slot=base + i, defaults={'valor': slug})
        TbPersonagemProficiencia.objects.get_or_create(
            id_personagem=personagem, tipo='ferramenta', nome=name,
            defaults={'origem': origem[:100]})


def _ferramenta_readback(personagem, group):
    if personagem is None:
        return []
    origem = _ferramenta_origem(group)
    if group.get('ruleset') is not None:
        nomes = {u['slug']: u['nome'] for u in group.get('universo', [])}
    else:
        from .models import TbItemMundano
        nomes = dict(TbItemMundano.objects.filter(categoria='ferramenta').values_list('slug', 'nome'))
    return [{'id': row.id, 'slot': row.slot, 'valor': row.valor,
             'nome': nomes.get(row.valor, row.valor)}
            for row in personagem.escolhas.filter(
                tipo='ferramenta', origem=origem).order_by('slot')]


# ---------------------------------------------------------------------------
# kind 'idioma' — opções do catálogo de idiomas do mundo, com proficiência
# materializada para a ficha e escolha por feature para releitura.
# ---------------------------------------------------------------------------
def _idioma_universe(ctx):
    from .models import TbIdioma
    from .character_engine import derive, _slug

    personagem = ctx.get('personagem')
    conhecidos = ({_slug(nome) for nome in derive(personagem).get('idiomas', [])}
                  if personagem is not None else set())
    return [{'id': idioma.pk, 'slug': idioma.slug, 'nome': idioma.nome,
             'descricao': '', 'pre': '',
             'ja_proficiente': (_slug(idioma.nome) in conhecidos
                                or _slug(idioma.slug) in conhecidos)}
            for idioma in TbIdioma.objects.all()]


def _idioma_validate(group, valores):
    disponiveis = [item for item in group.get('universo', [])
                   if not item.get('ja_proficiente')]
    return _default_validate(dict(group, universo=disponiveis), valores)


def _idioma_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha, TbPersonagemProficiencia

    origem = str(group.get('origem') or group.get('classe') or 'Idioma')[:150]
    base = int(group.get('slot_base') or 0)
    for i, valor in enumerate(valores):
        option = next((item for item in group.get('universo', [])
                       if str(valor) in (str(item['id']), item['slug'])), None)
        if option is None:
            continue
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem, tipo='idioma', slot=base + i,
            defaults={'valor': option['slug']})
        TbPersonagemProficiencia.objects.get_or_create(
            id_personagem=personagem, tipo='idioma', nome=option['nome'],
            defaults={'origem': origem[:100]})


def _idioma_readback(personagem, group):
    if personagem is None:
        return []
    from .models import TbIdioma

    origem = str(group.get('origem') or group.get('classe') or 'Idioma')[:150]
    nomes = dict(TbIdioma.objects.values_list('slug', 'nome'))
    return [{'id': row.id, 'slot': row.slot, 'valor': row.valor,
             'nome': nomes.get(row.valor, row.valor)}
            for row in personagem.escolhas.filter(
                tipo='idioma', origem=origem).order_by('slot')]


# kind 'talento' — escolha de um TALENTO (TbTalento) concedido por uma feature
# (`pick:talento:1(=talento_de_origem...)` da linhagem Erthari 'Determinação Comum';
# `pick:talento:1(tipo:origem, requires:prereqs)` do talento 'Raízes Profundas';
# `pick:talento:1(from:any_raca, requires:prereq, without{asi})` do traço humano 'Multitalentoso').
# O universo é TbTalento honrando as constraints da tag: `=talento_de_origem`/`tipo:origem`
# restringe a tipo='origem'; `from:any_raca`/`tipo:geral` restringe a tipo='geral' (talento
# "de qualquer raça" — Multitalentoso concede um talento GERAL, nunca de origem/antecedente);
# `requires:prereq` valida pré-requisitos (views._talento_prereq_ok); exclui os já possuídos.
# Persiste em TbPersonagemTalento (materialização, p/ o derive aplicar o efeito) E em
# TbPersonagemEscolha(tipo='talento', origem=<feature>) para o READBACK per-feature (uma
# TbPersonagemTalento sozinha não distingue de qual feature veio o talento — ex.: o talento
# de origem do antecedente NÃO deve satisfazer o pick de 'Determinação Comum').
# ---------------------------------------------------------------------------
_TALENTO_ORIGEM_RE = re.compile(r'talento_de_origem|\btipo\s*:\s*origem\b')
# GERAL: `from:any_raca` (Multitalentoso — "Talento (Feat) de qualquer raça para a qual
# cumpra os pré-requisitos") ou um `tipo:geral` explícito. No modelo de dados só existem
# talentos 'origem' e 'geral' (não há talentos "raciais"), então "de qualquer raça" = GERAL.
_TALENTO_GERAL_RE = re.compile(r'\bfrom\s*:\s*any_raca\b|\btipo\s*:\s*geral\b')
_TALENTO_PREREQ_RE = re.compile(r'requires\s*:\s*prereq')


def _talento_constraint_text(ctx):
    return '%s %s' % (ctx.get('tag_text') or '', (ctx.get('constraints') or {}).get('raw') or '')


def _talento_owned_slugs(personagem):
    """Talentos que o personagem JÁ possui (TbPersonagemTalento materializado + escolhas
    pick:talento persistidas) — excluídos do universo de uma nova escolha."""
    if personagem is None:
        return set()
    out = set()
    for pt in personagem.talentos.select_related('id_talento').all():
        if pt.id_talento_id and getattr(pt.id_talento, 'slug', None):
            out.add(pt.id_talento.slug)
    for e in personagem.escolhas.filter(tipo='talento'):
        if e.valor:
            out.add(e.valor)
    return out


def _talento_universe(ctx):
    from .models import TbTalento
    from .epic_talents import is_epic_talent
    text = _talento_constraint_text(ctx)
    if ctx.get('ruleset') is not None:
        from .versioned_origins import VersionedOrigins
        talents = VersionedOrigins(ctx['ruleset']).objects(TbTalento)
    else:
        talents = TbTalento.objects.all()
    talents = [t for t in talents if not is_epic_talent(t)]
    if _TALENTO_ORIGEM_RE.search(text) or (ctx.get('kind') or '') == 'talento_de_origem':
        talents = [t for t in talents if (t.tipo or '').lower() == 'origem']
    elif _TALENTO_GERAL_RE.search(text):
        # `from:any_raca`/`tipo:geral` (Multitalentoso): pool = talentos GERAIS que o
        # personagem qualifica (requires:prereq abaixo) — NUNCA os de origem. Sem este
        # ramo o universo caía no `all()` e misturava os 43 de origem, e — quando o
        # personagem tinha TAMBÉM um pick de origem (Erthari) — o grupo de origem vencia
        # o desempate por persist_tipo e o talento geral acusava "fora do universo".
        talents = [t for t in talents if (t.tipo or '').lower() == 'geral']
    personagem = ctx.get('personagem')
    owned = _talento_owned_slugs(personagem)
    # `requires:prereq` → filtra pelo mesmo checador do ASI (views._talento_prereq_ok, que
    # precisa da ficha derivada). Sem personagem (criador nv1) não há como avaliar → aceita
    # todos (talentos de origem não têm pré de nível > 1).
    ficha = None
    if _TALENTO_PREREQ_RE.search(text) and personagem is not None:
        from .character_engine import derive
        ficha = derive(personagem, ruleset=ctx.get('ruleset'))
        from . import views as _views
    out = []
    for t in sorted(talents, key=lambda t: t.nome or ''):
        if getattr(t, 'slug', None) in owned:
            continue
        if ficha is not None and not _views._talento_prereq_ok(t, personagem, ficha):
            continue
        out.append({'id': t.id_talento, 'slug': t.slug, 'nome': t.nome,
                    'descricao': (t.descricao or ''), 'pre': (t.pre_requisito or ''),
                    'tipo': t.tipo or ''})
    return out


def _talento_origem(group):
    """Origem estável POR FEATURE (separa múltiplos pick:talento). Casa persist↔readback."""
    return str(group.get('origem') or group.get('classe') or 'Talento')[:150]


def _talento_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha, TbPersonagemTalento, TbTalento
    origem = _talento_origem(group)
    base = int(group.get('slot_base') or 0)
    nivel = int(group.get('nivel') or getattr(personagem, 'nivel', 1) or 1)
    for i, v in enumerate(valores):
        frozen = next((u for u in group.get('universo', [])
                       if str(v) in (str(u.get('id')), str(u.get('slug')))), None)
        if frozen is None:
            continue
        if group.get('ruleset') is not None:
            t = TbTalento.objects.only('pk').filter(pk=frozen['id']).first()
            if t is None:
                raise ValueError('Selected talent no longer exists.')
            slug, name = frozen['slug'], frozen['nome']
            category = 'origem' if (frozen.get('tipo') or '').lower() == 'origem' else 'geral'
        else:
            t = (TbTalento.objects.filter(id_talento=v).first() if str(v).isdigit() else None) \
                or TbTalento.objects.filter(slug=v).first()
            if not t:
                continue
            slug, name = t.slug, t.nome
            category = 'origem' if (t.tipo or '').lower() == 'origem' else 'geral'
        # categoria conforme a fonte/tipo do talento escolhido (origem vs geral).
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem, tipo='talento', slot=base + i,
            defaults={'valor': slug})
        TbPersonagemTalento.objects.get_or_create(
            id_personagem=personagem, id_talento=t,
            defaults={'categoria': category, 'nivel': nivel, 'nome': name,
                      'detalhes': origem[:200]})


def _talento_readback(personagem, group):
    if personagem is None:
        return []
    origem = _talento_origem(group)
    nomes = {u['slug']: u['nome'] for u in group.get('universo', [])}
    if group.get('ruleset') is None:
        from .models import TbTalento
        nomes.update(dict(TbTalento.objects.values_list('slug', 'nome')))
    out = []
    for e in personagem.escolhas.filter(tipo='talento', origem=origem).order_by('slot'):
        out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor,
                    'nome': nomes.get(e.valor, e.valor)})
    return out


# ---------------------------------------------------------------------------
# kind GENÉRICO de MENU — `pick:<kind>:<count>` cujo universo vive num
# `define{<kind>: list{ a:{..}, b:{..} }}` IRMÃO na mesma feature (menu inline).
# É o padrão de Máscara de Guerra/Comunidade, Evolução Totêmica, mutagênicos… onde
# as opções não estão em TbOpcaojogo mas na própria tag. Um único handler serve a
# TODOS esses kinds (zero if-por-tipo): o `kind` do pick nomeia o define a ler.
# ---------------------------------------------------------------------------
def _pretty_kind(slug):
    """slug de kind/opção -> rótulo legível ('mascara_guerra' -> 'Mascara Guerra')."""
    return (slug or '').replace('_', ' ').replace('-', ' ').strip().title()


_RESIST_DAMAGE_LABELS = {
    'acido': 'Ácido', 'raio': 'Elétrico', 'fogo': 'Fogo',
    'frio': 'Frio', 'trovejante': 'Trovão',
}


def _match_brace(s, open_idx):
    """Índice do `}` que fecha o `{` em `open_idx` (contagem balanceada) ou -1."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _menu_entries(body, class_level=None):
    """Opções de topo de `list{...}`; enum interno gera pares distintos.

    Um ramo `resistencia:{pick:resist:{fogo|frio}}` representa duas escolhas
    persistentes, não a opção incompleta `resistencia`. Outros picks aninhados
    continuam no seu próprio fluxo condicional.
    """
    out, seen = [], set()
    i = 0
    while i < len(body):
        m = re.search(r'([a-z0-9_-]+)\s*:\s*\{', body[i:])
        if not m:
            break
        slug = m.group(1)
        open_idx = i + m.end() - 1          # posição do '{' da opção
        close = _match_brace(body, open_idx)
        if close < 0:
            break
        entry_body = body[open_idx + 1:close]
        level_gate = re.search(r'\bmin_class_level\s*:\s*(\d+)\b', entry_body)
        if level_gate and class_level is not None and class_level < int(level_gate.group(1)):
            i = close + 1
            continue
        nested = re.search(r'\bpick:([a-z][a-z0-9_]*):\s*\{([^{}]+)\}', entry_body)
        options = []
        if nested:
            choices = [value.strip() for value in nested.group(2).split('|')]
            if len(choices) > 1 and all(re.fullmatch(r'[a-z][a-z0-9_-]*', value)
                                         for value in choices):
                options = [(slug + '|' + value,
                            ('Resistência Elemental' if slug == 'resistencia_elemental'
                             else _pretty_kind(slug)) + ' — ' +
                            (_RESIST_DAMAGE_LABELS.get(value, _pretty_kind(value))
                             if nested.group(1) == 'resist' else _pretty_kind(value)))
                            for value in choices]
        if not options:
            options = [(slug, _pretty_kind(slug))]
        for option_slug, option_name in options:
            if option_slug not in seen:
                seen.add(option_slug)
                out.append({'id': None, 'slug': option_slug,
                            'nome': option_name, 'descricao': '', 'pre': ''})
        i = close + 1
    return out


@lru_cache(maxsize=1)
def _legacy_choice_supplements():
    path = Path(__file__).resolve().parent / 'rules' / 'legacy_choice_supplements.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1:
        raise ValueError('Unsupported legacy choice supplement schema.')
    return data['pages']


def _menu_options_from_define(source, kind, class_level=None):
    """Opções de `pick:<kind>` cujo universo vive num `define{<kind>: list{...}}` da
    própria feature. Devolve [{'id':None,'slug':..,'nome':..}] ou [] (sem define)."""
    kind = (kind or '').strip()
    if not kind:
        return []
    pat = re.compile(r'define\s*\{\s*' + re.escape(kind) + r'\s*:\s*list\s*\{')
    for tag in (getattr(source, 'tags_json', None) or []):
        s = str(tag)
        m = pat.search(s)
        if not m:
            continue
        open_idx = m.end() - 1              # '{' do list{...}
        close = _match_brace(s, open_idx)
        if close < 0:
            continue
        options = _menu_entries(s[open_idx + 1:close], class_level=class_level)
        # Keep option labels and descriptions in sync with the same page that
        # defines the inline menu, including accented names in frozen rules.
        from django.utils.text import slugify
        details = {}
        for line in str(getattr(source, 'descricao', '') or '').splitlines():
            match = re.match(
                r'^\s*-\s*\*\*(?:\[([^\]]+)\]\([^)]*\)|([^:*]+)):\*\*\s*(.*)$',
                line)
            if match:
                name = (match.group(1) or match.group(2)).strip()
                details[slugify(name).replace('-', '_')] = (name, match.group(3).strip())
        for option in options:
            if '|' not in option['slug'] and option['slug'] in details:
                option['nome'], option['descricao'] = details[option['slug']]
        page_digest = hashlib.sha256(
            str(getattr(source, 'descricao', '') or '').encode('utf-8')).hexdigest()
        existing = {option['slug'] for option in options}
        for page in _legacy_choice_supplements():
            if page['page_sha256'] != page_digest or page['choice_kind'] != kind:
                continue
            for supplement in page['options']:
                if (supplement['slug'] in existing or
                        (class_level is not None and
                         class_level < supplement['min_class_level'])):
                    continue
                options.append({'id': None, 'slug': supplement['slug'],
                                'nome': supplement['name'],
                                'descricao': supplement['description'], 'pre': ''})
                existing.add(supplement['slug'])
        return options
    return []


# ---------------------------------------------------------------------------
# Universo INLINE — quando o menu não vive num `define{list}` irmão e sim na
# CAUDA do próprio token: `(={a|b|c})`, `(=<rotulo>:{a|b|c})`, `(=define:{a|b})`,
# sub `:{a|b|c}`, ou `(=match(<var>){k1:{..}, k2:{..}})` (universo DEPENDE de uma
# escolha anterior, ex.: `pick:sangue` depende de `pick:vertente`). Um único
# resolvedor serve a TODOS esses kinds — o mesmo _MENU_ENTRY genérico.
# ---------------------------------------------------------------------------
def _split_pipe(s):
    """'a | b, c' -> ['a','b','c'] (slugs canônicos, sem vazios)."""
    return [t.strip() for t in re.split(r'[|,]', str(s or '')) if t.strip()]


def _slugs_to_opts(slugs):
    out, seen = [], set()
    for s in slugs:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append({'id': None, 'slug': s, 'nome': _pretty_kind(s), 'descricao': '', 'pre': ''})
    return out


def _menu_branch_options(body, chosen):
    """De um corpo de ramos `k1:{a | b}, k2:{c}` (usado em `=match(var){...}`),
    devolve os slugs do ramo `chosen`. [] se o ramo não existe (ex.: vertente
    'oread' num sangue que só ramifica undine/sylph -> nenhuma sub-escolha)."""
    if not chosen:
        return []
    m = re.search(r'(?<![a-z0-9_-])' + re.escape(chosen) + r'\s*:\s*\{([^}]*)\}', body)
    if m:
        return _split_pipe(m.group(1))
    m = re.search(r'(?<![a-z0-9_-])' + re.escape(chosen) + r'\s*:\s*([a-z0-9_-]+)', body)
    return [m.group(1)] if m else []


def _inline_menu_options(tok, escolhas=None):
    """Opções inline de um PickToken (universo na cauda do token, não num define
    irmão). Ordem de tentativa: `=match(var){...}` (ramo da escolha anterior) →
    `=<rotulo>?:{a|b|c}` / `={a|b}` / `=define:{a|b}` → sub `:{a|b|c}`. [] se nenhum."""
    escolhas = escolhas or {}
    raw = ((tok.constraints or {}).get('raw')) or ''
    # (1) universo DEPENDENTE: =match(<var>){ramo:{..}, ...}
    m = re.search(r'=\s*match\((?:pick:)?([a-z0-9_]+)\)\s*\{', raw)
    if m:
        var = m.group(1)
        open_idx = m.end() - 1
        close = _match_brace(raw, open_idx)
        body = raw[open_idx + 1:close] if close >= 0 else raw[open_idx + 1:]
        return _slugs_to_opts(_menu_branch_options(body, escolhas.get(var)))
    # (2) enumeração literal na cauda: ={a|b} | =<rotulo>:{a|b} | =define:{a|b}
    m = re.search(r'=\s*(?:[a-z0-9_]+\s*:\s*)?\{([^}]*)\}', raw)
    if m:
        return _slugs_to_opts(_split_pipe(m.group(1)))
    # Paginas tambem declaram menus literais como `pick:elemento:1(agua|ar|fogo)`.
    # Aceitar apenas uma lista simples evita interpretar custos e efeitos como opcoes.
    m = re.fullmatch(r'\s*\(([a-z0-9_-]+(?:\s*\|\s*[a-z0-9_-]+)+)\)\s*', raw)
    if m:
        return _slugs_to_opts(_split_pipe(m.group(1)))
    # (3) enumeração no SUB do token: pick:<kind>:{a|b|c}:N
    sub = (tok.sub or '').strip()
    if sub.startswith('{'):
        return _slugs_to_opts(_split_pipe(sub.strip('{}')))
    return []


def _selected_define_branches(tags, choice_values):
    """Recover nested grants from old menus without a separate match() tag.

    The menu itself remains a single choice; only the selected branch can
    grant additional persistent picks. Published snapshots stay unchanged.
    """
    from .character_engine import _resolve_match

    chosen = choice_values or {}
    for raw in tags:
        tag = str(raw)
        for match in re.finditer(r'define\s*\{\s*([a-z][a-z0-9_]*)\s*:\s*list\s*\{', tag):
            kind = match.group(1)
            if not chosen.get(kind) or any(re.search(
                    r'\bmatch\((?:pick:)?' + re.escape(kind) + r'\)\s*\{', str(item))
                    for item in tags):
                continue
            end = _match_brace(tag, match.end() - 1)
            if end < 0:
                continue
            body = tag[match.end():end]
            branch = _resolve_match('match(%s){%s}' % (kind, body), chosen,
                                    outer_only=True)
            if any(iter_pick_tokens(branch)):
                yield branch


def _listed_menu_options(source, tok):
    """Resolve a literal `pick:kind:N de [a, b]` from the same page tag."""
    if source is None or tok is None:
        return []
    pattern = re.compile(re.escape(tok.raw) + r'\s+de\s*\[([^\]]+)\]', re.I)
    for tag in getattr(source, 'tags_json', None) or []:
        match = pattern.search(str(tag))
        if match:
            return _slugs_to_opts(_split_pipe(match.group(1)))
    return []


def _paired_prepared_spell_options(source, tok):
    """Use a same-feature spell list for a legacy prepared-spell pick.

    Sealed pages can name the list in ``spell_selection:fonte:X`` while their
    ``pick:X_preparada:N`` omits ``de [...]``. The shared source identifier
    prevents an unrelated spell list on the page from becoming this menu.
    """
    if source is None or tok is None:
        return []
    for tag in getattr(source, 'tags_json', None) or []:
        match = re.search(
            r'\bspell_selection:fonte:([a-z0-9_]+)\s*\{[^{}]*\blist:\s*\[([^\]]+)\]',
            str(tag))
        if not match or tok.kind not in {match.group(1) + '_preparada',
                                       match.group(1) + '_preparado'}:
            continue
        options = _split_pipe(match.group(2))
        if len(options) >= 2 and all(re.fullmatch(r'[a-z0-9_-]+', slug) for slug in options):
            return _slugs_to_opts(options)
    return []


def _legacy_description_menu_options(source, tok):
    """Recover a legacy menu only from an explicit choice list on its own page.

    Early sealed catalogs sometimes had a counted ``pick:kind`` tag without a
    universe even though the feature text enumerated the choices. Require a
    matching ``Escolha`` heading, or a single counted pick paired with a
    bold, counted ``dentre`` list. Runtime picks remain excluded by the token
    scanner; arbitrary prose must never become a builder menu by inference.
    """
    if source is None or tok is None:
        return []
    from django.utils.text import slugify

    # A frozen page may enumerate an initial choice without bold Markdown:
    # "escolha um Elemento inicial: Água, Ar, Fogo ou Terra".  Match the noun
    # to the counted pick kind and require a complete, unique list.
    for line in str(getattr(source, 'descricao', '') or '').splitlines():
        statement = re.search(
            r'\bescolha\s+um(?:a)?\s+([\wÀ-ÿ]+)\s+inicial\s*:\s*([^.;\n]+)',
            line, re.I)
        if not statement or slugify(statement.group(1)).replace('-', '_') != tok.kind:
            continue
        names = [name.strip() for name in re.split(
            r',\s*|\s+ou\s+', statement.group(2), flags=re.I)]
        slugs = [slugify(name) for name in names]
        if len(slugs) >= 3 and all(slugs) and len(set(slugs)) == len(slugs):
            return [{'id': None, 'slug': slug, 'nome': name,
                     'descricao': '', 'pre': ''}
                    for slug, name in zip(slugs, names)]

    # A rest-swappable sealed choice can list its named options with effects
    # in parentheses rather than in a `de [...]` tag. Require the tagged noun,
    # every enumerated entry, and an explicit rest-time replacement on the page.
    if tok.constraints.get('swap') == 'short_or_long':
        prose = str(getattr(source, 'descricao', '') or '')
        stem = tok.kind.split('_')[0]
        if (len(stem) >= 5 and re.search(r'\bescolher um novo\s+' + re.escape(stem),
                                          prose, re.I)
                and re.search(r'Descanso Curto.*Descanso Longo', prose, re.I | re.S)):
            listing = re.search(r'\bt[eé]cnicas\s*:\s*([^.;\n]+)', prose, re.I)
            if listing:
                names = re.findall(r'([\wÀ-ÿ]+)\s*\([^()]+\)', listing.group(1))
                slugs = [slugify(name) for name in names]
                if len(slugs) >= 3 and len(slugs) == len(set(slugs)):
                    return [{'id': None, 'slug': slug, 'nome': name,
                             'descricao': '', 'pre': ''}
                            for slug, name in zip(slugs, names)]

    # A counted legacy pick may name the category while the same sentence
    # enumerates every option in bold: "escolha um tipo de Terreno ...: **A**,
    # **B** ou **C**". Match the category to the pick kind so unrelated lists
    # on the page cannot become its universe.
    for line in str(getattr(source, 'descricao', '') or '').splitlines():
        statement = re.search(
            r'\bescolha\s+um\s+tipo\s+de\s+([\wÀ-ÿ]+)[^:\n]*:\s*([^.;\n]+)',
            line, re.I)
        if not statement or slugify(statement.group(1)).replace('-', '_') != tok.kind:
            continue
        listing = statement.group(2).strip()
        if not re.fullmatch(
                r'\*\*[^*]+\*\*(?:\s*,\s*\*\*[^*]+\*\*)+\s+ou\s+\*\*[^*]+\*\*',
                listing, re.I):
            continue
        names = re.findall(r'\*\*([^*]+)\*\*', listing)
        if len(names) < 3 or any('\ufffd' in name for name in names):
            continue
        return [{'id': None, 'slug': slugify(name), 'nome': name,
                 'descricao': '', 'pre': ''} for name in names]

    kind_parts = [part for part in tok.kind.split('_') if len(part) >= 5]
    for line in str(getattr(source, 'descricao', '') or '').splitlines():
        heading = re.match(r'^\s*-\s*\*\*([^*]+)\*\*\s*:?\s*(.+)$', line)
        if not heading or not slugify(heading.group(1)).startswith('escolha'):
            continue
        heading_slug = slugify(heading.group(1)).replace('-', '_')
        if not any(part in heading_slug for part in kind_parts):
            continue
        listing = re.search(r'\bentre:\s*([^.;\n]+)', heading.group(2), re.I)
        if not listing:
            continue
        names = [name.strip(' *') for name in re.split(r',\s*|\s+ou\s+', listing.group(1), flags=re.I)]
        if len(names) < 3 or any(not name for name in names):
            continue
        slugs = [slugify(name) for name in names]
        if any(not slug for slug in slugs) or len(set(slugs)) != len(slugs):
            continue
        return [{'id': None, 'slug': slug, 'nome': name, 'descricao': '', 'pre': ''}
                for slug, name in zip(slugs, names)]
    # Some sealed features omitted `de [...]` but explicitly say "escolher
    # **dois ...** dentre: **A**, **B** ou **C**". Require the only actionable
    # pick on that feature, the same count in prose and tag, and a complete
    # bold list. This also works when old prose lost accents in its noun.
    count_words = {'um': 1, 'uma': 1, 'dois': 2, 'duas': 2,
                   'tres': 3, 'três': 3, 'quatro': 4}
    actionable = [pick for tag in getattr(source, 'tags_json', None) or []
                  for pick in iter_pick_tokens(_strip_define_bodies(str(tag)))]
    if len(actionable) != 1 or actionable[0].kind != tok.kind:
        return []
    for line in str(getattr(source, 'descricao', '') or '').splitlines():
        statement = re.search(
            r'\bescolher\s+\*\*(um|uma|dois|duas|tres|três|quatro)\b[^*]*\*\*\s+dentre:\s*([^.;\n]+)',
            line, re.I)
        if not statement or str(count_words[statement.group(1).lower()]) != tok.count_expr:
            continue
        listing = statement.group(2).strip()
        if not re.fullmatch(r'\*\*[^*]+\*\*(?:\s*,\s*\*\*[^*]+\*\*)*\s+ou\s+\*\*[^*]+\*\*',
                            listing, re.I):
            continue
        names = re.findall(r'\*\*([^*]+)\*\*', listing)
        if len(names) < 3 or any('\ufffd' in name for name in names):
            continue
        slugs = [slugify(name) for name in names]
        if any(not slug for slug in slugs) or len(set(slugs)) != len(slugs):
            continue
        return [{'id': None, 'slug': slug, 'nome': name, 'descricao': '', 'pre': ''}
                for slug, name in zip(slugs, names)]
    return []


def _missing_page_menu_options(source, kind, options):
    """Complete a frozen inline menu from its own explicitly enumerated page.

    The section must match the pick category and already contain at least two
    tagged entries. Unrelated prose therefore cannot create a builder choice.
    """
    from django.utils.text import slugify

    description = str(getattr(source, 'descricao', '') or '')
    category = [part.rstrip('s') for part in (kind or '').split('_') if len(part) >= 5]
    if not description or not category:
        return []
    existing = {str(option['slug']).partition('|')[0] for option in options}
    stopwords = {'a', 'o', 'as', 'os', 'de', 'do', 'da', 'dos', 'das', 'e'}

    def normalized(value):
        return '_'.join(part for part in slugify(value.replace('_', '-')).split('-')
                        if part not in stopwords)

    for section in re.finditer(r'(?m)^#{3,6}\s+(.+?)\s*$', description):
        if not any(part in normalized(section.group(1)) for part in category):
            continue
        next_section = re.search(r'(?m)^#{1,6}\s+', description[section.end():])
        end = section.end() + next_section.start() if next_section else len(description)
        names = []
        for line in description[section.end():end].splitlines():
            match = re.match(
                r'^\s*-\s*\*\*(?:\[([^\]]+)\]\([^)]*\)|([^:*]+)):\*\*', line)
            if match:
                names.append(((match.group(1) or match.group(2)).strip(),
                              line[match.end():].strip().replace('**', '')))
        if len(names) < 3:
            continue
        matched, additions = 0, []
        for name, detail in names:
            slug = normalized(name)
            if not slug:
                continue
            if any(current == slug or current.startswith(slug + '_')
                   or slug.startswith(current + '_')
                   for current in (normalized(old) for old in existing)):
                matched += 1
            else:
                additions.append({'id': None, 'slug': slug, 'nome': name,
                                  'descricao': detail, 'pre': ''})
        if matched >= 2 and len({item['slug'] for item in additions}) == len(additions):
            return additions
    return []


def _menu_universe(ctx):
    """Universo de um pick de MENU: define{list} irmão OU enumeração inline na cauda."""
    constraints = ctx.get('constraints') or {}
    source_menu = constraints.get('from_menu')
    if source_menu:
        return _menu_options_from_define(ctx.get('source'), source_menu,
                                         class_level=ctx.get('nivel'))
    opts = _menu_options_from_define(ctx.get('source'), ctx.get('kind'),
                                     class_level=ctx.get('nivel'))
    if opts:
        opts += _missing_page_menu_options(ctx.get('source'), ctx.get('kind'), opts)
    else:
        tok = ctx.get('token')
        if tok is None:
            return []
        opts = (_inline_menu_options(tok, ctx.get('escolhas'))
                or _listed_menu_options(ctx.get('source'), tok)
                or _paired_prepared_spell_options(ctx.get('source'), tok)
                or _legacy_description_menu_options(ctx.get('source'), tok))
    known_kind = constraints.get('from_known')
    personagem = ctx.get('personagem')
    if known_kind and personagem is not None:
        known = set(personagem.escolhas.filter(tipo=known_kind).values_list('valor', flat=True))
        if not known:
            # Keep an older prepared choice visible until it is seeded as known.
            known.update(personagem.escolhas.filter(tipo=ctx.get('kind')).values_list('valor', flat=True))
        opts = [option for option in opts if option['slug'] in known]
    elif known_kind:
        opts = []
    return opts


def _save_prof_universe(ctx):
    """Inline save choices, optionally excluding saves already proficient."""
    options = _menu_universe(ctx)
    raw = str(ctx.get('tag_text') or '')
    personagem = ctx.get('personagem')
    if personagem is None or not re.search(
            r'requires\s*:\s*not\s*\{\s*prof\s*\}', raw):
        return options
    from .character_engine import derive
    key_by_slug = {
        'str': 'FOR', 'dex': 'DES', 'con': 'CON',
        'int': 'INT', 'wis': 'SAB', 'cha': 'CAR',
    }
    saves = derive(personagem).get('saves') or {}
    return [option for option in options
            if not (saves.get(key_by_slug.get(option.get('slug'))) or {}).get('proficiente')]


def _strip_define_bodies(text):
    """Remove os corpos `define{...}` de um texto (contagem balanceada). O menu de um
    pick (a `list{}`/ramos dentro do define) NÃO deve ser varrido por iter_pick_tokens
    como se fossem picks IRMÃOS — senão os sub-picks de uma opção (ex.: Doutrina Marcial
    `armas_treinadas:{pick:arma:3}`) VAZAM como grupos independentes. O pick EXTERNO fica
    fora do define e é preservado; o universo já é lido por _menu_options_from_define."""
    for _ in range(40):
        m = re.search(r'define\s*\{', text)
        if not m:
            break
        close = _match_brace(text, m.end() - 1)
        if close < 0:
            break
        text = text[:m.start()] + text[close + 1:]
    return text


def _menu_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha
    tipo = group['persist_tipo']
    origem = str(group.get('origem') or tipo)[:150]
    base = int(group.get('slot_base') or 0)
    universo = {str(u['slug']) for u in group.get('universo', [])}
    for i, v in enumerate(valores):
        if str(v) not in universo:
            continue
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem, tipo=tipo, slot=base + i,
            defaults={'valor': str(v)})


def _menu_readback(personagem, group):
    if personagem is None:
        return []
    tipo = group['persist_tipo']
    origem = str(group.get('origem') or tipo)[:150]
    nomes = {u['slug']: u['nome'] for u in group.get('universo', [])}
    out = []
    for e in personagem.escolhas.filter(tipo=tipo, origem=origem).order_by('slot'):
        out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor,
                    'nome': nomes.get(e.valor, e.valor)})
    return out


def _truque_universe(ctx):
    """Cantrips from the live or pinned spell catalog."""
    from .models import TbMagia
    ruleset = ctx.get('ruleset')
    if ruleset is not None:
        from .versioned_spells import spell_catalog
        spells = (spell for spell in spell_catalog(ruleset).values()
                  if int(spell.nivel or 0) == 0)
    else:
        spells = TbMagia.objects.filter(nivel=0)
    return [{'id': None, 'slug': spell.slug, 'nome': spell.nome,
             'descricao': spell.descricao or '', 'pre': ''}
            for spell in sorted(spells, key=lambda spell: (spell.nome, spell.slug))]


def _spell_universe(ctx):
    """Spells already acquired in the class spellbook at the declared circle."""
    from .models import TbMagia

    personagem = ctx.get('personagem')
    classe = ctx.get('classe')
    raw = (ctx.get('constraints') or {}).get('raw') or ''
    circle = re.search(r'circulo\s*:\s*(\d+)', raw)
    if not (personagem and classe and circle and re.search(r'\bde\s*:\s*grimorio\b', raw)):
        return []
    level = int(circle.group(1))
    ruleset = ctx.get('ruleset')
    if ruleset is not None:
        from .versioned_spells import spell_catalog
        catalog = spell_catalog(ruleset)
    else:
        catalog = None
    options = {}
    for owned in personagem.magias.filter(
            origem__iexact=classe.nome, nivel=level,
            sempre_preparada=False).select_related('id_magia'):
        spell = catalog.get(owned.id_magia_id) if catalog is not None else owned.id_magia
        if spell and int(spell.nivel or 0) == level:
            options[spell.slug] = spell
    return [{'id': spell.pk, 'slug': spell.slug, 'nome': spell.nome,
             'descricao': spell.descricao or '', 'pre': ''}
            for spell in sorted(options.values(), key=lambda spell: (spell.nome, spell.slug))]


def _spell_readback(personagem, group):
    allowed = {option['slug'] for option in group.get('universo', [])}
    return [row for row in _menu_readback(personagem, group)
            if row['valor'] in allowed]


def _spell_persist(personagem, group, valores):
    """Reuse slots whose spell left the book, retaining character and choice IDs."""
    from .models import TbPersonagemEscolha

    origin = str(group.get('origem') or 'spell')[:150]
    allowed = {option['slug'] for option in group.get('universo', [])}
    stale = list(personagem.escolhas.filter(
        tipo='spell', origem=origin).exclude(valor__in=allowed).order_by('slot'))
    next_slot = int(group.get('slot_base') or 0)
    for value in valores:
        if value not in allowed:
            continue
        if stale:
            row = stale.pop(0)
            row.valor = value
            row.save(update_fields=['valor'])
        else:
            TbPersonagemEscolha.objects.update_or_create(
                id_personagem=personagem, origem=origin, tipo='spell', slot=next_slot,
                defaults={'valor': value})
            next_slot += 1


_MENU_ENTRY = {
    'sink': 'escolha',
    'menu': True,
    'universe': _menu_universe,
    'persist': _menu_persist,
    'validate': _default_validate,
    'readback': _menu_readback,
}

# Kinds ligados por um FLUXO DEDICADO (não pelo painel genérico de escolhas):
#   `vertente` — escolhida no passo de Essência do CRIADOR, persistida por lá
#     (tipo='vertente') e lida pelo derive via _collect_escolhas; nunca deve virar
#     pendência genérica (evita pendência-fantasma p/ quem já a escolheu, ex.: Scar).
#   `attr` — `pick:attr:{...}:+1` é o Aumento de Atributo (ASI), 100% resolvido pelos
#     campos booleanos do talento + TbPersonagemAtributoBonus (fluxo _lvl_aplicar_asi),
#     fora de tags_json; não é um menu de escolha de build.
_DEDICATED_KINDS = frozenset({'vertente', 'attr'})


PICK_REGISTRY = {
    'spell': {
        'sink': 'escolha', 'label': 'Magia do Grimório', 'menu': True,
        'universe': _spell_universe, 'persist': _spell_persist,
        'validate': _default_validate, 'readback': _spell_readback,
    },
    'truque': {
        'sink': 'escolha', 'label': 'Truque', 'menu': True,
        'universe': _truque_universe, 'persist': _menu_persist,
        'validate': _default_validate, 'readback': _menu_readback,
    },
    'idioma': {
        'sink': 'proficiencia',
        'label': 'Idioma',
        'universe': _idioma_universe,
        'persist': _idioma_persist,
        'validate': _idioma_validate,
        'readback': _idioma_readback,
    },
    'opcao': {
        'sink': 'escolha',
        'universe': _opcao_universe,
        'persist': _opcao_persist,
        'validate': _default_validate,
        'readback': _opcao_readback,
    },
    'arma': {
        'sink': 'escolha',
        'label': 'Maestria de Arma',
        'universe': _arma_universe,
        'persist': _arma_persist,
        'validate': _arma_validate,
        'readback': _arma_readback,
    },
    'pericia': {
        'sink': 'escolha',
        'label': 'Perícia',
        'universe': _pericia_universe,
        'persist': _pericia_persist,
        'validate': _default_validate,
        'readback': _pericia_readback,
    },
    'pericia_expertise': {
        'sink': 'escolha',
        'label': 'Especialização',
        'universe': _pericia_expertise_universe,
        'persist': _pericia_expertise_persist,
        'validate': _default_validate,
        'readback': _pericia_expertise_readback,
    },
    'ferramenta': {
        'sink': 'proficiencia',
        'label': 'Ferramenta',
        'universe': _ferramenta_universe,
        'persist': _ferramenta_persist,
        'validate': _ferramenta_validate,
        'readback': _ferramenta_readback,
    },
    # kind 'talento' (+ alias 'talento_de_origem'): escolha de um TbTalento concedido por
    # feature (Determinação Comum, Raízes Profundas, Aprendizado dos Antigos…). O universo
    # honra as constraints da tag; persiste em TbPersonagemTalento + TbPersonagemEscolha.
    'talento': {
        'sink': 'escolha',
        'label': 'Talento',
        'universe': _talento_universe,
        'persist': _talento_persist,
        'validate': _default_validate,
        'readback': _talento_readback,
    },
    'talento_de_origem': {
        'sink': 'escolha',
        'label': 'Talento de Origem',
        'universe': _talento_universe,
        'persist': _talento_persist,
        'validate': _default_validate,
        'readback': _talento_readback,
    },
    'save_prof': {
        'sink': 'escolha',
        'label': 'Salvaguarda',
        'menu': True,
        'universe': _save_prof_universe,
        'persist': _menu_persist,
        'validate': _default_validate,
        'readback': _menu_readback,
    },
}


# ---------------------------------------------------------------------------
# Resolvedor — varre features e devolve os grupos normalizados.
# ---------------------------------------------------------------------------
def _persist_tipo_for(kind, tipo, is_menu=False):
    """Chave `tipo` gravada em TbPersonagemEscolha. `opcao:<sub>` grava o slug do sub
    (ex.: 'estilo_de_luta', 'metamagia'); `arma` grava 'maestria' (compat com o engine);
    `pericia` grava sempre 'pericia' (o sub, quando existe, é a lista de restrição).
    MENU inline grava sempre o KIND — para esses o `sub` é a LISTA de opções
    (`{int|wis|cha}`), não um subuniverso, e não pode virar chave de persistência."""
    if kind == 'arma':
        return 'maestria'
    if kind == 'pericia':
        return 'pericia'
    if kind == 'ferramenta':
        return 'ferramenta'
    if is_menu:
        return kind
    return tipo or kind


def _legacy_subclass_bonus_defaults(source, subclasse, token):
    """Recover an old page's two named additional styles from frozen prose."""
    if (token.kind != 'opcao' or token.count_expr != '2' or subclasse is None
            or getattr(source, 'id_subclasse_id', None) != subclasse.pk):
        return []
    description = str(getattr(source, 'descricao', '') or '')
    match = re.search(
        r'aprende os Estilos de Ki\s+([\wÀ-ÿ]+)\s+e\s+([\wÀ-ÿ]+)'
        r'\s*\(se já possuir[^)]*escolha outro(?: Estilo)?',
        description, re.I)
    if not match:
        return []
    from django.utils.text import slugify
    return [slugify('Estilo ' + name) for name in match.groups()]


def _build_group(token, source, classe, subclasse, nivel, personagem, escolhas_map, entry,
                 tag_text='', choice_values=None, ruleset=None):
    from .character_engine import _feature_identity
    tipo = token.sub
    n = count_for(token.count_expr, nivel, classe, token.resource_ref, ruleset=ruleset)
    optional = token.kind == 'opcao' and tipo == 'item_magico'
    if optional and personagem is not None:
        known = personagem.escolhas.filter(tipo='infusao')
        if personagem.classes.count() > 1:
            known = known.filter(origem__startswith='%s:' % classe.nome)
        maximum = resource_limit(classe, nivel, 'infusoes_conhecidas', ruleset=ruleset)
        n = min(known.count(), maximum or 0)
    if not n or n <= 0:
        return None
    constraints = dict(token.constraints or {})
    if token.kind == 'pericia_expertise' and constraints.get('requires') == 'already_expertise':
        from .character_engine import (
            _feature_talent_attr_sig, _talent_attr_map,
        )
        match = re.search(r'requires:already_expertise\{([a-z0-9_-]+)\}',
                          constraints.get('raw') or '')
        tags = getattr(source, 'tags_json', None) or []
        if (personagem is None or match is None or not _feature_identity(source)
                or (any('attr:talent_attr_score+' in str(tag) for tag in tags)
                    and not _feature_talent_attr_sig(source, _talent_attr_map(personagem)))
                or not _prior_expertise(personagem, source, match.group(1))):
            return None
    # Legacy subclass pages use ``(<subclass slug>)`` to replace the class
    # option catalog and add a choice. Interpret the frozen declaration
    # against its own option ACL without changing the snapshot.
    subclass_replacement = bool(
        token.kind == 'opcao' and subclasse is not None
        and getattr(source, 'id_subclasse_id', None) == subclasse.pk
        and constraints.get('raw', '').strip() == '(%s)' % subclasse.slug
        and re.search(r'substitu[ií]d', str(getattr(source, 'descricao', '') or ''), re.I))
    if subclass_replacement:
        constraints['subclass_only'] = True
    defaults = constraints.get('default_slugs') or _legacy_subclass_bonus_defaults(
        source, subclasse, token)
    seed_from = constraints.get('seed_from')
    if seed_from and personagem is not None:
        defaults = list(dict.fromkeys(defaults + list(
            personagem.escolhas.filter(tipo=seed_from).values_list('valor', flat=True))))
    bonus_count = constraints.get('add') or (len(defaults) if defaults else 0)
    if seed_from:
        bonus_count = 0
    source_slug = _page_option_source(source, token)
    if source_slug:
        constraints.update(from_kind='classe', from_slug=source_slug)
    ctx = {
        'personagem': personagem, 'classe': classe, 'subclasse': subclasse, 'nivel': nivel,
        'kind': token.kind, 'tipo': tipo, 'constraints': constraints,
        'tag_text': tag_text, 'source': source, 'token': token,
        'escolhas': choice_values or {}, 'ruleset': ruleset,
    }
    universo = entry['universe'](ctx)
    if bonus_count and (bonus_count != len(defaults) or
                        not set(defaults) <= {o['slug'] for o in universo}):
        raise ValueError('Declared additional options are absent from the catalog.')
    learned_replica = (token.kind == 'opcao' and tipo == 'item_magico'
                       and personagem is not None
                       and personagem.escolhas.filter(
                           tipo='infusao', valor__startswith='item_magico:').exists())
    if not universo and not learned_replica and (ruleset is None or
                                                 (token.kind == 'opcao' and tipo == 'item_magico')):
        return None
    persist_tipo = _persist_tipo_for(token.kind, tipo, is_menu=bool(entry.get('menu')))
    # Rótulo: kinds com rótulo FIXO no registry (`arma`, `pericia`) usam-no; `opcao` deriva
    # o rótulo do tipo exibido; menu inline (`define{list}`) rotula pelo próprio kind.
    # `arma` não expõe tipo_display (tem painel próprio).
    label_fixo = entry.get('label')
    if token.kind == 'arma':
        tipo_display, label = None, label_fixo
    elif entry.get('menu'):  # pick genérico de menu inline (universo no define{list})
        tipo_display, label = None, _pretty_kind(token.kind)
    elif label_fixo:
        tipo_display, label = label_fixo, label_fixo
    else:  # opcao — rótulo dinâmico do tipo
        if ruleset is not None:
            from .versioned_options import VersionedOptions
            tipo_display = VersionedOptions(ruleset).type_map().get(tipo) or tipo
        else:
            tipo_display = _slug2tipo_map().get(tipo) or tipo
        label = tipo_display
    group = {
        'origem': getattr(source, 'nome', None) or (classe.nome if classe else ''),
        'source_identity': _feature_identity(source) if personagem is not None else '',
        'kind': token.kind, 'tipo': tipo, 'persist_tipo': persist_tipo,
        'optional': optional, 'paired_target_is_choice': optional,
        'increment_existing': subclass_replacement or bool(bonus_count),
        'auto_options': defaults,
        'unique_parent': optional,
        'tipo_display': tipo_display, 'label': label,
        # TROCABILIDADE: sai da TAG (constraint do token ou marcador irmão), nunca de uma
        # lista de tipos trocáveis. `None` = escolha fixa.
        'swap': swap_scope(token, source),
        'n': n, 'universo': universo, 'constraints': constraints,
        'classe_id': (classe.id_classe if classe else None),
        'classe': (classe.nome if classe else ''),
        'sink': entry['sink'], 'ruleset': ruleset,
        'spell_table': bool(
            re.search(r'^\s*\|\s*N[ií]vel[^|]*\|\s*C[ií]rculo',
                      str(getattr(source, 'descricao', '') or ''), re.I | re.M)
            and any('spell_selection:' in str(tag) and 'always_prepared' in str(tag)
                    and 'extra' in str(tag)
                    for tag in (getattr(source, 'tags_json', None) or []))),
    }
    # escolhidas: do personagem (readback) OU do mapa passado (builder sem personagem)
    if personagem is not None:
        escolhidas = entry['readback'](personagem, group)
    else:
        escolhidas = list((escolhas_map or {}).get(persist_tipo)
                          or (escolhas_map or {}).get(normalize_slug(persist_tipo)) or [])
    # Regressao de nivel suspende slots ainda nao desbloqueados sem destruir as
    # escolhas persistidas: ao progredir novamente, o readback recupera todos.
    escolhidas = escolhidas[:n]
    group['escolhidas'] = escolhidas
    group['usados'] = len(escolhidas)
    group['pendentes'] = max(0, n - len(escolhidas))
    group['slot_base'] = 0
    group['prox_slot'] = max([e.get('slot', -1) for e in escolhidas], default=-1) + 1
    return group


def _entry_for_token(tok, source, choice_values=None):
    """REGISTRY entry de um token pick papel-A. Kinds fixos vêm do PICK_REGISTRY; um
    `pick:<kind>` cujo universo mora num `define{<kind>: list{...}}` IRMÃO **ou** numa
    enumeração INLINE na cauda do token (`(={a|b}), :{a|b|c}, =match(var){...}`) usa o
    handler genérico de menu (`_MENU_ENTRY`). Kinds de fluxo DEDICADO (`vertente`) e sem
    universo -> None (ref/efeito/combate/futuro)."""
    if tok.kind in _DEDICATED_KINDS:
        return None
    if tok.kind in PICK_REGISTRY:
        return PICK_REGISTRY[tok.kind]
    if ((tok.constraints or {}).get('from_menu')
            or _menu_options_from_define(source, tok.kind)
            or _inline_menu_options(tok, choice_values)
            or _listed_menu_options(source, tok)
            or _paired_prepared_spell_options(source, tok)
            or _legacy_description_menu_options(source, tok)):
        return _MENU_ENTRY
    return None


def _paired_known_formula(source):
    """A page's counted formula source and its prepared menu share one catalog."""
    tags = [str(tag) for tag in getattr(source, 'tags_json', None) or []]
    for tag in tags:
        match = re.search(
            r'spell_selection:fonte:([a-z0-9_]+)\s*\{\s*qtd:\s*(\{[^}]+\})',
            tag)
        if not match:
            continue
        stem = match.group(1).rstrip('s')
        prepared = stem + '_preparado'
        if (any(re.search(r'\bpick:' + re.escape(prepared) + r':', item)
                for item in tags)
                and _menu_options_from_define(source, prepared)):
            return stem + '_conhecido', prepared, match.group(2)
    return None


def _legacy_guarded_rune_pick(source):
    """Recover a rest choice from an old ability-rune guard reference and its page.

    The frozen tag names the guarded rune but predates a build-choice menu.  Use
    only an explicit four-row rune table and both rest triggers on that same
    page; activation-only rune references must not become permanent choices.
    """
    from django.utils.text import slugify

    tags = [str(tag) for tag in getattr(source, 'tags_json', None) or []]
    if not any(re.search(r'pick:ability\{[^{}]+\}\.runa:1\(guard\)', tag)
               for tag in tags):
        return None
    if 'trigger=on{short_rest, long_rest}' not in tags:
        return None
    prose = str(getattr(source, 'descricao', '') or '')
    heading = re.search(r'(?m)^- \*\*(Runa Guardi[ãa])\.\*\*', prose)
    if not heading or not re.search(r'Descanso Curto.*Descanso Longo', prose, re.I):
        return None
    slugs = []
    for cell in re.findall(r'(?m)^\|\s*\*\*([^*|]+)\*\*\s*\|', prose):
        rune = re.fullmatch(r'Runa d(?:a|as|o|os)\s+(.+)',
                            cell.split('(')[0].strip(), re.I)
        if rune:
            slugs.append(slugify(rune.group(1)))
    if len(slugs) != 4 or len(set(slugs)) != 4:
        return None
    kind = slugify(heading.group(1)).replace('-', '_')
    return 'pick:%s:1(={%s},swap:short_or_long)' % (kind, '|'.join(slugs))


def _legacy_rest_attunement_pick(source):
    """Recover a frozen rest choice only when its own page names both options.

    Old tags placed this pick inside ``instant{}``, where the builder correctly
    ignores activation choices. A page that explicitly attunes an aspect at a
    rest instead needs one persistent, rest-swappable character choice.
    """
    from django.utils.text import slugify

    tags = [str(tag) for tag in getattr(source, 'tags_json', None) or []]
    matches = [re.fullmatch(
        r'trigger=short_rest,\s*trigger=long_rest,\s*instant\{\s*'
        r'pick:([a-z][a-z0-9_]+):1\s*\}', tag)
        for tag in tags]
    kinds = [match.group(1) for match in matches if match]
    if len(kinds) != 1:
        return None
    prose = str(getattr(source, 'descricao', '') or '')
    statement = re.search(
        r'Ao terminar um \*\*Descanso Curto ou Longo\*\*,\s*'
        r'[^.\n]*?\bsintoniza\b[^.\n]*?\bao\s+([\wÀ-ÿ]+)\s+'
        r'\*\*([^*]+)\*\*\s+ou\s+\*\*([^*]+)\*\*', prose, re.I)
    if not statement or slugify(statement.group(1)) != kinds[0].split('_')[-1]:
        return None
    options = [slugify(statement.group(i)) for i in (2, 3)]
    if not all(options) or len(set(options)) != 2:
        return None
    return 'pick:%s:1(={%s},swap:short_or_long)' % (
        kinds[0], '|'.join(options))


def registry_entry(kind):
    """Entry (persist/validate/readback) de um grupo JÁ resolvido. Kinds fixos vêm do
    PICK_REGISTRY; qualquer kind de MENU (define/inline) usa o _MENU_ENTRY genérico. Usado
    pelas views ao persistir/validar sem re-inspecionar a fonte (o grupo só existe porque
    _entry_for_token já o admitiu)."""
    return PICK_REGISTRY.get(kind, _MENU_ENTRY)


def resolve_groups(sources, *, classe=None, subclasse=None, nivel=1,
                   personagem=None, escolhas_map=None, kinds=None, choice_values=None,
                   ruleset=None):
    """Varre `sources` (objetos com .tags_json/.nome), extrai os picks papel-A e devolve
    a lista de grupos normalizados (um por (kind,sub,classe) distinto). `kinds` filtra os
    kinds considerados; None = todos. `choice_values` = mapa var->valor das escolhas JÁ
    feitas (p/ resolver o universo DEPENDENTE de `=match(<var>){...}`, ex.: sangue×vertente).

    DEDUP POR MAIOR CONTAGEM: quando a MESMA escolha reaparece em várias features/tokens
    da classe (ex.: Metamagia declarada no nv2, nv10 e nv17, cada uma com uma fórmula de
    contagem), o grupo fica com a MAIOR contagem aplicável ao nível (`count_for`) — NÃO a
    primeira vista. Sem isto, o literal `pick:opcao:metamagia:2` (primeiro token) travava a
    progressão em 2 e a fórmula `{classlvl=..}` que concede mais era descartada."""
    classe_id = classe.id_classe if classe else None
    grupos = []
    por_chave = {}  # chave -> índice em `grupos` (dedup pela MAIOR contagem)
    for source in sources:
        source_tags = list(getattr(source, 'tags_json', None) or [])
        guarded_rune = _legacy_guarded_rune_pick(source) if ruleset is not None else None
        if guarded_rune and not any('pick:' + guarded_rune.split(':')[1] + ':' in str(tag)
                                    for tag in source_tags):
            source_tags.insert(0, guarded_rune)
        rest_attunement = (_legacy_rest_attunement_pick(source)
                            if ruleset is not None else None)
        if rest_attunement:
            rest_kind = rest_attunement.split(':')[1]
            if not any(tok.kind == rest_kind for tag in source_tags
                       for tok in iter_pick_tokens(str(tag))):
                source_tags.insert(0, rest_attunement)
        paired_formula = _paired_known_formula(source)
        if paired_formula:
            known_kind, prepared_kind, count_expr = paired_formula
            if not any(re.search(r'\bpick:' + re.escape(known_kind) + r':', str(tag))
                       for tag in source_tags):
                swap_on_gain = bool(re.search(
                    r'sempre que aprender.{0,120}substituir',
                    str(getattr(source, 'descricao', '') or ''), re.I | re.S))
                source_tags.insert(0, 'pick:%s:%s(from_menu:%s,seed_from:%s%s)' % (
                    known_kind, count_expr, prepared_kind, prepared_kind,
                    ',swap:level_up,on_gain:1' if swap_on_gain else ''))
        define_branches = list(_selected_define_branches(source_tags, choice_values))
        declared = {m.group(1) for raw in source_tags
                    for m in re.finditer(r'(?<![a-z_-])pick:([a-z][a-z0-9_]+)', str(raw))}
        for tag, from_define in ([(raw, False) for raw in source_tags]
                                 + [(branch, True) for branch in define_branches]):
            # Picks inside match branches are offered only for the selected branch.
            # Match expressions inside a pick's own constraints are its option
            # source, not a branch to collapse before parsing that pick.
            tag = str(tag)
            pick_spans = [token.span for token in iter_pick_tokens(tag)]
            for match in reversed(list(re.finditer(
                    r'match\((?:pick:)?([a-z][a-z0-9_]+)\)\s*\{', tag))):
                variable = match.group(1)
                if variable not in declared:
                    continue
                if any(start <= match.start() < end for start, end in pick_spans):
                    continue
                end = _match_brace(tag, match.end() - 1)
                if end < 0:
                    continue
                from .character_engine import _resolve_match
                branch = _resolve_match(tag[match.start():end + 1],
                                        {variable: (choice_values or {}).get(variable)},
                                        outer_only=True)
                tag = tag[:match.start()] + branch + tag[end + 1:]
            # O corpo dos define{} é o MENU do próprio pick — não deve ser varrido como
            # picks IRMÃOS (senão sub-picks de uma opção, ex.: Doutrina Marcial
            # `armas_treinadas:{pick:arma:3}`, vazam como grupos independentes). O pick
            # EXTERNO fica fora do define e é preservado; o universo é lido da fonte crua.
            for tok in iter_pick_tokens(_strip_define_bodies(tag)):
                if kinds is not None and tok.kind not in kinds:
                    continue
                if paired_formula and tok.kind == paired_formula[1]:
                    tok.constraints['from_known'] = paired_formula[0]
                    # Old frozen pages wrote the prepared limits as absolute
                    # milestones (1, 2, 3), not cumulative grants.
                    if not re.search(r'[+-]\d+', tok.count_expr or ''):
                        milestones = [int(value) for level, value in re.findall(
                            r'classlvl\s*=\s*(\d+)\s*:\s*(\d+)', tok.count_expr or '')
                                      if int(level) <= nivel]
                        if milestones:
                            tok.count_expr = str(milestones[-1])
                entry = _entry_for_token(tok, source, choice_values)
                if (entry is None and ruleset is not None
                        and tok.kind not in _DEDICATED_KINDS
                        and any(previous['kind'] == tok.kind
                                and previous['tipo'] == tok.sub
                                and previous['classe_id'] == classe_id
                                and previous['universo'] for previous in grupos)):
                    # A sealed later feature can raise the count of an earlier
                    # menu without repeating its option list.
                    entry = _MENU_ENTRY
                if entry is None:
                    continue  # kind não registrado e sem define/inline -> ignora
                g = _build_group(tok, source, classe, subclasse, nivel,
                                 personagem, escolhas_map, entry, tag_text=tag,
                                 choice_values=choice_values, ruleset=ruleset)
                if g is None:
                    continue
                if from_define:
                    g['increment_existing'] = True
                # Picks de perÃ­cia pertencem Ã  FEATURE que os concedeu: Conhecimento
                # Primitivo e PresenÃ§a Intimidante, por exemplo, sÃ£o dois slots distintos.
                # OpÃ§Ãµes de progressÃ£o (Metamagia etc.) continuam deduplicadas por kind/sub.
                # Traços e talentos distintos podem conceder o mesmo kind (ex.:
                # Poliglota + Linguista + Contratos e Decretos). Só escolhas da
                # mesma fonte devem compartilhar os slots nesse caso. Para
                # classe, a deduplicação por kind continua permitindo que uma
                # feature posterior amplie o limite da mesma escolha.
                source_key = None
                if classe is None or tok.kind in ('pericia', 'pericia_expertise'):
                    source_key = (getattr(getattr(source, '_meta', None),
                                          'label_lower', type(source).__name__),
                                  getattr(source, 'pk', id(source)))
                chave = (tok.kind, tok.sub, classe_id, source_key)
                idx = por_chave.get(chave)
                if idx is not None and g.get('increment_existing'):
                    g['n'] += grupos[idx]['n']
                if idx is None:
                    por_chave[chave] = len(grupos)
                    grupos.append(g)
                elif g['n'] > grupos[idx]['n']:
                    # A feature que amplia a contagem preserva a identidade de
                    # persistencia da escolha inicial (ex.: Terreno N3 -> N18).
                    g['origem'] = grupos[idx]['origem']
                    # Se a pagina posterior apenas amplia os slots, mantenha o
                    # universo e a troca declarados pela primeira pagina.
                    if not g['universo'] and grupos[idx]['universo']:
                        g['universo'] = grupos[idx]['universo']
                    if not g['swap']:
                        g['swap'] = grupos[idx]['swap']
                    g['spell_table'] = g['spell_table'] or grupos[idx]['spell_table']
                    if personagem is not None:
                        g['escolhidas'] = entry['readback'](personagem, g)
                        g['usados'] = len(g['escolhidas'])
                        g['pendentes'] = max(0, g['n'] - g['usados'])
                        g['prox_slot'] = max(
                            [e.get('slot', -1) for e in g['escolhidas']], default=-1) + 1
                    grupos[idx] = g  # a MAIOR fórmula aplicável vence (não a primeira)
    return grupos


def builder_sources(classe, *, ruleset=None):
    """Features de nível 1 de uma classe (classe + habilidades N1 sem subclasse)."""
    from .models import TbClassehabilidade
    from .tag_engine import evaluate_tags, parse_tags
    if not classe:
        return []
    if ruleset is not None:
        from .versioned_classes import VersionedClassCatalog
        catalog = VersionedClassCatalog(ruleset, classe.pk)
        classe = catalog.classe
        features = [feature for _, _, feature, _ in catalog.features(1)]
    else:
        features = list(TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True, niveladquirido=1))
    source_tags = getattr(classe, 'tags_json', None) or []
    multiclass_raw = {
        operation.raw for operation in evaluate_tags(source_tags).operations
        if (operation.op, operation.target)
        == ('grant_proficiency', 'multiclasse.proficiencias')
    }
    class_tags = [
        node.raw for node in parse_tags(source_tags).nodes
        if node.raw and node.raw not in multiclass_raw
    ]
    initial_class = SimpleNamespace(nome=classe.nome, tags_json=class_tags)
    return [initial_class] + features


def multiclass_sources(classe):
    """Expose only picks nested in multiclass_prof for a secondary class."""
    from .tag_engine import evaluate_tags
    tags = []
    for operation in evaluate_tags(
            getattr(classe, 'tags_json', None) or []).operations:
        if ((operation.op, operation.target)
                != ('grant_proficiency', 'multiclasse.proficiencias')):
            continue
        values = (operation.value if isinstance(operation.value, list)
                  else [operation.value])
        tags.extend(str(value) for value in values if value)
    return [SimpleNamespace(
        nome='Multiclasse: %s' % classe.nome,
        tags_json=tags,
    )] if tags else []


def resolve_builder(classe, *, escolhas_map=None, kinds=None, ruleset=None):
    """Grupos de escolha do CRIADOR (nível 1, sem personagem ainda)."""
    if ruleset is not None:
        from .versioned_classes import VersionedClassCatalog
        catalog = VersionedClassCatalog(ruleset, classe.pk)
        classe = catalog.classe
    return resolve_groups(builder_sources(classe, ruleset=ruleset), classe=classe, subclasse=None,
                          nivel=1, personagem=None, escolhas_map=escolhas_map, kinds=kinds,
                          ruleset=ruleset)


def _choice_values(personagem):
    """Mapa var->valor (1º slot) das escolhas JÁ persistidas do personagem, p/ resolver o
    universo DEPENDENTE de `=match(<var>){...}` (ex.: `pick:sangue` ramifica pela vertente
    escolhida). Mesma chave `tipo` que o derive lê em _collect_escolhas."""
    out = {}
    if personagem is None:
        return out
    for e in personagem.escolhas.all().order_by('tipo', 'slot'):
        out.setdefault(e.tipo, e.valor)
    return out


def resolve_personagem(personagem, *, kinds=None):
    """Grupos de escolha de um PERSONAGEM (level-up/editar): varre classe+subclasse
    desbloqueada até o nível de cada classe, os TRAÇOS raciais/essência e os TALENTOS do
    personagem. Dedup por (kind,sub,classe)."""
    from .models import TbClassehabilidade
    from .character_engine import _subclass_unlocked, _talentos, _tracos_raciais
    grupos = []
    if personagem is None:
        return grupos
    cvals = _choice_values(personagem)
    for c in personagem.classes.select_related('id_classe', 'id_subclasse', 'ruleset'):
        nivel = int(c.nivel or 0)
        classe = c.id_classe
        ruleset = c.ruleset if c.ruleset_id else None
        if ruleset is None and classe.slug == 'cacador':
            from .models import TbPersonagemCacador
            profile = TbPersonagemCacador.objects.select_related('ruleset').filter(
                personagem_classe=c).first()
            if profile is not None:
                ruleset = profile.ruleset
        if ruleset is not None:
            from .versioned_classes import VersionedClassCatalog
            catalog = VersionedClassCatalog(ruleset, c.id_classe_id)
            classe = catalog.classe
        if ruleset is None:
            habs = list(TbClassehabilidade.objects.filter(
                id_classe=classe, id_subclasse__isnull=True, niveladquirido__lte=nivel))
        else:
            habs = [h for h in catalog.collections[TbClassehabilidade]
                    if h.id_subclasse_id is None and h.niveladquirido <= nivel]
        subclasse = None
        if _subclass_unlocked(c, nivel, ruleset=ruleset):
            subclasse = catalog.subclasses[c.id_subclasse_id] if ruleset else c.id_subclasse
            if ruleset:
                habs += [h for h in catalog.collections[TbClassehabilidade]
                         if h.id_subclasse_id == c.id_subclasse_id and h.niveladquirido <= nivel]
            else:
                habs += list(TbClassehabilidade.objects.filter(
                    id_subclasse=subclasse, niveladquirido__lte=nivel))
        # Para classe secundaria entram somente os picks de multiclass_prof;
        # picks de proficiencia inicial da classe nao podem vazar na multiclasse.
        sources = (multiclass_sources(classe) if not c.principal else []) + habs
        grupos += resolve_groups(sources, classe=classe, subclasse=subclasse, nivel=nivel,
                                 personagem=personagem, kinds=kinds, choice_values=cvals,
                                 ruleset=ruleset)
    # TRAÇOS raciais/linhagem/ESSÊNCIA automáticos (talento_racial=False): sede das
    # SUB-ESCOLHAS de essência (`pick:sangue`, `pick:energia`, `pick:polo`, `pick:elemento`,
    # `pick:alento_elemental`) que hoje viram lixo literal na ficha. `_tracos_raciais` já
    # entrega o objeto-fonte com .tags_json; classe=None (traço não é de classe).
    fontes_traco = [obj for (_o, _f, obj, _cl) in _tracos_raciais(personagem)]
    if fontes_traco:
        grupos += resolve_groups(fontes_traco, classe=None, subclasse=None,
                                  nivel=int(personagem.nivel or 0),
                                  personagem=personagem, kinds=kinds, choice_values=cvals)
    # TALENTOS do personagem (origem/gerais/raciais): antes NUNCA varridos, por isso a
    # Máscara de Guerra (pick via define{list}) e 7+ talentos com pick jamais viravam
    # pendência. Mesma varredura genérica, sem ramo por tipo — classe=None (talento não é
    # de classe) e nível = total (p/ fórmulas classlvl eventuais). `_talentos` já resolve
    # cada TbPersonagemTalento no objeto-fonte com .tags_json (TbTalento OU TbTracoracial).
    fontes_talento = [obj for (_t, _n, obj, _x) in _talentos(personagem)]
    if fontes_talento:
        grupos += resolve_groups(fontes_talento, classe=None, subclasse=None,
                                  nivel=int(personagem.nivel or 0),
                                  personagem=personagem, kinds=kinds, choice_values=cvals)
    return grupos


def resolve_versioned_class_options(ruleset, class_id, *, nivel=1, subclass_id=None,
                                    escolhas_map=None):
    """Resolve class option groups entirely from sealed class and option catalogs.

    Other choice kinds are not covered by this adapter; activation remains gated
    on migrating their own catalogs and the character effect readers.
    """
    from .versioned_classes import VersionedClassCatalog
    catalog = VersionedClassCatalog(ruleset, class_id)
    sources = [catalog.classe] + [h for _, _, h, _ in catalog.features(nivel, subclass_id)]
    groups = {}
    for source in sources:
        for tag in source.tags_json or []:
            for token in iter_pick_tokens(_strip_define_bodies(tag)):
                if token.kind != 'opcao':
                    continue
                group = _build_group(token, source, catalog.classe,
                    catalog.subclasses.get(subclass_id), nivel, None, escolhas_map,
                    PICK_REGISTRY['opcao'], tag_text=tag, ruleset=ruleset)
                if group is not None:
                    key = (token.kind, token.sub)
                    if key not in groups or group['n'] > groups[key]['n']:
                        groups[key] = group
    return list(groups.values())
