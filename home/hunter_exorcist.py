"""Linked Exorcist Reaper Form, with declared game time and atomic costs."""
import hashlib
import json
import uuid

from django.db import transaction

from .hunter_preparation import preparation
from .hunter_resources import contract
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemCacador
from .resource_engine import spend_resource


ORDER = 'ordem-dos-exorcistas'


def _slot_rows(profile):
    from .character_engine import derive
    from .views import _magias_sheet_info
    person = profile.personagem_classe.id_personagem
    sheet = derive(person, ruleset=profile.ruleset)
    return [row for row in _magias_sheet_info(person, sheet, [],
        ruleset=profile.ruleset)['slots'] if row['nivel'] >= 2 and row['total']]


def panel(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['order'] != ORDER or prepared['level'] < 6:
        return None
    state = dict(profile.exorcist or {})
    return dict(state, version=profile.version, level=prepared['level'],
                free_ready=state.get('free_ready', True),
                remaining_seconds=state.get('remaining_seconds', 0),
                immortal=prepared['level'] >= 14,
                slot_options=_slot_rows(profile))


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version,
            action, confirmed, mode='', slot_level=0, slot_version='', seconds=0):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    version = int(expected_version)
    slot_level, seconds = int(slot_level), int(seconds)
    fingerprint = hashlib.sha256(json.dumps([
        'hunter-reaper-form', owner_id, version, action, bool(confirmed),
        mode, slot_level, slot_version, seconds], ensure_ascii=False).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person,
                                                operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Operação já usada com outros dados.')
        return receipt.resposta
    current = panel(profile)
    if current is None or version != profile.version:
        raise ValueError('A Ordem, a revisão ou a ficha mudou. Recarregue a preparação.')
    if not confirmed:
        raise ValueError('Confirme o evento declarado na mesa.')
    state = dict(profile.exorcist or {})
    if action == 'activate':
        if state.get('active') or mode not in ('free', 'secrets', 'slot'):
            raise ValueError('Forma do Ceifador já ativa ou método de ativação inválido.')
        if mode == 'free':
            if not current['free_ready']:
                raise ValueError('Uso gratuito da Forma do Ceifador já gasto.')
            state['free_ready'] = False
        elif mode == 'secrets':
            success, _ = spend_resource(person, contract(profile, preparation(profile)), 2)
            if not success:
                raise ValueError('Pontos de Segredo insuficientes para Forma do Ceifador.')
        else:
            slot = next((row for row in current['slot_options']
                         if row['nivel'] == slot_level), None)
            if slot is None or slot['version'] != slot_version or not slot['atual']:
                raise ValueError('Espaço de magia indisponível ou alterado. Recarregue a ficha.')
            success, _ = spend_resource(person, {
                'key': 'spell-slot:%d' % slot_level,
                'legacy_name': 'spell-slot:%d' % slot_level,
                'name': 'spell-slot:%d' % slot_level,
                'maximum': slot['total'], 'reset': 'long_rest',
                'origin': 'spellcasting'}, 1)
            if not success:
                raise ValueError('Espaço de magia insuficiente para Forma do Ceifador.')
        state.update(active=True, remaining_seconds=60, last_method=mode)
    elif action == 'elapsed':
        if not state.get('active') or not 1 <= seconds <= 86400:
            raise ValueError('Declare de 1 a 86400 segundos de Forma do Ceifador ativa.')
        state['remaining_seconds'] = max(0, state['remaining_seconds'] - seconds)
        if not state['remaining_seconds']:
            state['active'] = False
    elif action == 'dismiss':
        if not state.get('active'):
            raise ValueError('Não há Forma do Ceifador ativa.')
        state.update(active=False, remaining_seconds=0)
    else:
        raise ValueError('Evento de Forma do Ceifador inválido.')
    state['last_event'] = action
    profile.exorcist = state
    profile.version += 1
    profile.save(update_fields=['exorcist', 'version'])
    response = dict(state, version=profile.version)
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
                                     fingerprint=fingerprint, resposta=response, status_http=200)
    return response


def grant_rest(person, event):
    if event not in ('short_rest', 'long_rest'):
        return
    for profile in TbPersonagemCacador.objects.select_for_update().select_related(
            'ruleset', 'personagem_classe').filter(personagem_classe__id_personagem=person):
        prepared = preparation(profile, selected=[], allow_pending_order=True)
        if prepared['order'] != ORDER or prepared['level'] < 6:
            continue
        state = dict(profile.exorcist or {})
        changed = bool(state.get('active'))
        state.update(active=False, remaining_seconds=0)
        if event == 'long_rest' and not state.get('free_ready', True):
            state['free_ready'] = True
            changed = True
        if changed:
            profile.exorcist = state
            profile.version += 1
            profile.save(update_fields=['exorcist', 'version'])
