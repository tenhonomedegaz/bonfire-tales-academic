"""Declared Awakening Order form and exclusive secret, bound to a Hunter revision."""
import hashlib
import json
import uuid

from django.db import transaction

from .hunter_preparation import preparation
from .hunter_resources import contract
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemCacador
from .resource_engine import spend_resource
from .temporary_hp import grant_temporary_hp


ORDER = 'ordem-do-despertar'


def panel(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['level'] < 3 or prepared['order'] != ORDER:
        return None
    level = prepared['level']
    state = dict(profile.awakening or {})
    mark_active = bool((profile.mark or {}).get('active'))
    return dict(state, version=profile.version, level=level,
                ready=state.get('ready', True),
                remaining_seconds=state.get('remaining_seconds', 0),
                timeless=bool(state.get('active') and mark_active),
                final_eligible=any(secret['id'] == 'despertar-final'
                                   for secret in prepared['exclusive']),
                melee_bonus=3 if level >= 18 else 2 if level >= 11 else 1,
                unarmed_die='d12' if level >= 17 else 'd10' if level >= 11
                              else 'd8' if level >= 5 else 'd6',
                speed_bonus=10 if level >= 6 else 0,
                bloodied_heal='1d10 + modificador de %s' % profile.get_ability_display()
                    if level >= 6 else None,
                regeneration=level >= 10,
                elder=level >= 14,
                elder_ready=state.get('elder_ready', True),
                final_remaining_seconds=state.get('final_remaining_seconds', 0))


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version,
            action, confirmed, seconds=0, initial_howl=False):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    version = int(expected_version)
    seconds = int(seconds)
    fingerprint = hashlib.sha256(json.dumps([
        'hunter-awakening', owner_id, version, action, bool(confirmed), seconds,
        bool(initial_howl)],
        ensure_ascii=False).encode()).hexdigest()
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
    if initial_howl and action != 'activate':
        raise ValueError('O Uivo inicial só pode acompanhar a ativação da Forma.')
    state = dict(profile.awakening or {})
    if action == 'activate':
        if state.get('active') or not current['ready']:
            raise ValueError('Forma Desperta indisponível até o próximo descanso ou presa marcada derrotada.')
        state.update(active=True, ready=False, remaining_seconds=3600,
                     final=False, final_remaining_seconds=0,
                     initial_howl=bool(initial_howl))
    elif action == 'howl':
        if not state.get('active'):
            raise ValueError('Uivo Aterrador exige Forma Desperta ativa.')
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 2)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para Uivo Aterrador.')
        state['howl_count'] = state.get('howl_count', 0) + 1
    elif action == 'final':
        if not state.get('active') or state.get('final') or not current['final_eligible']:
            raise ValueError('Despertar Final exige Forma Desperta ativa e Segredo exclusivo disponível.')
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 4)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para Despertar Final.')
        state.update(final=True, final_remaining_seconds=60)
        grant_temporary_hp(person, 2 * current['level'], ruleset=profile.ruleset)
    elif action == 'elder_rescue':
        if (not current['elder'] or not state.get('active')
                or not current['elder_ready'] or person.pv_atual > 0):
            raise ValueError('Ímpeto Ancião exige nível 14, Forma ativa, 0 PV e uso disponível.')
        from .character_engine import derive
        from .epic_healing_bonus import healing_bonus, mark_healing_bonuses
        maximum = max(person.pv_maximo, derive(person, ruleset=profile.ruleset)['pv']['maximo_calculado'])
        bonus, pending = healing_bonus(person, hp=0, maximum_hp=maximum, ruleset=profile.ruleset)
        person.pv_atual = min(maximum, 2 * current['level'] + bonus)
        person.save(update_fields=['pv_atual'])
        if person.pv_atual:
            mark_healing_bonuses(person, pending)
        state['elder_ready'] = False
    elif action == 'elapsed':
        if not state.get('active') or not 1 <= seconds <= 86400:
            raise ValueError('Declare de 1 a 86400 segundos de Forma Desperta ativa.')
        if not current['timeless']:
            state['remaining_seconds'] = max(0, state.get('remaining_seconds', 0) - seconds)
        if state.get('final'):
            state['final_remaining_seconds'] = max(0, state['final_remaining_seconds'] - seconds)
            if not state['final_remaining_seconds']:
                state['final'] = False
        if not state['remaining_seconds'] and not current['timeless']:
            state.update(active=False, final=False, final_remaining_seconds=0)
    elif action in ('dismiss', 'unconscious', 'dead'):
        if not state.get('active'):
            raise ValueError('Não há Forma Desperta ativa.')
        state.update(active=False, final=False, final_remaining_seconds=0)
    else:
        raise ValueError('Evento de Forma Desperta inválido.')
    state['last_event'] = action
    profile.awakening = state
    profile.version += 1
    profile.save(update_fields=['awakening', 'version'])
    response = dict(state, version=profile.version)
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
                                     fingerprint=fingerprint, resposta=response, status_http=200)
    return response


def on_marked_prey_death(profile):
    """Called under the mark transaction lock; caller persists the profile once."""
    if panel(profile) is None:
        return False
    state = dict(profile.awakening or {})
    if state.get('ready', True):
        return False
    state['ready'] = True
    profile.awakening = state
    return True


def grant_rest(person, event):
    if event not in ('short_rest', 'long_rest'):
        return
    for profile in TbPersonagemCacador.objects.select_for_update().select_related(
            'ruleset', 'personagem_classe').filter(personagem_classe__id_personagem=person):
        if panel(profile) is None:
            continue
        state = dict(profile.awakening or {})
        changed = not state.get('ready', True)
        state['ready'] = True
        if event == 'long_rest' and not state.get('elder_ready', True):
            state['elder_ready'] = True
            changed = True
        if changed:
            profile.awakening = state
            profile.version += 1
            profile.save(update_fields=['awakening', 'version'])
