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
`match(...)`/`cast(...)`/`spell:pick{...}`.
"""
import re

# ---------------------------------------------------------------------------
# Gramática — UMA regex/parse (substitui as 5 regexes paralelas de views.py).
# ---------------------------------------------------------------------------
# Captura kind + toda a "cauda": sequência de segmentos `:<seg>` e grupos de
# restrição `(<...>)` intercalados (a ordem sub/count/constraint varia na base).
_PICK_RE = re.compile(
    r'pick:([a-z0-9_]+)((?::(?:\{[^}]*\}|[A-Za-z0-9_+\-]+)|\([^)]*\))*)'
)
_TAIL_RE = re.compile(r':(\{[^}]*\}|[A-Za-z0-9_+\-]+)|\(([^)]*)\)')


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


def _ref_spans(text):
    """Spans (start,end) de contextos de REFERÊNCIA (papel B) onde um pick: NÃO é escolha:
    `match(...)`, `cast(...)`, `spell:pick{...}`. Varredura com parênteses/chaves balanceados."""
    spans = []
    for kw, op, cl in (('match(', '(', ')'), ('cast(', '(', ')'), ('spell:pick{', '{', '}')):
        start = 0
        while True:
            i = text.find(kw, start)
            if i < 0:
                break
            j = i + len(kw) - 1  # posição do delimitador de abertura
            depth = 0
            k = j
            while k < len(text):
                if text[k] == op:
                    depth += 1
                elif text[k] == cl:
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            spans.append((i, k))
            start = k + 1
    return spans


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
    """Yields PickToken para cada `pick:` PAPEL-A em `text` (ignora match/cast/spell:pick)."""
    text = str(text)
    refs = _ref_spans(text)
    for m in _PICK_RE.finditer(text):
        start = m.start()
        if any(a <= start <= b for a, b in refs):
            continue  # dentro de match()/cast()/spell:pick{} -> referência, não escolha
        kind = m.group(1)
        tail = m.group(2) or ''
        segs, constr_bodies = [], []
        for tm in _TAIL_RE.finditer(tail):
            if tm.group(1) is not None:
                segs.append(tm.group(1))
            else:
                constr_bodies.append(tm.group(2) or '')
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
        yield PickToken(kind, sub, count_expr, resource_ref, constraints, m.group(0), m.span())


def _parse_constraints(raw):
    raw = raw or ''
    return {
        'raw': raw,
        'swap': (re.search(r'swap\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'reset': (re.search(r'reset\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'from': (re.search(r'from\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'requires': (re.search(r'requires\s*:\s*([a-z0-9_]+)', raw) or [None, None])[1],
        'define': [tok.strip() for body in re.findall(r'=\s*define\s*:\s*\{([^}]*)\}', raw)
                   for tok in body.split('|') if tok.strip()] or None,
    }


# ---------------------------------------------------------------------------
# Contagem — fusão de _count_expr_for_level + _choice_resource_limit + _pick_count_expr
# ---------------------------------------------------------------------------
def _count_expr_cumulative(expr, level):
    """`{classlvl=X:n,...}` -> soma cumulativa dos n com limiar<=level (conhecidas)."""
    return sum(int(v) for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*([+-]?\d+)', expr)
               if int(lv) <= level)


def resource_limit(classe, nivel, resource_slug):
    """Máximo de um recurso-de-escolha da classe no nível (ponte `_`↔`-`)."""
    if not classe or not resource_slug:
        return None
    from .models import TbRecursoclasse
    from .character_engine import RESOURCE_TIPO_CHOICE, _resource_max_at, _resource_tipo
    alvo = normalize_slug(resource_slug)
    todos = list(TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True))
    exatos = [r for r in todos if normalize_slug(r.slug) == alvo]
    parciais = [r for r in todos if alvo in normalize_slug(r.slug)]
    candidatos = exatos + [r for r in parciais if r not in exatos]
    r = next((rec for rec in candidatos if _resource_tipo(rec) == RESOURCE_TIPO_CHOICE), None)
    if r is None and candidatos:
        r = candidatos[0]
    return _resource_max_at(r, nivel) if r else None


def count_for(count_expr, nivel, classe=None, resource_ref=None):
    """N de uma pick-ESCOLHA: literal -> int; `{classlvl=..}` -> soma cumulativa;
    'N'/'+'/vazio -> vem do recurso de tabela (`=resource`). None se indeterminado."""
    expr = (count_expr or '').strip()
    if expr.startswith('{') and 'classlvl' in expr:
        return _count_expr_cumulative(expr, nivel) or None
    if re.match(r'^[+-]?\d+$', expr):
        return int(expr)
    if expr in ('N', '+', ''):
        return resource_limit(classe, nivel, resource_ref)
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


def _opcao_universe(ctx):
    """Opções acessíveis (TbOpcaojogo do tipo ∩ TbAcessoopcao p/ classe/subclasse/nível)."""
    from django.db.models import Q
    from .models import TbOpcaojogo, TbAcessoopcao
    tipo_disp = ctx.get('tipo_display') or _slug2tipo_map().get(ctx['tipo'])
    if not tipo_disp:
        return []
    classe = ctx.get('classe')
    subclasse = ctx.get('subclasse')
    nivel = int(ctx.get('nivel') or 1)
    acc = TbAcessoopcao.objects.filter(nivel_recebimento__lte=nivel).filter(
        (Q(id_classe=classe) if classe else Q(pk__in=[]))
        | (Q(id_subclasse=subclasse) if subclasse else Q(pk__in=[])))
    acc_ids = set(acc.values_list('id_opcao_id', flat=True))
    qs = TbOpcaojogo.objects.filter(tipo=tipo_disp)
    if acc_ids:
        qs = qs.filter(id_opcao__in=acc_ids)
    return [{'id': o.id_opcao, 'slug': o.slug, 'nome': o.nome,
             'descricao': o.descricao or '', 'pre': o.pre_requisito or ''}
            for o in qs.order_by('nome')]


def _opcao_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha, TbOpcaojogo
    tipo = group['persist_tipo']
    # origem IDÊNTICA à do editar-ficha (personagem_escolher_opcoes) p/ o update_or_create
    # casar entre criador e level-up: '<Classe>: <Tipo Exibido>'.
    disp = group.get('tipo_display') or _slug2tipo_map().get(group.get('tipo')) or group.get('tipo') or ''
    origem = '%s: %s' % (group.get('classe') or '', disp)
    base = int(group.get('slot_base') or 0)
    for i, v in enumerate(valores):
        op = (TbOpcaojogo.objects.filter(id_opcao=v).first() if str(v).isdigit() else None) \
            or TbOpcaojogo.objects.filter(slug=v).first()
        if not op:
            continue
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem[:150], tipo=tipo, slot=base + i,
            defaults={'id_opcao': op, 'valor': op.slug})


def _opcao_readback(personagem, group):
    if personagem is None:
        return []
    tipo = group['persist_tipo']
    alt = normalize_slug(tipo)
    alt2 = tipo.replace('-', '_')
    out = []
    for e in personagem.escolhas.select_related('id_opcao').all():
        if e.tipo in (tipo, alt, alt2):
            out.append({'id': e.id, 'slot': e.slot, 'valor': e.valor,
                        'id_opcao': e.id_opcao_id,
                        'nome': (e.id_opcao.nome if e.id_opcao_id else e.valor)})
    out.sort(key=lambda x: x['slot'])
    return out


def _arma_universe(ctx):
    """Armas (TbItemMundano categoria='arma') — escolhe a arma; ganha todas as maestrias dela."""
    import re as _re
    from .models import TbItemMundano, TbOpcaojogo
    from .item_mecanica import mecanica_de_tags, dano_display
    mast = {o.slug: o.nome for o in TbOpcaojogo.objects.filter(tipo='Maestria de Arma')}
    sub_label = {'arma_simples': 'Arma Simples', 'arma_simples_dist': 'Arma Simples à Distância',
                 'arma_marcial': 'Arma Marcial', 'arma_marcial_dist': 'Arma Marcial à Distância',
                 'arma_fogo': 'Arma de Fogo'}
    out = []
    for w in TbItemMundano.objects.filter(categoria='arma').order_by('subcategoria', 'nome'):
        mslugs = []
        for t in (w.tags_json or []):
            m = _re.search(r'maestrias\{([^}]*)\}', str(t))
            if m:
                mslugs = [x.strip() for x in m.group(1).split(',') if x.strip()]
        _mec = mecanica_de_tags(w.tags_json, w.subcategoria)
        out.append({'slug': w.slug, 'nome': w.nome, 'dano': dano_display(_mec),
                    'cat': sub_label.get(w.subcategoria, w.subcategoria or 'Arma'),
                    'chips': [mast.get(s, s) for s in mslugs]})
    return out


def _arma_persist(personagem, group, valores):
    from .models import TbPersonagemEscolha
    # rótulo estável (independe de qual feature carregou o pick:arma) — compat com o
    # criador antigo, que gravava origem='Maestria de Arma (<Classe>)'.
    origem = 'Maestria de Arma (%s)' % (group.get('classe') or '')
    base = int(group.get('slot_base') or 0)
    for i, wslug in enumerate(valores):
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=personagem, origem=origem[:150], tipo='maestria', slot=base + i,
            defaults={'valor': wslug})


def _arma_readback(personagem, group):
    if personagem is None:
        return []
    return [{'id': e.id, 'slot': e.slot, 'valor': e.valor, 'nome': e.valor}
            for e in personagem.escolhas.filter(tipo='maestria').order_by('slot')]


def _default_validate(group, valores):
    """Validação genérica: contagem exata + pertinência ao universo."""
    erros = []
    n = int(group.get('n') or 0)
    universo = {str(u.get('slug')) for u in group.get('universo', [])}
    universo |= {str(u.get('id')) for u in group.get('universo', []) if u.get('id') is not None}
    vals = list(dict.fromkeys([str(v) for v in (valores or [])]))
    fora = [v for v in vals if v not in universo]
    if fora or len(vals) != n:
        erros.append(group.get('erro_label') or ('Escolha %d opção(ões) válida(s).' % n))
    return erros


def _arma_validate(group, valores):
    n = int(group.get('n') or 0)
    universo = {str(u.get('slug')) for u in group.get('universo', [])}
    vals = [v for v in dict.fromkeys(valores or []) if str(v) in universo]
    if len(vals) != n:
        return ['Escolha %d arma(s) para Maestria de Arma.' % n]
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
    from .character_engine import _slug, _norm_skill_slug
    if personagem is None:
        return set()
    owned = set()
    for per in personagem.pericias.all():
        if per.proficiente or per.expertise:
            owned.add(_norm_skill_slug(_slug(per.nome)))
    for e in personagem.escolhas.filter(tipo='pericia'):
        if e.valor:
            owned.add(_norm_skill_slug(e.valor))
    return owned


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


PICK_REGISTRY = {
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
}


# ---------------------------------------------------------------------------
# Resolvedor — varre features e devolve os grupos normalizados.
# ---------------------------------------------------------------------------
def _persist_tipo_for(kind, tipo):
    """Chave `tipo` gravada em TbPersonagemEscolha. `opcao:<sub>` grava o slug do sub
    (ex.: 'estilo_de_luta', 'metamagia'); `arma` grava 'maestria' (compat com o engine);
    `pericia` grava sempre 'pericia' (o sub, quando existe, é a lista de restrição)."""
    if kind == 'arma':
        return 'maestria'
    if kind == 'pericia':
        return 'pericia'
    return tipo or kind


def _build_group(token, source, classe, subclasse, nivel, personagem, escolhas_map, entry,
                 tag_text=''):
    tipo = token.sub
    n = count_for(token.count_expr, nivel, classe, token.resource_ref)
    if not n or n <= 0:
        return None
    ctx = {
        'personagem': personagem, 'classe': classe, 'subclasse': subclasse, 'nivel': nivel,
        'kind': token.kind, 'tipo': tipo, 'constraints': token.constraints,
        'tag_text': tag_text,
    }
    universo = entry['universe'](ctx)
    if not universo:
        return None
    persist_tipo = _persist_tipo_for(token.kind, tipo)
    # Rótulo: kinds com rótulo FIXO no registry (`arma`, `pericia`) usam-no; `opcao` deriva
    # o rótulo do tipo exibido. `arma` não expõe tipo_display (tem painel próprio).
    label_fixo = entry.get('label')
    if token.kind == 'arma':
        tipo_display, label = None, label_fixo
    elif label_fixo:
        tipo_display, label = label_fixo, label_fixo
    else:  # opcao — rótulo dinâmico do tipo
        tipo_display = _slug2tipo_map().get(tipo) or tipo
        label = tipo_display
    group = {
        'origem': getattr(source, 'nome', None) or (classe.nome if classe else ''),
        'kind': token.kind, 'tipo': tipo, 'persist_tipo': persist_tipo,
        'tipo_display': tipo_display, 'label': label,
        'n': n, 'universo': universo, 'constraints': token.constraints,
        'classe_id': (classe.id_classe if classe else None),
        'classe': (classe.nome if classe else ''),
        'sink': entry['sink'],
    }
    # escolhidas: do personagem (readback) OU do mapa passado (builder sem personagem)
    if personagem is not None:
        escolhidas = entry['readback'](personagem, group)
    else:
        escolhidas = list((escolhas_map or {}).get(persist_tipo)
                          or (escolhas_map or {}).get(normalize_slug(persist_tipo)) or [])
    group['escolhidas'] = escolhidas
    group['usados'] = len(escolhidas)
    group['pendentes'] = max(0, n - len(escolhidas))
    group['slot_base'] = 0
    group['prox_slot'] = max([e.get('slot', -1) for e in escolhidas], default=-1) + 1
    return group


def resolve_groups(sources, *, classe=None, subclasse=None, nivel=1,
                   personagem=None, escolhas_map=None, kinds=None):
    """Varre `sources` (objetos com .tags_json/.nome), extrai os picks papel-A e devolve
    a lista de grupos normalizados (um por (kind,tipo) distinto). `kinds` filtra os kinds
    considerados; None = todos os registrados."""
    grupos = []
    vistos = set()
    for source in sources:
        for tag in (getattr(source, 'tags_json', None) or []):
            for tok in iter_pick_tokens(tag):
                if tok.kind not in PICK_REGISTRY:
                    continue  # kind não registrado (referência/efeito/futuro) -> ignora
                if kinds is not None and tok.kind not in kinds:
                    continue
                chave = (tok.kind, tok.sub, (classe.id_classe if classe else None))
                if chave in vistos:
                    continue
                entry = PICK_REGISTRY[tok.kind]
                g = _build_group(tok, source, classe, subclasse, nivel,
                                 personagem, escolhas_map, entry, tag_text=tag)
                if g is None:
                    continue
                vistos.add(chave)
                grupos.append(g)
    return grupos


def builder_sources(classe):
    """Features de nível 1 de uma classe (classe + habilidades N1 sem subclasse)."""
    from .models import TbClassehabilidade
    if not classe:
        return []
    return [classe] + list(TbClassehabilidade.objects.filter(
        id_classe=classe, id_subclasse__isnull=True, niveladquirido=1))


def resolve_builder(classe, *, escolhas_map=None, kinds=None):
    """Grupos de escolha do CRIADOR (nível 1, sem personagem ainda)."""
    return resolve_groups(builder_sources(classe), classe=classe, subclasse=None, nivel=1,
                          personagem=None, escolhas_map=escolhas_map, kinds=kinds)


def resolve_personagem(personagem, *, kinds=None):
    """Grupos de escolha de um PERSONAGEM (level-up/editar): varre classe+subclasse
    desbloqueada até o nível de cada classe. Dedup por (kind,tipo,classe)."""
    from .models import TbClassehabilidade
    from .character_engine import _subclass_unlocked
    grupos = []
    if personagem is None:
        return grupos
    for c in personagem.classes.select_related('id_classe', 'id_subclasse'):
        nivel = int(c.nivel or 0)
        classe = c.id_classe
        habs = list(TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True, niveladquirido__lte=nivel))
        subclasse = None
        if _subclass_unlocked(c, nivel):
            subclasse = c.id_subclasse
            habs += list(TbClassehabilidade.objects.filter(
                id_subclasse=subclasse, niveladquirido__lte=nivel))
        grupos += resolve_groups(habs, classe=classe, subclasse=subclasse, nivel=nivel,
                                 personagem=personagem, kinds=kinds)
    return grupos
