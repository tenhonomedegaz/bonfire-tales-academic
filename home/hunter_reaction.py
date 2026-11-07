"""Pinned Swarm reaction uses; battlefield conditions are confirmed at the table."""
import hashlib
import json
import uuid
from django.db import transaction
from .content_versions import resolve_content
from .versioned_classes import EVALUATOR, VOCABULARY
from .hunter_preparation import preparation
from .character_engine import derive
from .models import TbPersonagem, TbPersonagemCacador, TbOperacaoRecurso
from .resource_engine import spend_resource


def panel(profile, ability):
    if ability not in ('int', 'wis'):
        raise ValueError('Escolha INT ou SAB para os usos da reação.')
    data = resolve_content(profile.ruleset, 'hunter-rework',
        evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY).get('swarm_reaction')
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if not data or prepared['order'] != data['order'] or prepared['level'] < data['level']:
        return None
    person = profile.personagem_classe.id_personagem
    sheet = derive(person, ruleset=profile.ruleset)
    maximum = max(1, sheet['atributos'][{'int':'INT','wis':'SAB'}[ability]]['mod'])
    contract = dict(key=f'hunter:{profile.pk}:reaction', name='Resposta Instintiva',
                    maximum=maximum, reset='short_or_long', origin='hunter-rework:' + ability)
    row = person.recursos.filter(chave=contract['key']).first()
    current = max(0, maximum - max(0, row.maximo-row.atual)) if row else maximum
    upgraded = prepared['level'] >= data['upgrade_level']
    token = [profile.pk, profile.version, profile.ruleset_id, ability, prepared['level'],
             row.pk if row else None, row.versao if row else 0, current, maximum]
    return dict(contract=contract, current=current, maximum=maximum, ability=ability,
        version=hashlib.sha256(json.dumps(token).encode()).hexdigest(), upgraded=upgraded,
        text=data['upgrade_text'] if upgraded else data['text'])


@transaction.atomic
def use(*, character_id, owner_id, ability, trigger, confirmed, operation_id, expected_version):
    person = TbPersonagem.objects.select_for_update().get(pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related('ruleset',
        'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    fingerprint = hashlib.sha256(json.dumps(['swarm-reaction', owner_id, ability, trigger,
        confirmed, expected_version]).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Operação já utilizada com outros dados.')
        return receipt.resposta
    current = panel(profile, ability)
    if current is None:
        raise ValueError('Resposta Instintiva indisponível nesta revisão, Ordem ou nível.')
    if current['version'] != expected_version:
        raise ValueError('Os usos mudaram. Recarregue a ficha.')
    row = person.recursos.filter(chave=current['contract']['key']).first()
    if row and row.atual < row.maximo and row.origem != current['contract']['origin']:
        raise ValueError('Mantenha o atributo dos usos gastos até recuperar a reserva no descanso.')
    if not confirmed or trigger not in ('attack', 'save') or (trigger == 'save' and not current['upgraded']):
        raise ValueError('Confirme a reação disponível e as condições de alcance e gatilho.')
    success, resource = spend_resource(person, current['contract'], 1)
    if not success:
        raise ValueError('Sem usos de Resposta Instintiva até o próximo descanso.')
    result = dict(current=resource['current'], maximum=resource['maximum'], spent=1,
        attack_disadvantage=trigger == 'attack', damage_resistance=current['upgraded'],
        movement_feet=30 if current['upgraded'] else 5, trigger=trigger,
        movement_after_resolution=current['upgraded'])
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
        fingerprint=fingerprint, resposta=result, status_http=200)
    return result
