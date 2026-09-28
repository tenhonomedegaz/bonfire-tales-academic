"""Hunter expertise choices, evaluated against the complete pinned sheet."""
from django.db import transaction
from django.utils.text import slugify
from .content_versions import resolve_content
from .hunter_preparation import preparation
from .models import TbPersonagem, TbPersonagemCacador, TbPersonagemEscolha
from .versioned_classes import EVALUATOR, VOCABULARY


def choice_state(profile, skills):
    data = resolve_content(profile.ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    spec = data.get('expertise')
    if spec is None:
        return None
    level = preparation(profile, selected=[], allow_pending_order=True)['level']
    selected = list(TbPersonagemEscolha.objects.filter(
        id_personagem=profile.personagem_classe.id_personagem,
        origem='hunter:%s:expertise' % profile.pk, tipo='hunter-expertise')
        .order_by('slot').values_list('valor', flat=True))
    options = [dict(s, id=slugify(s['nome']), selected=slugify(s['nome']) in selected)
               for s in skills if s['proficiente'] and s['atributo'] in spec['abilities']]
    limit = sum(level >= n for n in spec['levels'])
    return dict(selected=selected, options=options, limit=limit,
                remaining=max(0, limit-len(selected)),
                valid=len(selected) == len(set(selected)) and len(selected) <= limit
                      and set(selected) <= {s['id'] for s in options})


def apply_expertise(person, ruleset, skills, proficiency, warnings):
    if ruleset is None:
        return
    for profile in TbPersonagemCacador.objects.filter(
            personagem_classe__id_personagem=person).select_related('personagem_classe', 'ruleset'):
        if profile.ruleset_id != ruleset.pk:
            raise ValueError('Hunter profile and derived ruleset differ.')
        state = choice_state(profile, skills)
        if state is None:
            continue
        if not state['valid']:
            warnings.append('Instinto de Caçador exige regularização das perícias; escolhas preservadas.')
            continue
        for skill in skills:
            if slugify(skill['nome']) in state['selected'] and not skill['expertise']:
                skill['expertise'] = True
                skill['bonus'] += proficiency


@transaction.atomic
def save_expertise(*, character_id, owner_id, selected, expected_version):
    from .character_engine import derive
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de escolher perícias.')
    state = choice_state(profile, derive(person, ruleset=profile.ruleset)['pericias'])
    selected = list(selected)
    if (state is None or not state['valid'] or len(selected) != state['limit']
            or len(set(selected)) != len(selected)
            or not set(selected) <= {s['id'] for s in state['options']}
            or not set(state['selected']) <= set(selected)):
        raise ValueError('Escolha perícias distintas já proficientes de INT/SAB, preservando escolhas anteriores.')
    added = [s for s in selected if s not in state['selected']]
    for slot, value in enumerate(added, start=len(state['selected'])):
        TbPersonagemEscolha.objects.create(id_personagem=person,
            origem='hunter:%s:expertise' % profile.pk, tipo='hunter-expertise', slot=slot, valor=value)
    if added:
        profile.version += 1
        profile.save(update_fields=['version'])
    return profile
