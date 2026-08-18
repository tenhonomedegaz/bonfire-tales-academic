"""Spellcasting contracts declared by the Bonfire tag language.

The character flows consume this module instead of inferring rules from class
names or resource labels.  The parser keeps support for the legacy Portuguese
field names while new content uses the canonical, composable contract below::

    spellcasting{
      ability:int,
      slots{progression:full},
      list:mago,
      mode:prepared,
      spell_limit{formula:classlvl+int_mod},
      spell_level_limit{resource:ciclo_de_feiticos},
      cantrip_limit{resource:truques},
      pool:spellbook,
      acquire{initial:6, level_up:2, transcribe{
        source:spell_scroll,
        cost_po:50*spell_level,
        time_hours:2*spell_level
      }},
      focus:spellbook
    }

Only the tag data decides what a caster can learn, prepare or replace.
"""
from __future__ import annotations

import re
from copy import deepcopy

from .tag_engine.parser import ParseError, parse_tag


_MODE_ALIASES = {
    "known": "known",
    "conhecida": "known",
    "conhecidas": "known",
    "prepared": "prepared",
    "preparada": "prepared",
    "preparadas": "prepared",
}

_MODIFY_CHAIN_RE = re.compile(
    r'^\s*(?P<target>[a-z_][a-z0-9_]*)\s*\{\s*(?P<path>[a-z_][a-z0-9_]*)\s*\}'
    r'\s*\.\s*(?P<operation>add|remove)\s*\{(?P<body>.*)\}\s*$',
    re.I,
)


def _identifier(value):
    return str(value or "").strip().lower().replace("-", "_")


def _children(node):
    return {child.name: child for child in node.children}


def _first(children, *names):
    for name in names:
        node = children.get(name)
        if node is not None:
            return node
    return None


def _scalar(node, default=None):
    if node is None:
        return default
    if node.value not in (None, ""):
        return str(node.value).strip()
    if node.operator == "block" and len(node.children) == 1:
        child = node.children[0]
        if child.value not in (None, ""):
            return str(child.value).strip()
        if child.operator == "flag":
            return child.name
    return default


def _split_list(value):
    value = str(value or "").strip().strip("[]")
    return [part.strip() for part in re.split(r"[|,]", value) if part.strip()]


def _limit_spec(node, *, legacy_formula=False):
    if node is None:
        return None
    if node.operator == "block":
        children = _children(node)
        resource = _scalar(_first(children, "resource", "recurso"))
        formula = _scalar(_first(children, "formula"))
        fixed = _scalar(_first(children, "fixed", "value", "valor"))
        if resource:
            return {"kind": "resource", "value": _identifier(resource)}
        if formula:
            return {"kind": "formula", "value": formula}
        if fixed is not None:
            return {"kind": "fixed", "value": fixed}
    value = _scalar(node)
    if value is None:
        return None
    if legacy_formula:
        return {"kind": "formula", "value": value}
    if re.fullmatch(r"\d+", value):
        return {"kind": "fixed", "value": value}
    return {"kind": "resource", "value": _identifier(value)}


def _slots_spec(node):
    if node is None:
        return {}
    if node.operator == "block":
        children = _children(node)
        progression = _scalar(_first(children, "progression", "type", "tipo"))
        resource = _scalar(_first(children, "resource", "recurso"))
        cost = _scalar(_first(children, "cost", "custo"))
        return {
            "slots": _identifier(progression) if progression else None,
            "slots_resource": _identifier(resource) if resource else None,
            "slots_cost": cost,
        }

    progression = _identifier(_scalar(node))
    resource = None
    for qualifier in node.qualifiers:
        match = re.search(r"\b(?:resource|recurso)\s*:\s*([a-z0-9_-]+)", qualifier, re.I)
        if match:
            resource = _identifier(match.group(1))
            break
    return {"slots": progression or None, "slots_resource": resource,
            "slots_cost": None}


def _swap_spec(node):
    if node is None:
        return None
    if node.operator == "block":
        children = _children(node)
        event = _scalar(_first(children, "event", "evento"))
        maximum = _scalar(_first(children, "max", "maximum", "limite"))
    else:
        event = _scalar(node)
        maximum = None
    if not event:
        return None
    maximum = _identifier(maximum or "1")
    if maximum != "all":
        try:
            maximum = max(0, int(maximum))
        except (TypeError, ValueError):
            maximum = 1
    return {"event": _identifier(event), "max": maximum}


def _acquire_spec(node):
    if node is None or node.operator != "block":
        return {}
    children = _children(node)
    out = {}
    for key, aliases in {
        "initial": ("initial", "inicial"),
        "level_up": ("level_up",),
    }.items():
        value = _scalar(_first(children, *aliases))
        if value is not None:
            try:
                out[key] = max(0, int(value))
            except (TypeError, ValueError):
                out[key] = value
    transcribe = _first(children, "transcribe", "transcrever")
    if transcribe is not None:
        if transcribe.operator == "block":
            tc = _children(transcribe)
            out["transcribe"] = {
                "source": _identifier(_scalar(_first(tc, "source", "fonte"), "spell_scroll")),
                "cost_po": _scalar(_first(tc, "cost_po", "cost", "custo_po", "custo")),
                "time_hours": _scalar(_first(
                    tc, "time_hours", "time", "tempo_horas", "tempo")),
            }
        else:
            out["transcribe"] = {"source": _identifier(_scalar(transcribe, "spell_scroll"))}
    return out


def _patch_from_node(node):
    children = _children(node)
    slots = _slots_spec(_first(children, "slots"))
    mode_raw = _scalar(_first(children, "mode", "prepara"))
    mode = _MODE_ALIASES.get(_identifier(mode_raw)) if mode_raw else None
    list_raw = _scalar(_first(children, "list", "lista"))
    focus = _scalar(_first(children, "focus", "foco"))
    pool = _scalar(_first(children, "pool"))

    spell_limit = _limit_spec(_first(children, "spell_limit"))
    if spell_limit is None:
        spell_limit = _limit_spec(
            _first(children, "prep_limit", "prep_limite"), legacy_formula=True)

    return {
        "ability": _identifier(_scalar(_first(children, "ability"))) or None,
        "list": _split_list(list_raw) if list_raw is not None else None,
        "mode": mode,
        "focus": focus,
        "pool": _identifier(pool) if pool else None,
        "spell_limit": spell_limit,
        "spell_level_limit": _limit_spec(_first(
            children, "spell_level_limit", "level_limit", "nivel_maximo_magia")),
        "cantrip_limit": _limit_spec(_first(children, "cantrip_limit")),
        "swap": _swap_spec(_first(children, "swap")),
        "acquire": _acquire_spec(_first(children, "acquire")),
        "raw": node.raw,
        **slots,
    }


def _merge(contract, patch, *, declaration=False):
    if declaration or contract is None:
        base = {
            "ability": "int",
            "slots": "full",
            "slots_resource": None,
            "slots_cost": None,
            "list": [],
            "mode": None,
            "focus": None,
            "pool": "class_list",
            "spell_limit": None,
            "spell_level_limit": None,
            "cantrip_limit": None,
            "swap": None,
            "acquire": {},
            "raw": "",
        }
        if contract and not declaration:
            base.update(deepcopy(contract))
        contract = base
    for key, value in patch.items():
        if value is None:
            continue
        if key == "acquire":
            contract.setdefault("acquire", {}).update(value)
        else:
            contract[key] = value
    return contract


def parse_spellcasting_sources(sources):
    """Return the effective top-level spellcasting contract for ordered sources.

    Nested ``spellcasting.modifiers`` keep their lexical scope in the general tag
    engine and are intentionally not promoted to the class declaration here.
    """
    contract = None
    for source in sources or ():
        for tag in (getattr(source, "tags_json", None) or []):
            try:
                program = parse_tag(tag)
            except ParseError:
                continue
            for node in program.nodes:
                if node.name != "spellcasting" or node.operator != "block":
                    continue
                names = {child.name for child in node.children}
                declaration = bool(names & {"slots", "list", "lista"})
                if declaration or contract is not None:
                    contract = _merge(
                        contract, _patch_from_node(node), declaration=declaration)
    if contract is None:
        return None

    contract["prepara"] = {
        "known": "conhecidas", "prepared": "preparadas"}.get(contract.get("mode"))
    contract["lista"] = list(contract.get("list") or [])
    limit = contract.get("spell_limit") or {}
    contract["prep_formula"] = (
        limit.get("value") if limit.get("kind") == "formula" else None)
    slots = contract.get("slots") or "full"
    resource = contract.get("slots_resource")
    contract["slots_raw"] = (
        "%s(resource:%s)" % (slots, resource) if resource else slots)
    contract["swap_level_up"] = bool(
        contract.get("swap") and contract["swap"].get("event") == "level_up")
    return contract


def parse_spellcasting_list_operations(sources, *, has_spellcasting=True):
    """Interpreta modificadores composáveis da lista de uma fonte de feature.

    A forma canônica é ``modify:spellcasting{list}.add{spell:<slug>, ...}``.
    ``remove`` usa o mesmo contrato. A ordem das fontes, tags e operandos é
    preservada; um requisito de conjuração bloqueia o modificador sem conceder
    conjuração por conta própria.
    """
    operations = []
    for source in sources or ():
        for tag in (getattr(source, 'tags_json', None) or []):
            try:
                program = parse_tag(tag)
            except ParseError:
                continue
            requirements = [
                _identifier(node.value)
                for node in program.nodes
                if node.name == 'requires' and node.operator == ':'
            ]
            if 'spellcasting' in requirements and not has_spellcasting:
                continue
            # Requisitos desconhecidos não podem ser presumidos como satisfeitos.
            if any(req != 'spellcasting' for req in requirements):
                continue
            for node in program.nodes:
                if node.name != 'modify' or node.operator != ':':
                    continue
                match = _MODIFY_CHAIN_RE.match(str(node.value or ''))
                if not match:
                    continue
                if (_identifier(match.group('target')) != 'spellcasting'
                        or _identifier(match.group('path')) != 'list'):
                    continue
                try:
                    operands = parse_tag(match.group('body')).nodes
                except ParseError:
                    continue
                for operand in operands:
                    if operand.name != 'spell' or operand.operator != ':' or not operand.value:
                        continue
                    operations.append({
                        'operation': match.group('operation').lower(),
                        'spell': str(operand.value).strip(),
                        'source': source,
                        'raw': str(tag),
                    })
    return operations


def character_spell_list_delta(personagem):
    """Adições/remoções efetivas que as features do personagem fazem na lista."""
    if personagem is None or not getattr(personagem, 'pk', None):
        return {'add': set(), 'remove': set(), 'operations': []}
    from .character_engine import _conjuracao_real, _features_do_personagem
    from .models import TbMagia

    features = [row[2] for row in _features_do_personagem(personagem)]
    operations = parse_spellcasting_list_operations(
        features, has_spellcasting=_conjuracao_real(personagem))
    by_token = {}
    for magia in TbMagia.objects.only('slug'):
        by_token[_identifier(magia.slug)] = magia.slug
    added, removed, resolved = set(), set(), []
    for operation in operations:
        slug = by_token.get(_identifier(operation['spell']))
        if not slug:
            continue
        if operation['operation'] == 'add':
            added.add(slug)
            removed.discard(slug)
        else:
            removed.add(slug)
            added.discard(slug)
        resolved.append({**operation, 'spell': slug})
    return {'add': added, 'remove': removed, 'operations': resolved}


def class_spellcasting_contract(classe, *, level=1, subclass=None):
    """Resolve a class/subclass contract in the same order as feature unlocks."""
    from django.db.models import Q

    from .models import TbClassehabilidade

    condition = Q(id_classe=classe, id_subclasse__isnull=True)
    if subclass is not None:
        condition |= Q(id_subclasse=subclass)
    features = TbClassehabilidade.objects.filter(condition)
    if level is not None:
        features = features.filter(niveladquirido__lte=level)
    features = features.order_by("niveladquirido", "id_habilidade")
    return parse_spellcasting_sources([classe] + list(features))


def resource_limit_at(spec, classe, *, level, subclass=None):
    """Resolve a fixed/resource limit. Formula limits need the character context."""
    if not spec:
        return None
    kind = spec.get("kind")
    value = spec.get("value")
    if kind == "fixed":
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None
    if kind != "resource" or not value:
        return None

    from django.db.models import Q

    from .models import TbRecursoclasse

    condition = Q(id_classe=classe, id_subclasse__isnull=True)
    if subclass is not None:
        condition |= Q(id_subclasse=subclass)
    wanted = _identifier(value)
    values = []
    for resource in TbRecursoclasse.objects.filter(condition):
        if _identifier(resource.slug) != wanted:
            continue
        table = resource.valores_json or {}
        eligible = []
        for key in table:
            try:
                number = int(key)
            except (TypeError, ValueError):
                continue
            if number <= int(level or 0):
                eligible.append(number)
        raw = table.get(str(max(eligible))) if eligible else None
        if raw is None and resource.nivel == level:
            raw = resource.valor
        try:
            values.append(int(str(raw).strip()))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def limit_at(spec, classe, *, level, context=None, subclass=None, minimum=0):
    """Resolve um limite declarado sem inferir nada pelo nome da classe.

    ``resource`` consulta a tabela de recursos, ``fixed`` devolve o literal e
    ``formula`` usa o avaliador aritmético compartilhado pelo motor de ficha.
    Variáveis ausentes tornam a fórmula inválida em vez de inventar um valor.
    """
    if not spec:
        return None
    if spec.get("kind") in {"resource", "fixed"}:
        value = resource_limit_at(spec, classe, level=level, subclass=subclass)
    elif spec.get("kind") == "formula":
        from .character_engine import _eval_formula

        value = _eval_formula(str(spec.get("value") or "").strip(), context or {})
    else:
        value = None
    if value is None:
        return None
    try:
        return max(int(minimum or 0), int(value))
    except (TypeError, ValueError):
        return None


def slot_table_at(classe, *, level, subclass=None):
    """Resolve os espacos 1o..9o declarados como recursos ``table_only``.

    A funcao existe aqui para que criador, progressao, ficha e motor usem a
    mesma fonte. O slug da classe e o nome visivel do recurso nao participam
    da regra; apenas o protocolo mecanico dos recursos.
    """
    if classe is None:
        return {}

    from django.db.models import Q

    from .character_engine import (
        RESOURCE_TIPO_TABLE_ONLY,
        _resource_max_at,
        _resource_tipo,
    )
    from .models import TbRecursoclasse

    condition = Q(id_classe=classe, id_subclasse__isnull=True)
    if subclass is not None:
        condition |= Q(id_subclasse=subclass)

    out = {}
    for resource in TbRecursoclasse.objects.filter(condition):
        match = re.fullmatch(r"([1-9])o", _identifier(resource.slug))
        if not match or _resource_tipo(resource) != RESOURCE_TIPO_TABLE_ONLY:
            continue
        value = _resource_max_at(resource, int(level or 0))
        if value is None:
            continue
        spell_level = int(match.group(1))
        out[spell_level] = max(0, int(value), out.get(spell_level, 0))
    return out


def progression_max_spell_level(level, progression):
    """Fallback para contratos sem tabela materializada de espacos."""
    level = max(0, int(level or 0))
    progression = _identifier(progression or "full")
    if progression == "half":
        return min(5, ((level + 1) // 2 + 1) // 2)
    if progression == "third":
        if level >= 19:
            return 4
        if level >= 13:
            return 3
        if level >= 7:
            return 2
        return 1 if level >= 3 else 0
    if progression == "pact":
        return min(5, max(1, (level + 1) // 2)) if level else 0
    return min(9, (level + 1) // 2) if level else 0


def max_spell_level_at(
        contract, classe, *, level, subclass=None, context=None):
    """Maior circulo conjuravel segundo o contrato efetivo da classe.

    A declaracao explicita cobre conjuradores por pontos. Sem ela, o topo da
    tabela de espacos vence; a progressao abstrata e apenas a rede de seguranca
    para conteudo ainda sem recursos materializados.
    """
    if not contract or classe is None:
        return 0
    explicit = limit_at(
        contract.get("spell_level_limit"), classe, level=level,
        context=context or {"classlvl": int(level or 0)}, subclass=subclass)
    if explicit is not None:
        return min(9, max(0, int(explicit)))
    table = slot_table_at(classe, level=level, subclass=subclass)
    available = [spell_level for spell_level, total in table.items() if total > 0]
    if available:
        return max(available)
    return progression_max_spell_level(level, contract.get("slots"))


def acquired_spell_count(contract, *, level):
    """Quantidade cumulativa que um ``pool:spellbook`` deve possuir no nível.

    A regra vem de ``acquire{initial:N, level_up:N}``; classes futuras podem
    trocar os números sem mudanças no criador ou no fluxo de progressão.
    """
    acquire = (contract or {}).get("acquire") or {}
    try:
        initial = max(0, int(acquire.get("initial") or 0))
        per_level = max(0, int(acquire.get("level_up") or 0))
        class_level = max(1, int(level or 1))
    except (TypeError, ValueError):
        return 0
    return initial + per_level * (class_level - 1)


def swap_quota(contract, *, known_count):
    """Converte ``swap{event:level_up,max:...}`` numa quota numérica."""
    swap = (contract or {}).get("swap") or {}
    if swap.get("event") != "level_up":
        return 0
    maximum = swap.get("max", 1)
    if maximum == "all":
        return max(0, int(known_count or 0))
    try:
        return max(0, int(maximum))
    except (TypeError, ValueError):
        return 0


def spell_scroll_slug(tags, *, source="spell_scroll"):
    """Extrai a magia de um item que implementa o protocolo de pergaminho.

    O nome do item, seu slot e sua categoria não têm papel mecânico. A fonte
    declarada em ``acquire.transcribe.source`` escolhe o nó e o item informa a
    magia por ``spell_scroll{spell:<slug>}``.
    """
    wanted = _identifier(source)
    for tag in tags or ():
        try:
            program = parse_tag(tag)
        except ParseError:
            continue
        for node in program.nodes:
            if node.name != wanted:
                continue
            if node.operator == "block":
                value = _scalar(_first(_children(node), "spell", "magia"))
            else:
                value = _scalar(node)
            if value:
                return str(value).strip()
    return None


def transcription_terms(contract, *, spell_level):
    """Resolve custo em PO e tempo em horas do contrato de transcrição."""
    transcribe = ((contract or {}).get("acquire") or {}).get("transcribe") or {}
    if not transcribe:
        return None
    from .character_engine import _eval_formula

    context = {"spell_level": max(0, int(spell_level or 0))}

    def resolve(field):
        raw = transcribe.get(field)
        if raw in (None, ""):
            return 0
        value = _eval_formula(str(raw), context)
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    cost_po = resolve("cost_po")
    time_hours = resolve("time_hours")
    if cost_po is None or time_hours is None:
        return None
    return {"cost_po": cost_po, "time_hours": time_hours,
            "source": transcribe.get("source") or "spell_scroll"}
