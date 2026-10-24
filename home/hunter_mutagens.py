"""Pinned Mutant formula preparation and declared activation lifecycle."""
import hashlib
import json
import re
import uuid

from django.db import transaction
from .content_versions import resolve_content
from .hunter_preparation import preparation
from .hunter_resources import contract
from .models import TbPersonagem, TbPersonagemCacador, TbOperacaoRecurso
from .resource_engine import spend_resource
from .versioned_classes import EVALUATOR, VOCABULARY

ORDER = 'ordem-dos-mutantes'
DAMAGE_TYPES = ('acido', 'concussivo', 'cortante', 'perfurante', 'frio', 'fogo',
                'energia', 'eletrico', 'necrotico', 'veneno', 'psiquico', 'radiante', 'trovejante')


def linked_effects(person, ruleset):
    if ruleset is None or not getattr(person, 'pk', None):
        return None
    profile = TbPersonagemCacador.objects.select_related('ruleset', 'personagem_classe').filter(
        personagem_classe__id_personagem=person).first()
    if profile is None or profile.ruleset_id != ruleset.pk:
        return None
    info = panel(profile)
    if info is None:
        return None
    allowed = {row['id'] for row in info['options']}
    return info, (set() if info['cooldown_seconds'] else set(info['active']) & allowed)


def side_effect_active(info, formula):
    return not info['chimera_seconds'] and not (
        info.get('suppressed', {}).get(formula, 0) > 0
        or info.get('stigma_transfers', {}).get(formula, {}).get('active', False))


def concentration_blocked(person):
    profile = TbPersonagemCacador.objects.select_related('ruleset', 'personagem_classe').filter(
        personagem_classe__id_personagem=person).first()
    if profile is None:
        return False
    info = panel(profile)
    return bool(info and not info['cooldown_seconds'] and 'guepardo-das-planicies' in info['active']
                and side_effect_active(info, 'guepardo-das-planicies'))


def end_blocked_concentration(person, profile):
    if not concentration_blocked(person):
        return
    from .resource_engine import end_state
    from .versioned_spells import spell_catalog
    catalog = spell_catalog(profile.ruleset)
    for effect in person.estados.filter(ativo=True, origem__startswith='magia:'):
        payload = effect.payload_json or {}
        spell = catalog.get(payload.get('spell_id'))
        if payload.get('concentration') or (spell and spell.concentracao):
            end_state(person, effect.chave)


def apply_attributes(person, ruleset, attributes):
    binding = linked_effects(person, ruleset)
    if binding is None:
        return
    info, active = binding
    boost = 5 if info['level'] >= 18 else 4 if info['level'] >= 11 else 3
    penalties = {}
    for formula, raised, reduced in (
            ('kraken-onisciente', 'INT', 'SAB'), ('esfinge-visionaria', 'SAB', 'INT'),
            ('raptor-sombrio', 'DES', 'FOR'), ('gorgona-prateada', 'FOR', 'DES')):
        if formula not in active:
            continue
        attribute = attributes[raised]
        increase = max(0, min(22, attribute['valor'] + boost) - attribute['valor'])
        attribute['valor'] += increase
        attribute['bonus'] += increase
        attribute['breakdown'].append({'origem': formula, 'valor': increase})
        if side_effect_active(info, formula):
            penalties[reduced] = penalties.get(reduced, 0) - 3
    for key, delta in penalties.items():
        attributes[key]['valor'] += delta
        attributes[key]['bonus'] += delta
        attributes[key]['breakdown'].append({'origem': 'Efeito Colateral mutagênico', 'valor': delta})


def apply_checks(person, ruleset, sheet):
    """Offer optional modifiers without changing learned skills or their expertise."""
    from django.utils.text import slugify
    binding = linked_effects(person, ruleset)
    if binding is None:
        return
    info, active = binding
    chimera = bool(info['chimera_seconds'])
    if 'manticora-raivosa' in active:
        sheet['mutagen_bonus_attack'] = True
        if side_effect_active(info, 'manticora-raivosa'):
            for attr in ('INT', 'SAB', 'CAR'):
                sheet['saves'][attr].setdefault('mutagen_conditions', []).append(
                    'Desvantagem — Manticora Raivosa')
    if 'quimera-do-caos' in active:
        sheet['mutagen_weapon_critical'] = 19
        for attack in sheet['ataques']['perfis']:
            if attack.get('escopo', '').startswith('weapon-') or attack.get('escopo') == 'off_hand':
                attack['critical_min'] = min(19, attack.get('critical_min', 20))
        if side_effect_active(info, 'quimera-do-caos'):
            sheet['mutagen_mental_save_disadvantage'] = True
    wolf = 'lobo-alfa' in active
    chameleon = 'camaleao-espectral' in active
    if chameleon:
        sheet['mutagen_charisma_modifiers'] = [
            {'atributo': attr, 'bonus': sheet['atributos'][attr]['mod']}
            for attr in ('INT', 'SAB')]
        if side_effect_active(info, 'camaleao-espectral'):
            sheet['mutagen_initiative_disadvantage'] = True
    for skill in sheet['pericias']:
        slug = slugify(skill['nome'])
        if wolf and slug == 'percepcao' and skill['atributo'] == 'SAB':
            skill.setdefault('mutagen_conditions', []).append(
                'Vantagem com audição, olfato ou visão — Lobo Alfa')
        if wolf and side_effect_active(info, 'lobo-alfa') and skill['atributo'] == 'CAR' and slug in (
                'atuacao', 'enganacao', 'intimidacao', 'persuasao'):
            skill.setdefault('mutagen_conditions', []).append(
                'Desvantagem — Lobo Alfa (também ao usar outro modificador)')
        if chameleon and skill['atributo'] == 'CAR':
            # The formula replaces the modifier of a Charisma check, not its
            # identity. Keep proficiency, expertise and conditional check bonuses.
            skill['mutagen_alternatives'] = [
                {'atributo': attr, 'bonus': skill['bonus']
                 - sheet['atributos']['CAR']['mod'] + sheet['atributos'][attr]['mod']}
                for attr in ('INT', 'SAB')]


def apply_defenses(person, ruleset, sheet):
    binding = linked_effects(person, ruleset)
    if binding is None:
        return
    info, active = binding
    if info['level'] >= 6:
        if 'veneno' not in sheet.setdefault('imunidades', []):
            sheet['imunidades'].append('veneno')
    resistances, vulnerabilities = [], []
    if 'vermeluz-das-cavernas' in active:
        from .versioned_conditions import condition_names
        names = condition_names(ruleset)
        conditions = sheet.setdefault('imunidades_condicao', [])
        for fallback, english, label in (('agarrado', 'grappled', 'Agarrado'),
                                         ('restringido', 'restrained', 'Restringido')):
            slug = next((key for key, name in names.items()
                         if key in (fallback, english) or name.casefold() == label.casefold()), fallback)
            if not any(row['slug'] == slug for row in conditions):
                conditions.append({'slug': slug, 'nome': names.get(slug, label)})
            rendered = '%s (condição)' % names.get(slug, label)
            if rendered not in sheet.setdefault('imunidades', []):
                sheet['imunidades'].append(rendered)
        if side_effect_active(info, 'vermeluz-das-cavernas'):
            sheet['mutagen_cannot_grapple'] = True
            sheet.setdefault('desvantagens_impostas', []).append('Testes de Força — Vermeluz das Cavernas')
    if 'morcego-abissal' in active:
        senses = sheet.setdefault('sentidos', [])
        darkvision = [value for value in senses if value.startswith('darkvision')]
        ranges = [int(match[1]) for value in darkvision
                  for match in [re.search(r'(\d+)\s*ft', value)] if match]
        sheet['sentidos'] = [value for value in senses if value not in darkvision]
        sheet['sentidos'].append('darkvision %dft' % (max(ranges, default=0) + 60))
        if side_effect_active(info, 'morcego-abissal'):
            sheet['mutagen_bright_light_disadvantage'] = True
            sheet.setdefault('desvantagens_impostas', []).append(
                'Sob luz plena: testes de habilidade e ataques — Morcego Abissal')
    if 'carapaca-de-basilisco' in active:
        resistances.extend(('cortante', 'perfurante', 'concussivo'))
    for formula, resistance, vulnerability in (
            ('salamandra-ignea', 'fogo', 'frio'),
            ('yeti-boreal', 'frio', 'fogo')):
        if formula in active:
            resistances.append(resistance)
            if side_effect_active(info, formula):
                vulnerabilities.append(vulnerability)
    if info['chimera_seconds']:
        resistances.extend(value for value in info.get('resistances', []) if value in DAMAGE_TYPES)
    # Preserve other sources and both opposing effects; neither cancels the other.
    for key, additions in (('resistencias', resistances), ('vulnerabilidades', vulnerabilities)):
        if additions:
            sheet[key] = list(dict.fromkeys(sheet.get(key, []) + additions))


def apply_movement(person, ruleset, sheet):
    binding = linked_effects(person, ruleset)
    if binding is None:
        return
    info, active = binding
    harpy = 'harpia-das-montanhas' in active and (info['chimera_seconds'] or info['harpy_seconds'])
    speed_delta = 0
    if 'guepardo-das-planicies' in active:
        speed_delta += 15 if info['level'] >= 15 else 10
        if side_effect_active(info, 'guepardo-das-planicies'):
            sheet['mutagen_cannot_concentrate'] = True
            sheet.setdefault('desvantagens_impostas', []).append('Testes de Inteligência — Guepardo das Planícies')
    if 'carapaca-de-basilisco' in active and side_effect_active(info, 'carapaca-de-basilisco'):
        sheet['mutagen_cannot_dodge'] = True
        speed_delta -= 10
    if speed_delta:
        speed_text = sheet.get('velocidade') or ''
        feet = re.search(r'(\d+(?:[.,]\d+)?)\s*ft', speed_text)
        metres = re.search(r'(\d+(?:[.,]\d+)?)\s*m\b', speed_text)
        if feet or metres:
            walking = float((feet or metres)[1].replace(',', '.')) / (1 if feet else 0.3)
            reduced = max(0, walking + speed_delta)
            sheet['velocidade'] = '%g m / %g ft' % (round(reduced * 0.3, 1), reduced)
            sheet['velocidade_bonus'] = sheet.get('velocidade_bonus', 0) + reduced - walking
        else:
            sheet.setdefault('avisos', []).append('Mutagênicos: ajuste o deslocamento em %+g pés; valor-base não numérico.' % speed_delta)
        for mode, speed in list(sheet.get('movimento_modos', {}).items()):
            numeric = re.fullmatch(r'(\d+)\s*ft', speed)
            if numeric:
                sheet['movimento_modos'][mode] = '%dft' % max(0, int(numeric[1]) + speed_delta)
    granted = []
    if harpy:
        granted.append('fly')
        if side_effect_active(info, 'harpia-das-montanhas'):
            sheet.setdefault('desvantagens_impostas', []).append('Ataques com armas — Harpia das Montanhas')
            sheet['mutagen_weapon_disadvantage'] = True
    if info['chimera_seconds']:
        mode = {'voo': 'fly', 'natacao': 'swim', 'escalada': 'climb'}.get(info.get('movement'))
        if mode:
            granted.append(mode)
    if not granted:
        return
    modes = sheet.setdefault('movimento_modos', {})
    walking = re.search(r'(\d+)\s*ft', sheet.get('velocidade') or '')
    for mode in granted:
        existing = modes.get(mode)
        speed = re.fullmatch(r'(\d+)\s*ft', existing or '')
        if existing is None or existing == 'walk' or (speed and walking and int(speed[1]) <= int(walking[1])):
            modes[mode] = 'walk'


def panel(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['order'] != ORDER or prepared['level'] < 3:
        return None
    data = resolve_content(profile.ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    state = dict(profile.mutagens or {})
    level = prepared['level']
    known_max = 4 + sum(level >= milestone for milestone in (7, 11, 15, 18))
    options = [row for row in data.get('mutagen_formulas', []) if row['level'] <= level]
    return dict(state, version=profile.version, level=level, options=options,
                known=state.get('known', []), known_max=known_max,
                limit=3 if level >= 15 else 2 if level >= 7 else 1,
                prepared=state.get('prepared', []), active=state.get('active', []),
                preparation_open=state.get('preparation_open', True),
                chimera_seconds=state.get('chimera_seconds', 0),
                harpy_seconds=state.get('harpy_seconds', 0),
                lizard_seconds=state.get('lizard_seconds', 0),
                lizard_penalty=not state.get('chimera_seconds', 0) and not state.get('suppressed', {}).get('lagartixa-cicatrizante', 0),
                harpy_penalty=not state.get('chimera_seconds', 0) and not state.get('suppressed', {}).get('harpia-das-montanhas', 0),
                cooldown_seconds=state.get('cooldown_seconds', 0),
                chimera_eligible=any(row['id'] == 'forma-quimerica' for row in prepared['exclusive']),
                damage_types=DAMAGE_TYPES)


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version, action,
            confirmed, selected=(), formula='', seconds=0, movement='', resistances=(),
            turn_key='', healing_amount=0, replaced_formula='', target='', damage_type='',
            critical=False, favored=False, attack_kind='', save_total=0):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    op = uuid.UUID(str(operation_id))
    selected, resistances = list(selected), list(resistances)
    fingerprint_data = ['hunter-mutagens', owner_id, expected_version,
        action, bool(confirmed), selected, formula, str(seconds), movement, resistances]
    if action in ('regenerate', 'external_heal'):
        fingerprint_data.extend([str(turn_key), str(healing_amount)])
    if action == 'transfuse':
        fingerprint_data.append(replaced_formula)
    if action == 'transfusion_hit':
        fingerprint_data.extend([str(turn_key), target, damage_type])
    if action in ('stigma_transfer', 'stigma_end', 'stigma_shape'):
        fingerprint_data.extend([str(turn_key), target, bool(critical), bool(favored), attack_kind, str(save_total)])
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data).encode()).hexdigest()
    receipt = TbOperacaoRecurso.objects.filter(id_personagem=person, operation_id=op).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Operação já usada com outros dados.')
        return receipt.resposta
    current = panel(profile)
    if current is None or int(expected_version) != profile.version or not confirmed:
        raise ValueError('Confirme as condições e recarregue a ficha vinculada dos Mutantes.')
    state = dict(profile.mutagens or {})
    if action == 'learn':
        old = set(current['known'])
        if (len(selected) != current['known_max'] or len(set(selected)) != len(selected)
                or not set(selected) <= {row['id'] for row in current['options']}
                or len(old) >= current['known_max'] or len(old - set(selected)) > 1
                or not set(current['active'] + current['prepared']) <= set(selected)):
            raise ValueError('Escolha as fórmulas conhecidas; só pode trocar uma ao aprender novas.')
        state['known'] = selected
    elif action == 'prepare':
        if (not current['preparation_open'] or current['cooldown_seconds']
                or len(selected) > current['limit'] or len(selected) != len(set(selected))
                or not set(selected) <= set(current['known'])):
            raise ValueError('Prepare fórmulas conhecidas após descanso, dentro do limite mutagênico.')
        state.update(prepared=selected, preparation_open=False)
    elif action == 'suppress':
        if (current['level'] < 6 or current['cooldown_seconds']
                or formula not in current['active'] or state.get('suppression_used', False)):
            raise ValueError('Supressão exige nível 6, mutagênico ativo e uso disponível.')
        suppressed = dict(state.get('suppressed', {}))
        suppressed[formula] = 60
        state.update(suppressed=suppressed, suppression_used=True)
    elif action == 'recover_suppression':
        if current['level'] < 6 or not state.get('suppression_used', False):
            raise ValueError('Não há uso de Supressão para recuperar.')
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 2)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes.')
        state['suppression_used'] = False
    elif action in ('consume', 'transfuse'):
        active = list(current['active'])
        if action == 'transfuse':
            from .character_engine import derive
            attrs = derive(person, ruleset=profile.ruleset)['atributos']
            limit = max(1, attrs['INT']['mod'], attrs['SAB']['mod'])
            used = int(state.get('transfusion_used', 0))
            if current['level'] < 14 or replaced_formula not in active or used >= limit:
                raise ValueError('Transfusão exige nível 14, efeito ativo e uso disponível até o Descanso Longo.')
            active.remove(replaced_formula)
            state['transfusion_used'] = used + 1
            if replaced_formula == 'harpia-das-montanhas':
                state['harpy_seconds'] = 0
            if replaced_formula == 'lagartixa-cicatrizante':
                state.update(lizard_seconds=0, regenerated_turns=[])
        if (current['cooldown_seconds'] or current['chimera_seconds']
                or formula not in current['prepared'] or formula in current['active']
                or len(active) >= current['limit']):
            raise ValueError('Mutagênico indisponível ou limite de efeitos ativos atingido.')
        state['prepared'] = [value for value in current['prepared'] if value != formula]
        state['active'] = active + [formula]
        if action == 'transfuse':
            state['suppressed'] = {key: value for key, value in state.get('suppressed', {}).items()
                                   if key != replaced_formula}
        if formula == 'harpia-das-montanhas':
            state['harpy_seconds'] = 3600
        if formula == 'lagartixa-cicatrizante':
            state.update(lizard_seconds=3600, regenerated_turns=[])
    elif action in ('stigma_transfer', 'stigma_end', 'stigma_shape'):
        mark = profile.mark or {}
        marked = bool(mark.get('active') and mark.get('remaining_seconds', 0)
                      and target and target == mark.get('target'))
        if current['level'] < 10:
            raise ValueError('Estigma Hermético exige nível 10.')
        if action == 'stigma_shape':
            if not marked:
                raise ValueError('A mudança de forma exige uma Presa Marcada vigente.')
            from .character_engine import derive
            from .hunter_combat import evaluate
            attrs = derive(person, ruleset=profile.ruleset)['atributos']
            dc = evaluate(preparation(profile, selected=[], allow_pending_order=True),
                          intelligence=attrs['INT']['valor'], wisdom=attrs['SAB']['valor'])['spell_dc']
            total = int(save_total)
            if not -100 <= total <= 1000:
                raise ValueError('Informe o total da salvaguarda de Sabedoria.')
            state['last_stigma_shape'] = dict(target=target, dc=dc, total=total, allowed=total >= dc)
        else:
            transfers = {key: dict(value) for key, value in state.get('stigma_transfers', {}).items()}
            if action == 'stigma_transfer':
                turn_key = str(turn_key).strip()
                if (current['cooldown_seconds'] or formula not in current['active']
                        or formula in transfers or not critical or not (marked or favored)
                        or not target or len(target) > 160 or not turn_key or len(turn_key) > 120
                        or attack_kind not in ('weapon', 'unarmed')):
                    raise ValueError('Declare crítico com arma ou Golpe Desarmado, presa marcada ou favorita e efeito ativo ainda não transferido.')
                transfers[formula] = dict(target=target, active=True, next_turn=turn_key)
            else:
                transfer = transfers.get(formula)
                if not transfer or not transfer['active'] or str(turn_key).strip() != transfer['next_turn']:
                    raise ValueError('Declare o fim do próximo turno registrado na transferência.')
                transfer['active'] = False
            state['stigma_transfers'] = transfers
    elif action == 'transfusion_hit':
        turn_key = str(turn_key).strip()
        turns = list(state.get('transfusion_turns', []))
        mark = profile.mark or {}
        active = set(current['active']) & {row['id'] for row in current['options']}
        if (current['level'] < 14 or current['cooldown_seconds'] or not active
                or not mark.get('active') or not mark.get('remaining_seconds', 0)
                or not target or target != mark.get('target')
                or not turn_key or len(turn_key) > 120 or turn_key in turns
                or damage_type not in ('concussivo', 'cortante', 'perfurante', 'necrotico', 'veneno')):
            raise ValueError('Declare um acerto na Presa Marcada, turno ainda não usado e tipo de dano válido, com mutagênicos ativos e nível 14.')
        state['transfusion_turns'] = turns + [turn_key]
        state['last_transfusion_hit'] = dict(target=target, turn=turn_key,
            dice='%dd4' % min(3, len(active)), damage_type=damage_type)
    elif action == 'purge':
        if not current['active']:
            raise ValueError('Não há mutagênicos ativos para purgar.')
        state['active'] = []
        state['suppressed'] = {}
        state['harpy_seconds'] = 0
        state['lizard_seconds'] = 0
        if current['chimera_seconds']:
            state.update(chimera_seconds=0, cooldown_seconds=3600)
    elif action == 'chimera':
        if (not current['chimera_eligible'] or current['cooldown_seconds']
                or current['chimera_seconds'] or not current['prepared']
                or movement not in ('escalada', 'natacao', 'voo')
                or len(set(resistances)) != 2 or len(resistances) != 2
                or not set(resistances) <= set(DAMAGE_TYPES)):
            raise ValueError('Forma Quimérica exige preparados, movimento e duas resistências distintas.')
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 4)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes.')
        state.update(chimera_seconds=60, movement=movement, resistances=resistances,
                     active=list(dict.fromkeys(current['active'] + current['prepared'])), prepared=[])
    elif action in ('regenerate', 'external_heal'):
        if ('lagartixa-cicatrizante' not in current['active'] or current['cooldown_seconds']):
            raise ValueError('Lagartixa-Cicatrizante não está ativa.')
        if action == 'regenerate':
            turn_key = str(turn_key).strip()
            turns = list(state.get('regenerated_turns', []))
            if (not (current['lizard_seconds'] or current['chimera_seconds'])
                    or person.pv_atual < 1 or not turn_key or len(turn_key) > 120
                    or turn_key in turns):
                raise ValueError('Declare um início de turno ainda não registrado, com ao menos 1 PV e duração disponível.')
            from .character_engine import derive
            amount = derive(person, ruleset=profile.ruleset)['bonus_proficiencia']
            state['regenerated_turns'] = turns + [turn_key]
        else:
            amount = int(healing_amount)
            if not 1 <= amount <= 100000:
                raise ValueError('Informe a cura recebida de outra criatura, entre 1 e 100000 PV.')
            if side_effect_active(current, 'lagartixa-cicatrizante'):
                amount //= 2
        from .character_engine import derive
        from .epic_healing_bonus import healing_bonus, mark_healing_bonuses
        before = person.pv_atual
        maximum = max(person.pv_maximo, derive(person, ruleset=profile.ruleset)['pv']['maximo_calculado'])
        bonus, pending = healing_bonus(person, hp=before, maximum_hp=maximum, ruleset=profile.ruleset)
        # Healing never reduces existing HP, even if a previously saved maximum is lower.
        person.pv_atual = max(before, min(maximum, max(0, before) + amount + bonus))
        person.save(update_fields=['pv_atual'])
        if person.pv_atual > before:
            mark_healing_bonuses(person, pending)
        state['last_healing'] = dict(source=action, amount=person.pv_atual - before,
                                     current=person.pv_atual, turn=turn_key if action == 'regenerate' else '')
    elif action == 'elapsed':
        seconds = int(seconds)
        if not 1 <= seconds <= 86400:
            raise ValueError('Declare de 1 a 86400 segundos de tempo de jogo.')
        state['suppressed'] = {key: value - seconds for key, value in state.get('suppressed', {}).items()
                               if value > seconds}
        if current['chimera_seconds']:
            remaining = max(0, current['chimera_seconds'] - seconds)
            state['chimera_seconds'] = remaining
            if not remaining:
                state.update(active=[], harpy_seconds=0, lizard_seconds=0, cooldown_seconds=max(0, 3600 - (seconds - current['chimera_seconds'])))
        else:
            state['cooldown_seconds'] = max(0, current['cooldown_seconds'] - seconds)
            state['lizard_seconds'] = max(0, current['lizard_seconds'] - seconds)
            if current['harpy_seconds']:
                state['harpy_seconds'] = max(0, current['harpy_seconds'] - seconds)
                if not state['harpy_seconds']:
                    state['active'] = [value for value in current['active'] if value != 'harpia-das-montanhas']
    else:
        raise ValueError('Evento mutagênico inválido.')
    profile.mutagens = state
    profile.version += 1
    profile.save(update_fields=['mutagens', 'version'])
    end_blocked_concentration(person, profile)
    result = dict(state, version=profile.version)
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=op,
        fingerprint=fingerprint, resposta=result, status_http=200)
    return result


def grant_rest(person, event):
    if event not in ('short_rest', 'long_rest'):
        return
    for profile in TbPersonagemCacador.objects.select_for_update().select_related(
            'ruleset', 'personagem_classe').filter(personagem_classe__id_personagem=person):
        current = panel(profile)
        if current is None:
            continue
        state = dict(profile.mutagens or {})
        # A completed rest lasts at least the one-hour recovery period.
        state.update(active=[], prepared=[], preparation_open=True,
                     suppressed={},
                     chimera_seconds=0, cooldown_seconds=0, harpy_seconds=0, lizard_seconds=0,
                     regenerated_turns=[])
        state['stigma_transfers'] = {key: dict(value, active=False)
                                    for key, value in state.get('stigma_transfers', {}).items()}
        if event == 'long_rest':
            state['transfusion_used'] = 0
            state['suppression_used'] = False
        if state != profile.mutagens:
            profile.mutagens = state
            profile.version += 1
            profile.save(update_fields=['mutagens', 'version'])
