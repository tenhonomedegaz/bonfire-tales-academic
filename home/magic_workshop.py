"""Produtos virtuais e regras mecânicas da Oficina de Magia."""
from __future__ import annotations

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


def scroll_offer(spell):
    level = int(spell.nivel or 0)
    if level not in SCROLL_PRICE_PO:
        return None
    rarity, save_dc, attack_bonus = SCROLL_STATS[level]
    materials = parse_priced_materials(spell.componentes)
    price = SCROLL_PRICE_PO[level] + materials['consumed_cost_po']
    return {
        'kind': 'scroll', 'slug': spell.slug, 'spell': spell,
        'name': f'Pergaminho de {spell.nome}', 'level': level,
        'price_po': price, 'base_price_po': SCROLL_PRICE_PO[level],
        'material_price_po': materials['consumed_cost_po'],
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


def character_casters(personagem):
    from .character_engine import _subclass_unlocked, spell_scope_names
    from .spellcasting import class_spellcasting_contract, max_spell_level_at

    rows = []
    for pc in personagem.classes.select_related('id_classe', 'id_subclasse'):
        level = int(pc.nivel or 1)
        subclass = pc.id_subclasse if _subclass_unlocked(pc, level) else None
        contract = class_spellcasting_contract(pc.id_classe, level=level, subclass=subclass)
        if not contract:
            continue
        contract['lista_nomes'] = spell_scope_names(contract.get('list') or []) or [pc.id_classe.nome]
        rows.append({
            'pc': pc, 'contract': contract,
            'max_spell_level': max_spell_level_at(
                contract, pc.id_classe, level=level, subclass=subclass,
                context={'classlvl': level}),
        })
    return rows


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


def focus_schools(personagem):
    """Escolas escolhidas ou concedidas pelo catálogo genérico de opções."""
    schools = set()
    for choice in personagem.escolhas.select_related('id_opcao'):
        option_type = _ascii(
            choice.id_opcao.tipo if choice.id_opcao_id else '').replace(' ', '_')
        if choice.tipo not in {'escola_de_foco', 'spell_school'} \
                and option_type != 'escola_de_foco':
            continue
        value = choice.id_opcao.slug if choice.id_opcao_id else choice.valor
        if value:
            schools.add(_ascii(value).replace(' ', '_'))
    return schools


def transcription_terms_for_character(personagem, caster, spell):
    from .spellcasting import transcription_terms
    terms = transcription_terms(caster['contract'], spell_level=spell.nivel)
    if terms is None:
        return None
    school = _ascii(spell.escola).replace(' ', '_')
    discounted = bool(school and school in focus_schools(personagem))
    if discounted:
        terms = dict(terms)
        terms['cost_po'] = terms['cost_po'] / 2
        terms['time_hours'] = terms['time_hours'] / 2
    terms['focus_discount'] = discounted
    return terms
