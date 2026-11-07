"""Owner-declared hunting journal; game time and target events are explicit.

This does not mutate VTT actors or add target bonuses to the permanent sheet.
"""
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation
from django.db import transaction
from .content_versions import resolve_content
from .models import TbPersonagem, TbPersonagemCacador, TbOperacaoRecurso
from .versioned_classes import EVALUATOR, VOCABULARY


def panel(profile):
    pc = profile.personagem_classe
    payload = resolve_content(profile.ruleset, 'class-catalog:%s' % pc.id_classe_id,
        evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
    spec = payload.get('hunter_mark_replacement')
    if spec is None:
        return None
    if spec.get('version') != 1 or spec.get('duration_seconds') != 3600:
        raise ValueError('Contrato de Marca incompatível.')
    level = pc.nivel
    if not 1 <= level <= 20:
        raise ValueError('Nível de Caçador inválido.')
    die = 12 if level >= 17 else 10 if level >= 11 else 8 if level >= 5 else 6
    from .hunter_preparation import preparation
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    final_hunt_eligible = any(secret['id'] == 'cacada-final'
                              for secret in prepared['exclusive'])
    exterminator = prepared['order'] == 'ordem-dos-exterminadores' and level >= 3
    exorcist = prepared['order'] == 'ordem-dos-exorcistas' and level >= 3
    hunt_active = bool(profile.mark.get('active') and profile.mark.get('final_hunt')
                       and profile.mark.get('final_hunt_remaining_seconds', 0) > 0)
    return dict(profile.mark, version=profile.version, duration_seconds=3600,
        damage='%sd%s' % (2 if hunt_active else 1, die),
        final_hunt=hunt_active, final_hunt_eligible=final_hunt_eligible,
        anticipation_eligible=exterminator,
        mortuary_eligible=exorcist,
        mortuary_damage_type=(profile.mark.get('mortuary_damage_type')
                              if exorcist and profile.mark.get('active') else None),
        mortuary_bleeding_bonus=prepared['proficiency'] if exorcist and profile.mark.get('active') else 0,
        inquisition_available=exterminator and bool(profile.mark.get('active')),
        dispel_circle=min(9, level // 2), during_attack=level >= 11)


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version,
            action, target='', seconds=0, confirmed=False, final_hunt=False,
            anticipate=False, clues=(), target_type='', same_plane=False,
            distance_miles='', defenses=None, mortuary_damage_type=''):
    person = TbPersonagem.objects.select_for_update().get(pk=character_id,
        dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    version = int(expected_version)
    seconds = int(seconds)
    target = str(target).strip()
    final_hunt = bool(final_hunt)
    anticipate = bool(anticipate)
    clues = [str(clue).strip() for clue in clues]
    target_type = str(target_type).strip()
    mortuary_damage_type = str(mortuary_damage_type).strip().lower()
    defenses = {key: str((defenses or {}).get(key, '')).strip()
                for key in ('immunities', 'resistances', 'vulnerabilities',
                            'condition_immunities')}
    receipt_data = ['hunter-mark', owner_id, version, action, target, seconds, confirmed]
    if final_hunt:
        receipt_data.append('final-hunt')
    if anticipate:
        receipt_data.append(['anticipate', clues, target_type, bool(same_plane),
                             str(distance_miles)])
    if action == 'inquisition':
        receipt_data.append(['inquisition', defenses])
    if mortuary_damage_type:
        receipt_data.append(['mortuary', mortuary_damage_type])
    fingerprint = hashlib.sha256(json.dumps(receipt_data, ensure_ascii=False).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Operação já usada com outros dados.')
        return receipt.resposta
    current = panel(profile)
    if current is None or version != profile.version:
        raise ValueError('A revisão ou a ficha mudou. Recarregue antes de registrar a Marca.')
    if not confirmed:
        raise ValueError('Confirme as condições declaradas na mesa.')
    if final_hunt and action != 'apply':
        raise ValueError('Caçada Final só pode ser declarada ao aplicar a Marca.')
    if anticipate and action != 'apply':
        raise ValueError('Marca Antecipada só pode ser declarada ao aplicar a Marca.')
    if mortuary_damage_type and action != 'apply':
        raise ValueError('Escolha o tipo da Marca Mortuária apenas ao aplicar a Marca.')
    state = dict(profile.mark)
    if action == 'apply':
        if not target or len(target) > 160:
            raise ValueError('Identifique a presa em até 160 caracteres.')
        if current['mortuary_eligible']:
            if mortuary_damage_type not in ('radiante', 'frio'):
                raise ValueError('Escolha dano radiante ou de frio para Marca Mortuária.')
        elif mortuary_damage_type:
            raise ValueError('Marca Mortuária é exclusiva dos Exorcistas.')
        if anticipate:
            if not current['anticipation_eligible']:
                raise ValueError('Marca Antecipada indisponível nesta Ordem ou nível.')
            if (seconds < 600 or len(clues) < 3 or len(clues) > 10
                    or any(not clue or len(clue) > 160 for clue in clues)
                    or len({clue.casefold() for clue in clues}) < 3
                    or not target_type or len(target_type) > 80):
                raise ValueError('Investigue 10 minutos e registre três pistas diferentes e o tipo da presa.')
            try:
                distance = Decimal(str(distance_miles))
            except InvalidOperation as exc:
                raise ValueError('Informe a distância da presa em milhas.') from exc
            if not same_plane or not distance.is_finite() or not 0 <= distance <= 5:
                raise ValueError('O rastro esfriou: a presa deve estar no mesmo plano e a até 5 milhas.')
        if final_hunt:
            if not current['final_hunt_eligible']:
                raise ValueError('Caçada Final indisponível nesta Ordem ou nível.')
            from .hunter_preparation import preparation
            from .hunter_resources import contract
            from .resource_engine import spend_resource
            prepared = preparation(profile)
            secret = next(s for s in prepared['exclusive'] if s['id'] == 'cacada-final')
            success, _resource = spend_resource(person, contract(profile, prepared), secret['cost'])
            if not success:
                raise ValueError('Pontos de Segredo insuficientes para Caçada Final.')
        state = dict(target=target, active=True, remaining_seconds=current['duration_seconds'],
                     reason='', final_hunt=final_hunt,
                     final_hunt_remaining_seconds=60 if final_hunt else 0,
                     anticipated=anticipate,
                     clues=clues if anticipate else [],
                     target_type=target_type if anticipate else '',
                     mortuary_damage_type=mortuary_damage_type if current['mortuary_eligible'] else '')
    elif action == 'inquisition':
        if not current['inquisition_available'] or not state.get('active'):
            raise ValueError('Inquisição exige uma presa marcada pelos Exterminadores.')
        if any(len(value) > 300 for value in defenses.values()):
            raise ValueError('Resuma cada defesa em até 300 caracteres.')
        state['defenses'] = defenses
    elif action in ('elapsed', 'incapacitated', 'recovered', 'dead', 'dispelled', 'dismissed'):
        if not state.get('active'):
            raise ValueError('Não há Marca ativa.')
        if action in ('elapsed', 'incapacitated'):
            if not 1 <= seconds <= 86400:
                raise ValueError('Informe de 1 a 86400 segundos de tempo de jogo.')
            state['remaining_seconds'] = max(0, state['remaining_seconds'] - seconds)
            if state.get('final_hunt'):
                state['final_hunt_remaining_seconds'] = max(0,
                    state.get('final_hunt_remaining_seconds', 0) - seconds)
                if not state['final_hunt_remaining_seconds']:
                    state['final_hunt'] = False
            if action == 'incapacitated':
                state['incapacitated_seconds'] = state.get('incapacitated_seconds', 0) + seconds
            if action == 'incapacitated' and state['incapacitated_seconds'] > 60:
                state.update(active=False, reason='incapacitated')
            elif state['remaining_seconds'] == 0:
                state.update(active=False, reason='expired')
        elif action == 'recovered':
            state['incapacitated_seconds'] = 0
        else:
            state.update(active=False, reason=action)
    else:
        raise ValueError('Evento de Marca inválido.')
    profile.mark = state
    awakening_recovered = False
    if action == 'dead':
        from .hunter_awakening import on_marked_prey_death
        awakening_recovered = on_marked_prey_death(profile)
    profile.version += 1
    profile.save(update_fields=['mark', 'awakening', 'version']
                 if awakening_recovered else ['mark', 'version'])
    response = dict(state, version=profile.version)
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
