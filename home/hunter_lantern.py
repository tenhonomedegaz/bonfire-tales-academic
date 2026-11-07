"""Declared Exorcist lantern, ceremony and consecrated-vial actions."""
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .hunter_preparation import preparation
from .hunter_resources import contract
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemCacador
from .resource_engine import spend_resource
from .epic_healing_bonus import healing_bonus, mark_healing_bonuses


ORDER = 'ordem-dos-exorcistas'
FORMS = (
    'Lanterna de ferro', 'Turíbulo de bronze', 'Crânio polido',
    'Relicário de prata', 'Vela votiva', 'Fogo-fátuo em frasco',
)


def _range(value, limit, name):
    try:
        distance = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'Informe a distância {name} em metros.') from exc
    if not distance.is_finite() or not 0 <= distance <= limit:
        raise ValueError(f'A distância {name} deve estar entre 0 e {limit} metros.')
    return distance


def _turn_targets(raw, dice_count):
    """One declared target per line: name | metres | falhou/sucesso | d8 rolls."""
    lines = [line.strip() for line in str(raw).splitlines() if line.strip()]
    if not lines or len(raw) > 5000:
        raise ValueError('Declare os Mortos-Vivos afetados, um por linha.')
    result, seen = [], set()
    for line in lines:
        pieces = [part.strip() for part in line.split('|')]
        if len(pieces) != 4 or not pieces[0] or len(pieces[0]) > 160:
            raise ValueError('Use nome | distância | falhou ou sucesso | rolagens d8.')
        name, distance, outcome, rolls_text = pieces
        if name.casefold() in seen:
            raise ValueError('Cada Morto-Vivo deve aparecer uma vez na ação.')
        seen.add(name.casefold())
        _range(distance, 9, 'do Morto-Vivo')
        if outcome not in ('falhou', 'sucesso'):
            raise ValueError('Declare falhou ou sucesso na salvaguarda de Sabedoria.')
        try:
            rolls = [int(value.strip()) for value in rolls_text.split(',') if value.strip()]
        except ValueError as exc:
            raise ValueError('Informe cada rolagem d8 separada por vírgula.') from exc
        if len(rolls) != dice_count or any(not 1 <= value <= 8 for value in rolls):
            raise ValueError(f'Declare {dice_count} rolagens d8 válidas por alvo.')
        damage = sum(rolls)
        result.append({'target': name, 'distance_m': distance, 'save_failed': outcome == 'falhou',
                       'rolls': rolls, 'radiant_damage': damage if outcome == 'falhou' else damage // 2,
                       'frightened_and_incapacitated_seconds': 60 if outcome == 'falhou' else 0})
    return result


def panel(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['order'] != ORDER or prepared['level'] < 3:
        return None
    state = (profile.exorcist or {}).get('lantern') or {}
    vial_max = prepared['proficiency'] if prepared['level'] >= 10 else 0
    modifier = 0
    if prepared['level'] >= 10:
        from .character_engine import derive
        sheet = derive(profile.personagem_classe.id_personagem, ruleset=profile.ruleset)
        modifier = sheet['atributos'][{'int': 'INT', 'wis': 'SAB'}[profile.ability]]['mod']
    return dict(state, version=profile.version, level=prepared['level'],
                forms=FORMS, held=state.get('held', True),
                radius_m=state.get('radius_m', '0'),
                vials=state.get('vials', vial_max), vial_max=vial_max,
                turn_ready=state.get('turn_ready', True), turn_dice=max(0, modifier),
                speak_remaining=state.get('speak_remaining', max(1, modifier))
                    if prepared['level'] >= 14 else 0,
                speak_max=max(1, modifier) if prepared['level'] >= 14 else 0,
                revealing_light=prepared['level'] >= 14 and state.get('held', True)
                    and Decimal(str(state.get('radius_m', '0'))) > 0,
                sanctuary_eligible=prepared['level'] >= 18 and any(
                    row['id'] == 'santuario-do-veu' for row in prepared['exclusive']),
                sanctuary_site=state.get('sanctuary_site', ''),
                sanctuary_spell=state.get('sanctuary_spell', ''),
                hunter_die=12 if prepared['level'] >= 17 else 10 if prepared['level'] >= 11
                           else 8 if prepared['level'] >= 5 else 6)


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version, action,
            confirmed, form='', radius_m='', target='', distance_m='',
            undead=False, total_cover=False, corpse_id='', corpse_large_or_less=False,
            last_actions='', rest_event='', seconds=0, possessed=False,
            charisma_save_failed=False, mode='', roll_1=0, roll_2=0,
            target_undead=False, target_possessor=False, turn_targets='',
            ritual_spell='', ritual_site='', bind_site=False):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    operation_id = uuid.UUID(str(operation_id))
    version = int(expected_version)
    target, corpse_id = str(target).strip(), str(corpse_id).strip()
    fingerprint_data = [
        'hunter-lantern', owner_id, version, action, bool(confirmed), form,
        str(radius_m), target, str(distance_m), bool(undead), bool(total_cover),
        corpse_id, bool(corpse_large_or_less), last_actions, rest_event,
        str(seconds), bool(possessed), bool(charisma_save_failed), mode,
        str(roll_1), str(roll_2), bool(target_undead), bool(target_possessor),
        str(turn_targets)]
    if action in ('sanctuary_ritual', 'sanctuary_recall'):
        fingerprint_data.extend([ritual_spell, ritual_site, bool(bind_site)])
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data,
        ensure_ascii=False).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person,
                                                operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Operação já usada com outros dados.')
        return receipt.resposta
    current = panel(profile)
    if current is None or current['version'] != version:
        raise ValueError('A Ordem, revisão ou ficha mudou. Recarregue a preparação.')
    if not confirmed:
        raise ValueError('Confirme as condições declaradas na mesa.')
    root = dict(profile.exorcist or {})
    state = dict(root.get('lantern') or {})
    held = state.get('held', True)
    if action == 'configure':
        if form not in FORMS or not held:
            raise ValueError('Escolha uma forma válida para a Lanterna do Véu presente.')
        state['form'] = form
    elif action == 'light':
        if not held:
            raise ValueError('A Lanterna do Véu foi perdida; realize a cerimônia de substituição.')
        if str(radius_m) == '0':
            state['radius_m'] = '0'
        else:
            radius = _range(radius_m, 6, 'da luz intensa')
            if radius < Decimal('1.5'):
                raise ValueError('A luz intensa deve alcançar de 1,5 a 6 metros ou estar apagada.')
            state['radius_m'] = str(radius)
    elif action == 'detect':
        if not held:
            raise ValueError('Segure a Lanterna do Véu para procurar mortos-vivos.')
        _range(distance_m, 18, 'da busca')
        state['last_detection'] = bool(undead and not total_cover)
    elif action == 'corpse':
        if (not held or not corpse_id or len(corpse_id) > 160
                or not corpse_large_or_less or undead or not last_actions
                or len(last_actions) > 1000):
            raise ValueError('Identifique cadáver Grande ou menor, não morto-vivo, e os últimos seis segundos.')
        seen = list(state.get('seen_corpses', []))
        if corpse_id.casefold() in seen:
            raise ValueError('Este cadáver já foi revelado pela Lanterna do Véu.')
        seen.append(corpse_id.casefold())
        state.update(seen_corpses=seen, last_replay={'corpse': corpse_id,
                     'actions': last_actions})
    elif action == 'lost':
        if not held:
            raise ValueError('A lanterna já está perdida.')
        state.update(held=False, radius_m='0')
    elif action == 'replace':
        if (held or rest_event not in ('short_rest', 'long_rest')
                or int(seconds) < 3600 or (form and form not in FORMS)):
            raise ValueError('Substituição exige lanterna perdida e uma hora em Descanso Curto ou Longo.')
        state.update(held=True, form=form or state.get('form', ''), radius_m='0',
                     generation=state.get('generation', 1) + 1)
        # The old lantern, including its site bond, is destroyed by replacement.
        state.pop('sanctuary_site', None)
        state.pop('sanctuary_spell', None)
    elif action == 'ceremony':
        if current['level'] < 10:
            raise ValueError('Rito de Exorcismo exige nível 10.')
        if target:
            if len(target) > 160 or not possessed:
                raise ValueError('O alvo do exorcismo deve estar possuído.')
            _range(distance_m, 9, 'do alvo possuído')
        elif possessed or charisma_save_failed:
            raise ValueError('Identifique o alvo possuído para o exorcismo.')
        state['vials'] = min(current['vial_max'], current['vials'] + 1)
        state['last_ceremony'] = {'target': target,
                                  'expelled': bool(target and charisma_save_failed),
                                  'vial_count': state['vials']}
    elif action == 'vial':
        if current['level'] < 10 or current['vials'] < 1:
            raise ValueError('É necessário um Frasco Consagrado da Ordem disponível.')
        if mode not in ('drink', 'ally', 'throw') or not target or len(target) > 160:
            raise ValueError('Escolha beber, ungir aliado ou arremessar e identifique o alvo.')
        _range(distance_m, 0 if mode == 'drink' else Decimal('1.5') if mode == 'ally' else 9,
               'do Frasco Consagrado')
        if mode == 'drink' and target != 'self':
            raise ValueError('Beber o frasco só pode afetar o próprio Caçador.')
        try:
            first, second = int(roll_1), int(roll_2)
        except (ValueError, TypeError) as exc:
            raise ValueError('Informe as rolagens do Dado de Caçador.') from exc
        if not 1 <= first <= current['hunter_die'] or (mode != 'throw' and
                not 1 <= second <= current['hunter_die']):
            raise ValueError('Rolagem inválida para o Dado de Caçador.')
        amount = first if mode == 'throw' else first + second + current['level']
        if mode == 'throw' and (target_undead or target_possessor):
            amount *= 2
        if mode == 'drink':
            from .character_engine import derive
            before = max(0, person.pv_atual)
            maximum = max(person.pv_maximo, derive(person, ruleset=profile.ruleset)['pv']['maximo_calculado'])
            bonus, pending = healing_bonus(person, hp=before, maximum_hp=maximum, ruleset=profile.ruleset)
            person.pv_atual = max(before, min(maximum, before + amount + bonus))
            person.save(update_fields=['pv_atual'])
            if person.pv_atual > before:
                mark_healing_bonuses(person, pending)
        state['vials'] = current['vials'] - 1
        state['last_vial'] = {'mode': mode, 'target': target, 'amount': amount,
            'remove_exhaustion_level': mode != 'throw',
            'blocks_target_healing_until_next_turn': mode == 'throw' and
                (target_undead or target_possessor)}
    elif action == 'turn_undead':
        if current['level'] < 10 or not held or not current['turn_ready']:
            raise ValueError('Afastar Mortos-Vivos exige nível 10, lanterna presente e uso disponível.')
        state['last_turn'] = _turn_targets(turn_targets, current['turn_dice'])
        state['turn_ready'] = False
    elif action == 'restore_turn':
        if current['level'] < 10 or current['turn_ready']:
            raise ValueError('Afastar Mortos-Vivos não tem uso gasto para recuperar.')
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 3)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para recuperar Afastar Mortos-Vivos.')
        state['turn_ready'] = True
    elif action == 'speak_dead':
        if current['level'] < 14 or not held or not current['speak_remaining']:
            raise ValueError('Falar com Mortos exige nível 14, lanterna presente e uso disponível.')
        if not target or len(target) > 160:
            raise ValueError('Identifique o cadáver alvo de Falar com Mortos.')
        state['speak_remaining'] = current['speak_remaining'] - 1
        state['last_spoken_corpse'] = target
    elif action == 'sanctuary_ritual':
        if not current['sanctuary_eligible'] or not held:
            raise ValueError('Santuário do Véu exige nível 18, Segredo exclusivo e lanterna presente.')
        ritual_site = str(ritual_site).strip()
        if (ritual_spell not in ('hallow', 'forbiddance') or not ritual_site
                or len(ritual_site) > 160):
            raise ValueError('Escolha Consagração ou Interdição e identifique o local do ritual.')
        if current['vials'] < 1:
            raise ValueError('O ritual exige um Frasco Consagrado disponível.')
        prepared = preparation(profile)
        success, _ = spend_resource(person, contract(profile, prepared), 4)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para Santuário do Véu.')
        state['vials'] = current['vials'] - 1
        state['last_sanctuary_ritual'] = {'site': ritual_site, 'spell': ritual_spell,
                                         'vial_used': True, 'secret_points_spent': 4,
                                         'bound': bool(bind_site)}
        if bind_site:
            state['sanctuary_site'] = ritual_site
            state['sanctuary_spell'] = ritual_spell
    elif action == 'sanctuary_recall':
        if not current['sanctuary_eligible'] or not current['sanctuary_site']:
            raise ValueError('Palavra de Retorno exige local consagrado e vinculado à lanterna.')
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 4)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para Palavra de Retorno.')
        state['last_recall'] = {'site': current['sanctuary_site'],
                                'spell': 'word-of-recall', 'secret_points_spent': 4}
    else:
        raise ValueError('Evento da Lanterna do Véu inválido.')
    state['last_event'] = action
    root['lantern'] = state
    profile.exorcist = root
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
        current = panel(profile)
        if current is None:
            continue
        root = dict(profile.exorcist or {})
        state = dict(root.get('lantern') or {})
        changed = False
        if current['level'] >= 10 and not current['turn_ready']:
            state['turn_ready'] = True
            changed = True
        if (event == 'long_rest' and current['level'] >= 14
                and current['speak_remaining'] != current['speak_max']):
            state['speak_remaining'] = current['speak_max']
            changed = True
        if changed:
            root['lantern'] = state
            profile.exorcist = root
            profile.version += 1
            profile.save(update_fields=['exorcist', 'version'])
