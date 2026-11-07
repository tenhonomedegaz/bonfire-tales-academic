"""Produtos virtuais e regras mecânicas da Oficina de Magia."""
from __future__ import annotations

import copy
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from .tag_engine.parser import ParseError, parse_tag


SCROLL_PRICE_PO = {
    1: Decimal('60'), 2: Decimal('150'), 3: Decimal('300'),
    4: Decimal('600'), 5: Decimal('1000'), 6: Decimal('2500'),
    7: Decimal('7000'), 8: Decimal('15000'), 9: Decimal('20000'),
}

SCROLL_STATS = {
    0: ('comum', 13, 5), 1: ('comum', 13, 5),
    2: ('incomum', 13, 5), 3: ('incomum', 15, 7),
    4: ('raro', 15, 7), 5: ('raro', 17, 9),
    6: ('muito_raro', 17, 9), 7: ('muito_raro', 18, 10),
    8: ('muito_raro', 18, 10), 9: ('lendario', 19, 11),
}

_CURRENCY_VALUE = {
    'po': Decimal('1'), 'gp': Decimal('1'), 'ouro': Decimal('1'),
    'pp': Decimal('0.1'), 'sp': Decimal('0.1'), 'prata': Decimal('0.1'),
    'pc': Decimal('0.01'), 'cp': Decimal('0.01'), 'cobre': Decimal('0.01'),
}
_NUMBER_WORDS = {
    'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'par': 2,
    'tres': 3, 'quatro': 4, 'cinco': 5, 'seis': 6,
    'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10,
}
_PRICE_RE = re.compile(
    r'(?P<number>\d[\d.\s]*(?:,\d+)?)\s*(?:\+\s*)?'
    r'(?P<currency>PO|GP|PP|SP|PC|CP|pe[cç]as?\s+de\s+ouro|'
    r'pe[cç]as?\s+de\s+prata|pe[cç]as?\s+de\s+cobre)',
    re.I,
)


def _ascii(value):
    return unicodedata.normalize('NFKD', str(value or '')).encode(
        'ascii', 'ignore').decode('ascii').lower()


def _decimal_number(raw):
    raw = str(raw or '').strip().replace(' ', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    elif raw.count('.') == 1 and len(raw.rsplit('.', 1)[1]) != 3:
        pass
    else:
        raw = raw.replace('.', '')
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal('0')


def _currency_key(raw):
    value = _ascii(raw)
    if 'ouro' in value:
        return 'ouro'
    if 'prata' in value:
        return 'prata'
    if 'cobre' in value:
        return 'cobre'
    return value.strip()


def _each_multiplier(text, match):
    after = _ascii(text[match.end():match.end() + 32])
    if not re.search(r'\bcada\b', after):
        return 1
    before = _ascii(text[max(0, match.start() - 120):match.start()])
    words = re.findall(r'\b(?:um|uma|dois|duas|par|tres|quatro|cinco|seis|sete|oito|nove|dez)\b', before)
    if words:
        return _NUMBER_WORDS[words[-1]]
    numbers = re.findall(r'\b(\d+)\b', before)
    return max(1, int(numbers[-1])) if numbers else 1


def parse_priced_materials(componentes):
    """Extrai custos materiais e separa o que é consumido do foco reutilizável.

    O parser é conservador: só cria preço quando há número e moeda explícitos.
    A descrição original é preservada para a pessoa conferir o componente real.
    """
    text = str(componentes or '').strip()
    matches = list(_PRICE_RE.finditer(text))
    all_consumed_after = []
    normalized = _ascii(text)
    for marker in re.finditer(r'\btodos?\s+consumid[oa]s?\b', normalized):
        if matches and marker.start() > matches[-1].start():
            all_consumed_after.append(marker.start())

    entries = []
    for index, match in enumerate(matches):
        amount = _decimal_number(match.group('number'))
        amount *= _CURRENCY_VALUE.get(_currency_key(match.group('currency')), Decimal('0'))
        amount *= _each_multiplier(text, match)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        window = _ascii(text[match.end():next_start])
        consumed = bool(re.search(r'\bcons(?:om|um)(?:e|ido|ida|idos|idas|ida pela magia)\b', window))
        if all_consumed_after and match.start() < all_consumed_after[-1]:
            consumed = True
        if re.search(r'\breutiliz', window):
            consumed = False
        if amount > 0:
            entries.append({
                'amount_po': amount,
                'consumed': consumed,
                'source': match.group(0),
            })

    consumed_cost = sum(
        (row['amount_po'] for row in entries if row['consumed']), Decimal('0'))
    reusable_cost = sum(
        (row['amount_po'] for row in entries if not row['consumed']), Decimal('0'))
    return {
        'description': text,
        'entries': entries,
        'consumed_cost_po': consumed_cost,
        'reusable_cost_po': reusable_cost,
        'total_cost_po': consumed_cost + reusable_cost,
    }


def spell_token(spell_or_slug):
    slug = getattr(spell_or_slug, 'slug', spell_or_slug)
    return str(slug or '').strip().replace('-', '_')


def resolve_spell_token(token):
    from .models import TbMagia
    wanted = spell_token(token)
    return next((spell for spell in TbMagia.objects.all().only(
        'id_magia', 'slug', 'nome', 'nivel', 'escola', 'classes', 'classes_slugs')
        if spell_token(spell) == wanted), None)


def spell_is_log_castable(spell):
    """Indica se a magia produz um estado persistente gerenciável fora de jogo.

    A duração oficial cobre o caso normal. Efeitos instantâneos ou condicionais
    (como Encontrar Familiar) precisam declarar ``log_castable`` nas próprias
    tags, mantendo a exceção auditável no conteúdo em vez de uma lista no código.
    """
    if 'ate ser dissip' in _ascii(getattr(spell, 'duracao', '')):
        return True

    def contains_marker(nodes):
        for node in nodes:
            if node.name == 'log_castable':
                return True
            if contains_marker(node.children or []):
                return True
        return False

    for tag in getattr(spell, 'tags_json', None) or ():
        try:
            if contains_marker(parse_tag(tag).nodes):
                return True
        except ParseError:
            continue
    return False


def scroll_offer(spell):
    level = int(spell.nivel or 0)
    if level not in SCROLL_PRICE_PO:
        return None
    rarity, save_dc, attack_bonus = SCROLL_STATS[level]
    materials = parse_priced_materials(spell.componentes)
    # O componente consumido ja foi gasto ao criar o pergaminho. Ele nao e somado
    # novamente: apenas estabelece o piso quando custa mais que o pergaminho-base.
    price = max(SCROLL_PRICE_PO[level], materials['consumed_cost_po'])
    return {
        'kind': 'scroll', 'slug': spell.slug, 'spell': spell,
        'name': f'Pergaminho de {spell.nome}', 'level': level,
        'price_po': price, 'base_price_po': SCROLL_PRICE_PO[level],
        'material_price_po': materials['consumed_cost_po'],
        'material_sets_price': materials['consumed_cost_po'] > SCROLL_PRICE_PO[level],
        'rarity': rarity, 'save_dc': save_dc, 'attack_bonus': attack_bonus,
        'tags': [
            ('spell_scroll{spell:%s, level:%d, save_dc:%d, attack_bonus:%d}'
             % (spell_token(spell), level, save_dc, attack_bonus)),
            'consumable',
        ],
    }


def component_offers(spell):
    parsed = parse_priced_materials(spell.componentes)
    offers = []
    for kind, price, consumed in (
        ('consumable', parsed['consumed_cost_po'], True),
        ('focus', parsed['reusable_cost_po'], False),
    ):
        if price <= 0:
            continue
        if parsed['consumed_cost_po'] and parsed['reusable_cost_po']:
            qualifier = ' consumíveis' if consumed else ' reutilizáveis'
        else:
            qualifier = ''
        tags = [
            ('spell_component{spell:%s, kind:%s, cost_po:%s}'
             % (spell_token(spell), kind, format(price, 'f'))),
        ]
        if consumed:
            tags.append('consumable')
        offers.append({
            'kind': kind, 'slug': f'{spell.slug}:{kind}', 'spell': spell,
            'name': f'Componentes{qualifier} de {spell.nome}',
            'price_po': price, 'consumed': consumed,
            'description': parsed['description'], 'tags': tags,
        })
    return offers


def _block_info(tags, node_name):
    for tag in tags or ():
        try:
            program = parse_tag(tag)
        except ParseError:
            continue
        for node in program.nodes:
            if node.name != node_name or node.operator != 'block':
                continue
            return {child.name: child.value for child in node.children}
    return None


def scroll_item_info(tags):
    return _block_info(tags, 'spell_scroll')


def component_item_info(tags):
    return _block_info(tags, 'spell_component')


def character_casters(personagem, *, contract_cache=None, ruleset=None):
    from .character_engine import _subclass_unlocked, spell_scope_names
    from .spellcasting import class_spellcasting_contract, max_spell_level_at

    rows = []
    prefetched = getattr(personagem, '_prefetched_objects_cache', {}).get('classes')
    classes = (prefetched if prefetched is not None else
               personagem.classes.select_related('id_classe', 'id_subclasse'))
    scope_map = None
    if ruleset is not None:
        from .versioned_classes import resolved_classes
        from .versioned_spells import spell_scopes
        classes = resolved_classes(ruleset, classes)
        scope_map = spell_scopes(ruleset)
    for pc in classes:
        level = int(pc.nivel or 1)
        subclass = pc.id_subclasse if ruleset is not None or _subclass_unlocked(pc, level) else None
        cache_key = (pc.id_classe_id, getattr(subclass, 'pk', None), level)
        if ruleset is not None:
            cache_key = (ruleset.pk, *cache_key,
                         getattr(pc.id_classe, '_character_spellcasting_ability', None))
        cached = contract_cache.get(cache_key) if contract_cache is not None else None
        if cached is None:
            contract = class_spellcasting_contract(
                pc.id_classe, level=level, subclass=subclass, ruleset=ruleset)
            maximum = (max_spell_level_at(
                contract, pc.id_classe, level=level, subclass=subclass,
                context={'classlvl': level}, ruleset=ruleset) if contract else 0)
            if contract_cache is not None:
                contract_cache[cache_key] = (copy.deepcopy(contract), maximum)
        else:
            contract, maximum = copy.deepcopy(cached[0]), cached[1]
        if not contract:
            continue
        contract['lista_nomes'] = spell_scope_names(contract.get('list') or [], scope_map) or [pc.id_classe.nome]
        rows.append({
            'pc': pc, 'contract': contract,
            'max_spell_level': maximum,
        })
    return rows


def character_spell_access_map(personagem, spells, *, casters=None):
    """Resolve o acesso de todo o catálogo sem repetir consultas por magia."""
    from .models import TbMagia
    from .spell_access import spell_class_query
    from .spellcasting import character_spell_list_delta

    spells = list(spells)
    casters = character_casters(personagem) if casters is None else casters
    delta = character_spell_list_delta(personagem)
    spell_ids = {spell.pk for spell in spells}
    origins = {}
    for spell_id, origin in personagem.magias.filter(
            id_magia_id__in=spell_ids).values_list('id_magia_id', 'origem'):
        origins.setdefault(spell_id, set()).add(str(origin or '').casefold())

    base_ids = []
    scopes_cache = {}
    for caster in casters:
        raw_scopes = caster['contract'].get('list') or ()
        scopes = ((raw_scopes,) if isinstance(raw_scopes, str)
                  else tuple(raw_scopes))
        if scopes not in scopes_cache:
            scopes_cache[scopes] = set(
                TbMagia.objects.filter(spell_class_query(scopes)).values_list(
                    'pk', flat=True)) if spells else set()
        base_ids.append((caster, scopes_cache[scopes]))

    access = {}
    for spell in spells:
        if spell.slug in delta['remove']:
            continue
        added = spell.slug in delta['add']
        spell_origins = origins.get(spell.pk, set())
        eligible = [
            caster for caster, ids in base_ids
            if (added or spell.pk in ids
                or caster['pc'].id_classe.nome.casefold() in spell_origins)
        ]
        if eligible:
            access[spell.pk] = eligible
    return access


def spell_accessible_to_character(personagem, spell, *, casters=None):
    from .spell_access import spell_has_base_access
    from .spellcasting import character_spell_list_delta

    casters = character_casters(personagem) if casters is None else casters
    delta = character_spell_list_delta(personagem)
    if spell.slug in delta['remove']:
        return []
    owned_origins = {
        str(origin or '').casefold()
        for origin in personagem.magias.filter(
            id_magia=spell).values_list('origem', flat=True)
    }
    out = []
    for caster in casters:
        if (spell.slug in delta['add']
                or spell_has_base_access(spell, caster['contract'].get('list') or [])
                # Escolhas como Segredos Mágicos são persistidas com a classe
                # como origem: para aquele personagem, a magia passou a integrar
                # efetivamente essa lista, sem tornar magias inatas raciais elegíveis.
                or caster['pc'].id_classe.nome.casefold() in owned_origins):
            out.append(caster)
    return out


def focus_schools(personagem, *, ruleset=None):
    """Escolas escolhidas ou concedidas pelo catálogo genérico de opções."""
    from .versioned_options import VersionedOptions
    frozen = ({o['id_opcao']: o for o in VersionedOptions(ruleset).data['options']}
              if ruleset is not None else None)
    schools = set()
    for choice in personagem.escolhas.select_related('id_opcao'):
        option = choice.id_opcao if choice.id_opcao_id else None
        if frozen is not None and choice.id_opcao_id:
            if choice.id_opcao_id not in frozen:
                raise ValueError('Focus option absent from pinned ruleset.')
            from types import SimpleNamespace
            option = SimpleNamespace(**frozen[choice.id_opcao_id])
        option_type = _ascii(
            option.tipo if choice.id_opcao_id else '').replace(' ', '_')
        if choice.tipo not in {'escola_de_foco', 'spell_school'} \
                and option_type != 'escola_de_foco':
            continue
        value = option.slug if choice.id_opcao_id else choice.valor
        if value:
            schools.add(_ascii(value).replace(' ', '_'))
    return schools


def _spell_damage_types(spell, known=None):
    """Tipos de dano mecanicamente declarados nas tags de uma magia."""
    if known is None:
        from .tag_engine.library import Library
        known = Library().catalogs.get('damage_type', set())
    text = _ascii(' '.join(
        tag for tag in (getattr(spell, 'tags_json', None) or ())
        if isinstance(tag, str)))
    return sorted(
        damage for damage in known
        if re.search(r'(?<![a-z0-9_])%s(?![a-z0-9_])' % re.escape(damage), text)
    )


def _spell_components(spell):
    raw = str(getattr(spell, 'componentes', '') or '')
    letters = []
    for match in re.finditer(r'(?<![A-Za-z])([VSM])(?![A-Za-z])', raw, re.I):
        letter = match.group(1).upper()
        if letter not in letters:
            letters.append(letter)
    materials = parse_priced_materials(raw)
    protected = set()
    normalized = _ascii(raw)
    if 'M' in letters and (
            materials['total_cost_po'] > 0 or 'consum' in normalized):
        protected.add('M')
    return {
        'all': letters,
        'removable': [letter for letter in letters if letter not in protected],
        'protected': sorted(protected),
    }


def _spell_has_area(spell):
    text = _ascii(' '.join(
        tag for tag in (getattr(spell, 'tags_json', None) or ())
        if isinstance(tag, str)))
    return bool(re.search(r'(?<![a-z0-9_])(?:aoe|area)\s*\{', text))


def _spellcraft_node_values(node):
    values = {}
    for child in node.children or ():
        if child.operator == 'block':
            values[child.name] = [
                str(item.value if item.name == '_literal' else item.name)
                for item in child.children or ()
            ]
        else:
            values[child.name] = child.value
    return values


def signature_spell_rules(personagem, *, casters=None):
    """Contratos ``spellcraft`` ativos e seus catálogos para a Oficina.

    A oficina não conhece Mago, níveis ou nomes de habilidades. Cada feature
    declara slot, fonte, escola, limites e marcos de remodelagem na própria tag.
    """
    from .character_engine import _features_do_personagem
    from .models import TbPersonagemMagiaAssinatura
    from .tag_engine.library import Library

    casters = character_casters(personagem) if casters is None else casters
    caster_by_class = {row['pc'].id_classe_id: row for row in casters}
    focus = focus_schools(personagem)
    signatures = {
        (row.id_classe_id, int(row.slot)): row
        for row in TbPersonagemMagiaAssinatura.objects.filter(
            id_personagem=personagem).select_related(
                'id_magia_base', 'id_magia_personagem', 'id_classe')
    }
    signature_spell_ids = {
        row.id_magia_personagem_id for row in signatures.values()
    }
    owned = list(personagem.magias.filter(
        id_magia__isnull=False).select_related('id_magia'))
    damage_catalog = Library().catalogs.get('damage_type', set())

    rules = []
    for _origin, _source, feature, classlvl in _features_do_personagem(personagem):
        class_id = getattr(feature, 'id_classe_id', None)
        caster = caster_by_class.get(class_id)
        if caster is None:
            continue
        for tag in getattr(feature, 'tags_json', None) or ():
            if not isinstance(tag, str) or 'spellcraft' not in tag:
                continue
            try:
                nodes = parse_tag(tag).nodes
            except ParseError:
                continue
            for node in nodes:
                if node.name != 'spellcraft' or node.operator != 'block':
                    continue
                values = _spellcraft_node_values(node)
                if values.get('kind') != 'signature_spell':
                    continue
                try:
                    slot = int(values.get('slot'))
                    max_base = int(values.get('max_base_level'))
                except (TypeError, ValueError):
                    continue
                if values.get('source') != 'spellbook' \
                        or caster['contract'].get('pool') != 'spellbook':
                    continue
                max_final_raw = values.get('max_final_level')
                try:
                    max_final = (int(caster['max_spell_level'])
                                 if max_final_raw == 'spell_slot_max'
                                 else int(max_final_raw))
                except (TypeError, ValueError):
                    continue
                remodel_at = sorted({
                    int(level) for level in values.get('remodel_at', [])
                    if str(level).isdigit()
                })
                existing = signatures.get((class_id, slot))
                existing_mods = (
                    existing.modificacoes_json if existing is not None else {}) or {}
                current_level = int(classlvl or caster['pc'].nivel or 0)
                pending_levels = [
                    level for level in remodel_at
                    if level <= current_level and (
                        existing is None
                        or level > int(existing.ultima_reforma_nivel or 0))
                ]
                pending_remodel = max(pending_levels, default=None)
                can_edit = existing is None or pending_remodel is not None
                spell_rows = []
                class_owned = [
                    row for row in owned
                    if row.pk not in signature_spell_ids
                    and str(row.origem or '').casefold()
                    == caster['pc'].id_classe.nome.casefold()
                ]
                damage_types = {
                    damage for row in class_owned
                    for damage in _spell_damage_types(
                        row.id_magia, damage_catalog)
                }
                for row in class_owned:
                    spell = row.id_magia
                    if not 1 <= int(spell.nivel or 0) <= max_base:
                        continue
                    school = _ascii(spell.escola).replace(' ', '_')
                    if values.get('school') == 'focus' and school not in focus:
                        continue
                    damages = _spell_damage_types(spell, damage_catalog)
                    spell_rows.append({
                        'owned': row,
                        'spell': spell,
                        'components': _spell_components(spell),
                        'casting_action': _ascii(spell.casting_time).strip() in {
                            'acao', '1 acao'},
                        'damage_types': damages,
                        'has_area': _spell_has_area(spell),
                        'selected': bool(
                            existing is not None
                            and existing.id_magia_base_id == spell.pk),
                    })
                spell_rows.sort(key=lambda item: (
                    int(item['spell'].nivel or 0),
                    item['spell'].nome.casefold()))
                rules.append({
                    'slot': slot,
                    'feature': feature,
                    'class_id': class_id,
                    'class_name': caster['pc'].id_classe.nome,
                    'class_level': current_level,
                    'max_base_level': max_base,
                    'max_final_level': max_final,
                    'remodel_at': remodel_at,
                    'pending_remodel': pending_remodel,
                    'can_edit': can_edit,
                    'existing': existing,
                    'form': {
                        'name': existing.nome if existing is not None else '',
                        'bonus_action': bool(existing_mods.get('bonus_action')),
                        'removed_components': set(
                            existing_mods.get('removed_components') or ()),
                        'concentration_guard': bool(
                            existing_mods.get('concentration_guard')),
                        'damage_from': (
                            existing_mods.get('damage') or {}).get('from', ''),
                        'damage_to': (
                            existing_mods.get('damage') or {}).get('to', ''),
                        'area_shape': (
                            existing_mods.get('area') or {}).get('shape', ''),
                        'area_squares': (
                            existing_mods.get('area') or {}).get('squares', ''),
                    },
                    'spells': spell_rows,
                    'damage_types': sorted(damage_types),
                })
    rules.sort(key=lambda rule: (rule['class_name'].casefold(), rule['slot']))
    return rules


def transcription_terms_for_character(
        personagem, caster, spell, *, focus_school_values=None):
    from .spellcasting import transcription_terms
    terms = transcription_terms(caster['contract'], spell_level=spell.nivel)
    if terms is None:
        return None
    # Preserve a composição da prévia no registro da cobrança, sem usar foco
    # como identidade de subclasse ou como origem da lista de magias.
    terms = dict(terms)
    terms['base_cost_po'] = terms['cost_po']
    terms['base_time_hours'] = terms['time_hours']
    terms['rule_class'] = caster['pc'].id_classe.nome
    school = _ascii(spell.escola).replace(' ', '_')
    schools = (focus_schools(personagem) if focus_school_values is None
               else focus_school_values)
    discounted = bool(school and school in schools)
    if discounted:
        terms = dict(terms)
        terms['cost_po'] = terms['cost_po'] / 2
        terms['time_hours'] = terms['time_hours'] / 2
    terms['focus_discount'] = discounted
    terms['focus_school'] = spell.escola if discounted else ''
    terms['discount_percent'] = 50 if discounted else 0
    return terms
