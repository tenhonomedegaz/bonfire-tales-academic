"""Database-declared talent grants for adventure milestones, outside class ASIs."""
from types import SimpleNamespace
from django.db import transaction
from .models import TbOpcaojogo, TbPersonagem, TbPersonagemTalento, TbTalento
from .tag_engine.parser import ParseError, parse_tag

POLICY_TYPE = 'Marco de Progressao'
PREFIX = 'progression:'


def is_progression_talent(selected):
    return str(selected.detalhes or '').startswith(PREFIX)


def _requirements(tags):
    for raw in tags or []:
        try:
            nodes = parse_tag(raw).nodes
        except (ParseError, TypeError, ValueError):
            continue
        for node in nodes:
            if node.name != 'progression':
                continue
            values = {}
            for child in node.children:
                if child.name not in {'adventures', 'level'} or child.name in values:
                    return None
                try:
                    values[child.name] = int(child.value)
                except (TypeError, ValueError):
                    return None
            if set(values) == {'adventures', 'level'} and min(values.values()) >= 0:
                return values
    return None


def groups(personagem):
    from . import picks
    result = []
    class_levels = sum(int(level or 0) for level in personagem.classes.values_list('nivel', flat=True))
    for policy in TbOpcaojogo.objects.filter(tipo=POLICY_TYPE).order_by('slug'):
        req = _requirements(policy.tags_json)
        if (req is None or int(personagem.aventuras or 0) < req['adventures']
                or min(int(personagem.nivel or 0), class_levels) < req['level']):
            continue
        source = SimpleNamespace(nome=PREFIX + policy.slug, tags_json=policy.tags_json)
        resolved = picks.resolve_groups([source], personagem=personagem,
                                        nivel=personagem.nivel, kinds={'talento'})
        if len(resolved) == 1 and resolved[0]['n'] == 1:
            group = resolved[0]
            categories = picks._TALENTO_TIPO_RE.findall(picks._talento_constraint_text(group))
            category = categories[0].lower() if len(set(categories)) == 1 else None
            if (not group['usados'] and category
                    and personagem.talentos.filter(categoria=category, nivel__gte=req['level'])
                    .exclude(detalhes__startswith=PREFIX).exists()):
                # Preserve pre-existing manual grants of this milestone category.
                group['usados'], group['pendentes'] = 1, 0
            result.append((policy, resolved[0]))
    return result


def pending(personagem, ficha=None):
    from .views import _talento_attr_options, _talento_picks_contexto, _talento_prereq_ok
    from .character_engine import derive
    from .talent_presentation import attribute_presentation
    ficha = ficha if ficha is not None else derive(personagem)
    result = []
    for policy, group in groups(personagem):
        if not group['pendentes']:
            continue
        ids = {option['id'] for option in group['universo']}
        talents = []
        for talent in TbTalento.objects.filter(pk__in=ids).order_by('nome'):
            if not _talento_prereq_ok(talent, personagem, ficha):
                continue
            talents.append({
                'id': talent.pk, 'nome': talent.nome, 'descricao': talent.descricao or '',
                'attrs_csv': ','.join(_talento_attr_options(talent)),
                'picks': _talento_picks_contexto(talent, personagem),
                'aumento': attribute_presentation(talent.tags_json)['aumento_atributo'],
            })
        result.append({'slug': policy.slug, 'nome': policy.nome,
                       'descricao': policy.descricao or '', 'talentos': talents})
    return result


@transaction.atomic
def apply_choice(personagem, payload):
    from . import picks
    from .character_engine import derive
    from .views import _talento_attr_options, _talento_prereq_ok
    if not isinstance(payload, dict):
        return ['Escolha de marco invalida.']
    personagem = TbPersonagem.objects.select_for_update().get(pk=personagem.pk)
    selected = next(((policy, group) for policy, group in groups(personagem)
                     if policy.slug == payload.get('marco') and group['pendentes']), None)
    if selected is None:
        return ['Marco indisponivel ou escolha ja concedida.']
    policy, group = selected
    value = str(payload.get('talento') or '')
    option = next((row for row in group['universo'] if str(row['id']) == value), None)
    talent = TbTalento.objects.filter(pk=option['id']).first() if option else None
    attr = payload.get('talento_attr')
    if (talent is None or attr not in _talento_attr_options(talent)
            or not _talento_prereq_ok(talent, personagem, derive(personagem))):
        return ['Talento ou atributo invalido para este marco.']
    nested = picks.resolve_groups([talent], personagem=personagem, nivel=personagem.nivel)
    submitted = payload.get('talento_picks') or {}
    if not isinstance(submitted, dict):
        return ['Escolhas do talento invalidas.']
    choices = []
    for index, nested_group in enumerate(nested):
        values = submitted.get(str(index), [])
        if not isinstance(values, list) or picks.registry_entry(nested_group['kind'])['validate'](nested_group, values):
            return ['Complete as escolhas do talento.']
        choices.append((nested_group, values))
    group['slot_base'] = group['prox_slot']
    picks.registry_entry('talento')['persist'](personagem, group, [value])
    grant = TbPersonagemTalento.objects.get(id_personagem=personagem, id_talento=talent)
    grant.detalhes = '%s%s;talent_attr:%s' % (PREFIX, policy.slug, attr)
    grant.save(update_fields=['detalhes'])
    for nested_group, values in choices:
        nested_group['slot_base'] = nested_group.get('prox_slot', 0)
        picks.registry_entry(nested_group['kind'])['persist'](personagem, nested_group, values)
    return []
