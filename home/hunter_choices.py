"""Permanent favored-enemy picks for explicitly bound Hunter profiles."""
from django.db import transaction

from .content_versions import resolve_content
from .hunter_preparation import preparation
from .models import TbPersonagem, TbPersonagemCacador, TbPersonagemEscolha
from .versioned_classes import EVALUATOR, VOCABULARY


def favored_state(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    data = resolve_content(profile.ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    spec = data.get('favored_enemies')
    if spec is None:
        return None  # A sealed older draft must not acquire new choices implicitly.
    rows = TbPersonagemEscolha.objects.filter(
        id_personagem=profile.personagem_classe.id_personagem,
        origem='hunter:%s:favored' % profile.pk, tipo='hunter-favored').order_by('slot')
    selected_rows = list(rows.values_list('valor', flat=True))
    deferred = list((profile.regularization or {}).get('deferred_favored', []))
    allowed = {item['id'] for item in spec['types']}
    limit = sum(prepared['level'] >= level for level in spec['levels'])
    activated = deferred[:max(0, limit - len(selected_rows))]
    selected = selected_rows + activated
    pending = [item for item in spec['types']
               if item['id'] in deferred and item['id'] not in activated]
    return {'selected': selected, 'limit': limit, 'remaining': max(0, limit - len(selected)),
            'valid': len(selected) <= limit and len(selected) == len(set(selected))
                     and set(selected) <= allowed and len(deferred) == len(set(deferred))
                     and set(deferred) <= allowed
                     and not set(deferred) & set(selected_rows),
            'pending_legacy': pending,
            'options': [dict(item, selected=item['id'] in selected) for item in spec['types']]}


@transaction.atomic
def save_favored(*, character_id, owner_id, selected, expected_version):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de escolher Inimigos Favoritos.')
    state = favored_state(profile)
    if state is None or not state['valid']:
        raise ValueError('A revisão ou as escolhas precisam de regularização.')
    selected = list(selected)
    if (len(selected) != state['limit'] or len(set(selected)) != len(selected)
            or not set(selected) <= {o['id'] for o in state['options']}):
        raise ValueError('Escolha tipos distintos no limite do seu nível de Caçador.')
    if not set(state['selected']) <= set(selected):
        raise ValueError('Inimigos Favoritos já escolhidos não podem ser substituídos neste fluxo.')
    added = [value for value in selected if value not in state['selected']]
    for slot, value in enumerate(added, start=len(state['selected'])):
        TbPersonagemEscolha.objects.create(id_personagem=person,
            origem='hunter:%s:favored' % profile.pk, tipo='hunter-favored', slot=slot, valor=value)
    if added:
        profile.version += 1
        profile.save(update_fields=['version'])
    return profile
