"""Pinned fighting-style selection; replacement consumes the current hunter level."""
import json
from contextvars import ContextVar
from types import SimpleNamespace
from django.db import transaction
from .hunter_preparation import preparation
from .models import TbPersonagem, TbPersonagemCacador, TbPersonagemEscolha
from .versioned_options import VersionedOptions

_suppress = ContextVar('hunter_style_prerequisites', default=False)


def style_state(profile):
    level = preparation(profile, selected=[], allow_pending_order=True)['level']
    catalog = VersionedOptions(profile.ruleset)
    options = catalog.universe(dict(tipo='estilo-de-luta', nivel=level,
        constraints={'from_kind': 'classe', 'from_slug': 'cacador'})) if level >= 2 else []
    person = profile.personagem_classe.id_personagem
    row = person.escolhas.filter(origem='hunter:%s:style' % profile.pk,
                                tipo='hunter-style', slot=0).first()
    saved = json.loads(row.valor) if row else None
    selected = next((o for o in options if saved and o['id'] == saved['id']), None)
    others = person.escolhas.exclude(tipo='hunter-style')
    occupied = set(others.values_list('id_opcao_id', flat=True))
    slugs = set(others.values_list('valor', flat=True))
    valid = not saved or bool(selected and selected['id'] not in occupied
                             and selected['slug'] not in slugs)
    return dict(level=level, selected=selected, saved=saved, valid=valid,
        options=[o for o in options if o['id'] not in occupied and o['slug'] not in slugs],
        can_change=level >= 2 and valid and (not saved or level > saved['level']))


def features(person, ruleset):
    if ruleset is None or _suppress.get():
        return []
    out = []
    for profile in TbPersonagemCacador.objects.filter(
            personagem_classe__id_personagem=person).select_related('ruleset', 'personagem_classe'):
        if profile.ruleset_id != ruleset.pk:
            raise ValueError('Hunter profile and derived ruleset differ.')
        state = style_state(profile)
        if state['valid'] and state['selected']:
            out += VersionedOptions(ruleset).selected_features([
                SimpleNamespace(id_opcao_id=state['selected']['id'], valor='')])
    return out


@transaction.atomic
def save_style(*, character_id, owner_id, selected, expected_version):
    from .character_engine import derive, _features_do_personagem
    from .views import _talento_prereq_ok, _prereq_label
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de escolher o estilo.')
    state = style_state(profile)
    option = next((o for o in state['options'] if str(o['id']) == str(selected)), None)
    if not state['valid'] or option is None:
        raise ValueError('Estilo indisponível para esta revisão, nível ou escolhas existentes.')
    if state['selected'] and option['id'] == state['selected']['id']:
        return profile
    if not state['can_change']:
        raise ValueError('A troca exige um novo nível de Caçador.')
    token = _suppress.set(True)
    try:
        sheet = derive(person, ruleset=profile.ruleset)
        sources = {_prereq_label(name): source for _, name, source, _ in
                   _features_do_personagem(person, ruleset=profile.ruleset)}
    finally:
        _suppress.reset(token)
    context = dict(owned=set(sources), sources=sources, choices=[], conjura=True,
        proficiencias={_prereq_label(v) for key in
            ('proficiencias_arma', 'proficiencias_armadura', 'ferramentas')
            for v in sheet.get(key, [])})
    if not _talento_prereq_ok(SimpleNamespace(pre_requisito=option['pre']), person, sheet, context):
        raise ValueError('Pré-requisitos do estilo não atendidos.')
    TbPersonagemEscolha.objects.update_or_create(id_personagem=person,
        origem='hunter:%s:style' % profile.pk, tipo='hunter-style', slot=0,
        defaults={'valor': json.dumps({'id': option['id'], 'level': state['level']}),
                  'id_opcao': None})
    profile.version += 1
    profile.save(update_fields=['version'])
    return profile
