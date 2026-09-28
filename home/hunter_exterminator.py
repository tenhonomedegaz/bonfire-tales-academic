"""Permanent choice for the Exterminator's conditional countermeasures."""
from django.db import transaction

from .hunter_preparation import preparation
from .models import TbPersonagem, TbPersonagemCacador, TbPersonagemEscolha


def protective_state(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['order'] != 'ordem-dos-exterminadores' or prepared['level'] < 6:
        return None
    row = TbPersonagemEscolha.objects.filter(
        id_personagem=profile.personagem_classe.id_personagem,
        origem='hunter:%s:protective' % profile.pk,
        tipo='hunter-protective', slot=0).first()
    if row and row.valor not in ('int', 'wis'):
        raise ValueError('A escolha de Contramedidas precisa ser regularizada.')
    return {'ability': row.valor if row else None, 'pending': row is None,
            'version': profile.version}


@transaction.atomic
def choose_protective(*, character_id, owner_id, ability, expected_version):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de escolher Contramedidas.')
    state = protective_state(profile)
    if state is None or ability not in ('int', 'wis'):
        raise ValueError('Contramedidas Protetivas indisponíveis nesta Ordem ou nível.')
    if not state['pending']:
        if state['ability'] == ability:
            return profile
        raise ValueError('A escolha de Contramedidas é permanente.')
    TbPersonagemEscolha.objects.create(id_personagem=person,
        origem='hunter:%s:protective' % profile.pk, tipo='hunter-protective',
        slot=0, valor=ability)
    profile.version += 1
    profile.save(update_fields=['version'])
    return profile
