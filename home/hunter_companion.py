"""Primordial Companion lifecycle with the adopted Battle Familiar base block."""
import hashlib
import json
import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .hunter_preparation import preparation
from .battle_familiar import FORMS, stat_block
from .hunter_resources import contract
from .hunter_spellcasting import progression_at
from .models import (TbOperacaoRecurso, TbPersonagem, TbPersonagemCacador,
                     TbPersonagemEstado, TbPersonagemMagia)
from .resource_engine import spend_resource


ORDER = 'ordem-da-alianca-selvagem'
TYPES = {'Celestial', 'Dragão', 'Fera', 'Feérico', 'Ínfero'}
EVOLUTIONS = {
    'audicao-faro': 'Audição e Faro Aguçados',
    'camuflagem': 'Camuflagem Natural',
    'escalada': 'Escalada Aracnídea',
    'folego': 'Fôlego Prolongado',
    'anfibio': 'Anfíbio',
    'matilha': 'Táticas de Matilha',
    'alcance': 'Alcance Estendido',
    'ecolocalizacao': 'Ecolocalização',
    'investida': 'Investida',
}
ELEMENTS = ('Ácido', 'Elétrico', 'Fogo', 'Frio', 'Trovejante')
BREATH = ELEMENTS + ('Veneno',)
OPTIONS = [dict(id=key, label=label) for key, label in EVOLUTIONS.items()]
OPTIONS += [dict(id='resistencia:' + key.lower(), label='Resistência Elemental: ' + key)
            for key in ELEMENTS]
OPTIONS += [dict(id='sopro:' + key.lower(), label='Sopro Primordial: ' + key)
            for key in BREATH]
VALID = {option['id'] for option in OPTIONS}
EVOLUTION_EFFECTS = {
    'audicao-faro': 'Vantagem em Sabedoria (Percepção) baseada em audição ou olfato.',
    'camuflagem': 'Vantagem em Destreza (Furtividade) em terreno natural, Penumbra ou Escuridão.',
    'escalada': 'Escalada igual ao deslocamento de caminhada; percorre paredes e tetos sem teste de habilidade.',
    'folego': 'Pode prender a respiração por 1 hora.',
    'anfibio': 'Pode respirar ar e água.',
    'matilha': 'Vantagem nos ataques contra criatura com aliado a até 5 pés dela, se o aliado não estiver Incapacitado.',
    'alcance': 'Alcance dos ataques corpo a corpo aumenta em 5 pés.',
    'ecolocalizacao': 'Visão às Cegas de 30 pés; indisponível enquanto estiver Surdo.',
}


def _eligible(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    return prepared if prepared['level'] >= 3 and prepared['order'] == ORDER else None


def _circle(profile, level):
    row = progression_at(profile.personagem_classe.id_classe, level, profile.ruleset)
    if row is None:
        raise ValueError('A revisão não contém a progressão de magia do Caçador.')
    return max(2, max((i for i, count in enumerate(row['slots'], 1) if count), default=0))


def companion_block(state, level, proficiency, spell_attack):
    block = stat_block(9 if state.get('supreme') else state['circle'],
                       state['battle_form'], spell_attack)
    block['hp_max'] += 10 * level
    block['hp_current'] = max(0, block['hp_max'] - state.get('damage', 0))
    block['ac'] += proficiency
    block['check_save_bonus'] += proficiency
    for attribute in block['attributes']:
        attribute['save'] += proficiency
    block['size'] = ('Enorme' if state.get('supreme') else
                     ('Grande' if state.get('large') else block['size']))
    if 'alcance' in state.get('evolutions', []):
        block['reach_m'] += 1.5
    block['climb_m'] = block['walk_m'] if 'escalada' in state.get('evolutions', []) else 0
    return block


def panel(profile):
    prepared = _eligible(profile)
    if prepared is None:
        return None
    level = prepared['level']
    state = dict(profile.companion or {})
    maximum = 1 + sum(level >= milestone for milestone in (6, 10, 14, 18))
    from .character_engine import derive
    sheet = derive(profile.personagem_classe.id_personagem, ruleset=profile.ruleset)
    proficiency = sheet['bonus_proficiencia']
    attrs = sheet['atributos']
    ability_key = {'int': 'INT', 'wis': 'SAB'}[profile.ability]
    spell_dc = 8 + proficiency + attrs[ability_key]['mod']
    from .hunter_choices import favored_state
    favored = favored_state(profile)
    favored_types = ([row['name'] for row in favored['options'] if row['selected']]
                     if favored and favored['valid'] else [])
    favored_damage = max(1, attrs[ability_key]['mod']) if favored_types else 0
    breath_dice = max(1, attrs['INT']['mod'], attrs['SAB']['mod'])
    breath = next((key.partition(':')[2] for key in state.get('evolutions', [])
                   if key.startswith('sopro:')), '')
    exclusive = any(row['id'] == 'forma-primordial-suprema'
                    for row in prepared['exclusive'])
    selected_labels = [next((option['label'] for option in OPTIONS
                             if option['id'] == key), key)
                       for key in state.get('evolutions', [])]
    evolution_effects = []
    for key in state.get('evolutions', []):
        effect = EVOLUTION_EFFECTS.get(key)
        if key == 'investida':
            effect = ('Após mover 20 pés em linha reta até o alvo e acertar Retalhar no mesmo turno: '
                      'dano adicional de 1%s; Força CD %d ou Caído.'
                      % (prepared['progression']['hunter_die'], spell_dc))
        elif key.startswith('resistencia:') and key in VALID:
            effect = 'Resistência a dano de %s.' % key.partition(':')[2]
        elif key.startswith('sopro:') and key in VALID:
            effect = ('Pode substituir um Retalhar por Sopro Primordial; '
                      'uma vez por turno, cone de 15 pés, Destreza CD %d.' % spell_dc)
        if effect:
            evolution_effects.append(effect)
    shared_spells = []
    if state.get('active') and state.get('summon_id'):
        shared_spells = [effect.payload_json.get('spell_name') for effect in
            profile.personagem_classe.id_personagem.estados.filter(
                ativo=True, chave__startswith='spell:')
            if effect.payload_json.get('shared_companion_summon_id') == state['summon_id']]
    block = (companion_block(state, level, proficiency, spell_dc - 8)
             if state.get('battle_form') in FORMS else None)
    return dict(state, version=profile.version, level=level, block=block,
                battle_forms=FORMS,
                evolution_labels=selected_labels,
                evolution_effects=evolution_effects,
                free_ready=state.get('free_ready', True),
                available_circle=_circle(profile, level),
                circle=9 if state.get('supreme') else state.get('circle'),
                hp_bonus=10 * level, ac_bonus=proficiency,
                check_save_bonus=proficiency, evolution_limit=maximum,
                favored_types=favored_types, favored_damage=favored_damage,
                favored_pending=(favored['remaining'] if favored and favored['valid'] else None),
                options=OPTIONS, command_replaces_attack=level >= 6,
                shared_instinct=level >= 6,
                rend_attacks=2 if level >= 10 else 1,
                breath_type=breath,
                breath_damage='%d%s' % (breath_dice, prepared['progression']['hunter_die']) if breath else '',
                breath_dc=spell_dc if breath else None,
                large_grapple_advantage=bool(state.get('active') and state.get('large')
                                             and not state.get('supreme') and level >= 10),
                shared_mark_damage=prepared['progression']['hunter_die'] if level >= 10 else '',
                shared_mark_ready=bool(level >= 10 and state.get('active')
                                       and profile.mark.get('active')),
                large_available=level >= 10,
                spell_sharing=level >= 14, shared_spells=shared_spells,
                supreme_eligible=exclusive)


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version,
            action, confirmed, form='', creature_type='', evolutions=None, large=False,
            seconds=0, turn_key='', command_mode='bonus', rend_count=1,
            extra_rend=False, target='', spell_state_key='',
            self_only_no_area=False, companion_within_9m=False,
            battle_form='', hp_amount=0):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    version = int(expected_version)
    evolutions = list(evolutions or [])
    seconds = int(seconds)
    rend_count = int(rend_count)
    hp_amount = int(hp_amount)
    target = str(target).strip()
    command_data = [
        'hunter-companion', owner_id, version, action, confirmed,
        form, creature_type, evolutions, bool(large), seconds,
        str(turn_key).strip() if action in ('breath', 'command', 'stalk', 'mark_hit') else '',
        command_mode if action in ('command', 'breath', 'stalk') else '',
        rend_count if action == 'command' else 0,
        bool(extra_rend) if action in ('breath', 'stalk') else False,
        target if action == 'mark_hit' else '',
        spell_state_key if action == 'share_spell' else '',
        bool(self_only_no_area) if action == 'share_spell' else False,
        bool(companion_within_9m) if action == 'share_spell' else False,
        battle_form if action in ('summon', 'choose_block') else '',
        hp_amount if action in ('damage', 'heal', 'choose_block') else 0]
    fingerprint = hashlib.sha256(json.dumps(command_data,
        ensure_ascii=False).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person,
                                                operation_id=operation_id).first()
    if receipt:
        compatible = {fingerprint}
        if not battle_form and not hp_amount and action not in ('damage', 'heal', 'choose_block', 'stalk'):
            compatible.add(hashlib.sha256(json.dumps(command_data[:-2],
                ensure_ascii=False).encode()).hexdigest())
        if receipt.fingerprint not in compatible:
            raise ValueError('Operação já usada com outros dados.')
        return receipt.resposta
    current = panel(profile)
    if current is None or version != profile.version:
        raise ValueError('A Ordem, a revisão ou a ficha mudou. Recarregue a preparação.')
    if not confirmed:
        raise ValueError('Confirme o evento declarado na mesa.')
    state = dict(profile.companion or {})
    if action == 'summon':
        stat_block(current['available_circle'], battle_form)
        from .battle_familiar_casting import KEY, find_states, sync_locked
        sync_locked(person)
        if (person.estados.filter(chave=KEY, ativo=True).exists()
                or find_states(person) or find_states(person, 'Battle Familiar')):
            raise ValueError('Já existe um familiar comum. Encerre seu vínculo na Oficina antes de invocar o Companheiro Primordial.')
        form = str(form).strip()
        if not form or len(form) > 120 or creature_type not in TYPES:
            raise ValueError('Informe uma aparência e um tipo de espírito válidos.')
        if (len(evolutions) != current['evolution_limit']
                or len(evolutions) != len(set(evolutions))
                or any(evolution not in VALID for evolution in evolutions)
                or sum(e.startswith('sopro:') for e in evolutions) > 1):
            raise ValueError('Escolha as Evoluções Totêmicas disponíveis para este nível.')
        if large and not current['large_available']:
            raise ValueError('Forma Grande só está disponível a partir do nível 10.')
        free = current['free_ready']
        if not free:
            prepared = preparation(profile)
            success, _ = spend_resource(person, contract(profile, prepared), 1)
            if not success:
                raise ValueError('Ponto de Segredo insuficiente para o ritual de 1 minuto.')
        state = dict(active=True, form=form, creature_type=creature_type,
                     battle_form=battle_form, damage=0,
                     evolutions=evolutions, large=bool(large),
                     summon_id=str(operation_id), summoned_at=timezone.now().isoformat(),
                     circle=current['available_circle'], free_ready=False,
                     last_event='summoned', cost=0 if free else 1,
                     breath_turns=list(state.get('breath_turns', [])),
                     command_turns=list(state.get('command_turns', [])))
    elif action == 'choose_block':
        if not state.get('active') or current['block']:
            raise ValueError('A escolha do bloco é somente para uma invocação antiga sem forma registrada.')
        block = stat_block(current['circle'], battle_form)
        maximum_hp = block['hp_max'] + current['hp_bonus']
        if not 1 <= hp_amount <= maximum_hp:
            raise ValueError('Informe os PV atuais da invocação, entre 1 e o máximo do bloco escolhido.')
        state.update(battle_form=battle_form, damage=maximum_hp - hp_amount,
                     last_event=action)
    elif action in ('damage', 'heal'):
        if not state.get('active') or not current['block'] or not 1 <= hp_amount <= 100000:
            raise ValueError('Selecione o bloco e informe uma quantidade positiva de dano ou cura.')
        block = current['block']
        remaining = max(0, min(block['hp_max'], block['hp_current'] +
                              (hp_amount if action == 'heal' else -hp_amount)))
        state.update(damage=block['hp_max'] - remaining, last_event=action)
        if remaining == 0:
            state.update(active=False, supreme=False)
    elif action == 'share_spell':
        if (not current['spell_sharing'] or not state.get('active')
                or not state.get('summon_id') or not state.get('summoned_at')
                or not self_only_no_area or not companion_within_9m):
            raise ValueError('Comunhão Primordial exige espírito ativo, magia pessoal sem área e alcance de 9 m.')
        if not str(spell_state_key).startswith('spell:'):
            raise ValueError('Escolha uma conjuração persistente registrada na Oficina.')
        effect = TbPersonagemEstado.objects.select_for_update().get(
            id_personagem=person, chave=spell_state_key, ativo=True,
            origem__startswith='magia:')
        payload = dict(effect.payload_json or {})
        owned_id = payload.get('owned_id')
        owned = TbPersonagemMagia.objects.select_related('id_magia').get(
            pk=owned_id, id_personagem=person, id_magia_id=payload.get('spell_id'))
        if (payload.get('shared_companion_summon_id')
                or not owned.id_magia or (owned.id_magia.alcance or '').strip().casefold()
                    not in ('auto', 'pessoal', 'self')
                or effect.iniciado_em < parse_datetime(state['summoned_at'])):
            raise ValueError('A magia precisa ser pessoal, posterior à invocação e ainda não compartilhada.')
        payload['shared_companion_summon_id'] = state['summon_id']
        effect.payload_json = payload
        effect.save(update_fields=['payload_json'])
        state['last_shared_spell'] = dict(name=payload.get('spell_name') or owned.nome,
                                          key=spell_state_key)
        state['last_event'] = action
    elif action in ('command', 'breath', 'stalk'):
        turn_key = str(turn_key).strip()
        turns = list(state.get('command_turns', []))
        if (not state.get('active') or not turn_key or len(turn_key) > 120
                or turn_key in turns or turn_key in state.get('breath_turns', [])):
            raise ValueError('Comando exige espírito ativo e turno ainda não usado.')
        if (command_mode not in ('bonus', 'attack')
                or command_mode == 'attack' and not current['command_replaces_attack']):
            raise ValueError('Modo de Comando indisponível neste nível.')
        if action == 'command':
            if rend_count < 1 or rend_count > current['rend_attacks']:
                raise ValueError('Modo ou quantidade de Retalhar indisponível neste nível.')
            state['last_command'] = dict(turn=turn_key, mode=command_mode,
                                         action='Retalhar', rend_attacks=rend_count,
                                         reaction_spent=True)
        elif action == 'stalk':
            if not current['block'] or not current['block']['stalk']:
                raise ValueError('Espreitar exige forma Espreitador.')
            if extra_rend and current['rend_attacks'] < 2:
                raise ValueError('Retalhar adicional exige Ataques Primordiais.')
            state['last_command'] = dict(turn=turn_key, mode=command_mode,
                                         action='Espreitar', rend_attacks=1 if extra_rend else 0,
                                         reaction_spent=True)
        else:
            if not current['breath_type']:
                raise ValueError('Sopro Primordial exige evolução escolhida.')
            if extra_rend and current['rend_attacks'] < 2:
                raise ValueError('Retalhar adicional exige Ataques Primordiais.')
            state['breath_turns'] = list(state.get('breath_turns', [])) + [turn_key]
            state['last_breath'] = dict(turn=turn_key, damage=current['breath_damage'],
                                        damage_type=current['breath_type'], dc=current['breath_dc'],
                                        area='cone de 15 pés', save='Destreza',
                                        on_success='metade')
            state['last_command'] = dict(turn=turn_key, mode=command_mode,
                                         action='Sopro Primordial',
                                         rend_attacks=1 if extra_rend else 0,
                                         reaction_spent=True)
        state['command_turns'] = turns + [turn_key]
        state['last_event'] = action
    elif action == 'mark_hit':
        turn_key = str(turn_key).strip()
        commanded = state.get('last_command') or {}
        hits = dict(state.get('mark_hits') or {})
        if (not current['shared_mark_ready'] or not turn_key
                or commanded.get('turn') != turn_key
                or not 0 <= len(target) <= 160 or not target
                or target != str(profile.mark.get('target', '')).strip()):
            raise ValueError('Marca Compartilhada exige presa marcada e Retalhar deste Comando.')
        if hits.get(turn_key, 0) >= commanded.get('rend_attacks', 0):
            raise ValueError('Todos os acertos de Retalhar deste Comando já foram registrados.')
        hits[turn_key] = hits.get(turn_key, 0) + 1
        state['mark_hits'] = hits
        state['last_mark_hit'] = dict(turn=turn_key, target=target,
                                      hit=hits[turn_key],
                                      damage='1' + current['shared_mark_damage'])
        state['last_event'] = 'mark_hit'
    elif action == 'supreme':
        if not state.get('active') or not current['supreme_eligible'] or not current['block']:
            raise ValueError('Forma Primordial Suprema indisponível para este espírito.')
        if state.get('supreme'):
            raise ValueError('Forma Primordial Suprema já está ativa.')
        prepared = preparation(profile)
        success, _ = spend_resource(person, contract(profile, prepared), 4)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para Forma Primordial Suprema.')
        state.update(supreme=True, supreme_remaining_seconds=3600, damage=0,
                     last_event='supreme', cost=4)
    elif action == 'elapsed':
        if not state.get('active') or not state.get('supreme'):
            raise ValueError('Não há Forma Primordial Suprema ativa.')
        if not 1 <= seconds <= 86400:
            raise ValueError('Informe de 1 a 86400 segundos de tempo de jogo.')
        state['supreme_remaining_seconds'] = max(0,
            state['supreme_remaining_seconds'] - seconds)
        if not state['supreme_remaining_seconds']:
            normal_max = (stat_block(state['circle'], state['battle_form'])['hp_max']
                          + current['hp_bonus'])
            state['damage'] = max(0, normal_max - current['block']['hp_current'])
            state['supreme'] = False
        state['last_event'] = 'elapsed'
    elif action in ('dismiss', 'fell'):
        if not state.get('active'):
            raise ValueError('Não há Companheiro Primordial ativo.')
        state['active'] = False
        state['supreme'] = False
        state['last_event'] = action
    else:
        raise ValueError('Evento de Companheiro Primordial inválido.')
    profile.companion = state
    profile.version += 1
    profile.save(update_fields=['companion', 'version'])
    response = dict(state, version=profile.version)
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
                                     fingerprint=fingerprint, resposta=response, status_http=200)
    return response


def grant_long_rest(person):
    """Called inside the existing atomic rest; never auto-summons or changes form."""
    for profile in TbPersonagemCacador.objects.select_for_update().select_related(
            'ruleset', 'personagem_classe').filter(personagem_classe__id_personagem=person):
        if _eligible(profile) is None:
            continue
        state = dict(profile.companion or {})
        if not state.get('free_ready', True):
            state['free_ready'] = True
            profile.companion = state
            profile.version += 1
            profile.save(update_fields=['companion', 'version'])
