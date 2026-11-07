"""Spend pinned Hunter secrets through existing resource counters and receipts."""
import hashlib
import json
import uuid

from django.db import transaction

from .hunter_preparation import preparation
from .hunter_rework import secret_cost
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemCacador
from .resource_engine import spend_resource


def contract(profile, prepared):
    return {'key': 'hunter:%s:secrets' % profile.pk, 'name': 'Pontos de Segredo',
            'maximum': prepared['points'], 'reset': 'long_rest', 'origin': 'hunter-rework'}


def state(profile, prepared):
    person = profile.personagem_classe.id_personagem
    spec = contract(profile, prepared)
    row = person.recursos.filter(chave=spec['key']).first()
    spent = max(0, row.maximo - row.atual) if row else 0
    current = max(0, spec['maximum'] - spent)
    token = [profile.pk, profile.version, profile.ruleset_id, prepared['level'],
             prepared['order'], prepared['selected'], row.pk if row else None,
             row.versao if row else 0, current, spec['maximum']]
    return {'current': current, 'maximum': spec['maximum'],
            'version': hashlib.sha256(json.dumps(token).encode()).hexdigest()}


@transaction.atomic
def use_secret(*, character_id, owner_id, secret_id, enhanced, operation_id, expected_version):
    if secret_id == 'cacada-final':
        raise ValueError('Declare Caçada Final ao aplicar a Marca do Caçador.')
    if secret_id == 'forma-primordial-suprema':
        raise ValueError('Ative Forma Primordial Suprema no painel do Companheiro Primordial.')
    if secret_id == 'despertar-final':
        raise ValueError('Ative Despertar Final no painel da Forma Desperta.')
    if secret_id == 'santuario-do-veu':
        raise ValueError('Registre o ritual ou a Palavra de Retorno no painel da Lanterna do Véu.')
    if secret_id == 'forma-quimerica':
        raise ValueError('Ative Forma Quimérica no painel de mutagênicos.')
    if secret_id in ('caminho-final',):
        raise ValueError('Este Segredo exclusivo aguarda o fluxo da Ordem; nenhum ponto foi gasto.')
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    fingerprint = hashlib.sha256(json.dumps([
        'hunter-secret', owner_id, secret_id, enhanced, expected_version]).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Esta operação já foi usada com outros dados.')
        return receipt.resposta
    prepared = preparation(profile)
    if state(profile, prepared)['version'] != expected_version:
        raise ValueError('Os recursos ou a preparação mudaram. Recarregue a ficha.')
    cost = secret_cost(prepared, secret_id, enhanced=enhanced)
    secret = next(row for row in prepared['available'] if row['id'] == secret_id)
    casting = None
    if secret.get('casting'):
        from .character_engine import derive
        sheet = derive(person, ruleset=profile.ruleset)
        sig = {'int': 'INT', 'wis': 'SAB'}[profile.ability]
        modifier = sheet['atributos'][sig]['mod']
        casting = dict(secret['casting'], ability=profile.ability,
                       save_dc=8 + sheet['bonus_proficiencia'] + modifier,
                       spell_attack=sheet['bonus_proficiencia'] + modifier)
    success, resource = spend_resource(person, contract(profile, prepared), cost)
    if not success:
        raise ValueError('Pontos de Segredo insuficientes.')
    response = {'secret': secret_id, 'enhanced': enhanced, 'spent': cost,
                'current': resource['current'], 'maximum': resource['maximum']}
    if casting is not None:
        response['casting'] = casting
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
