"""Apply the base rework passives only when the sealed revision declares them."""
import re
from copy import copy
from django.db import transaction
from .content_versions import resolve_content
from .hunter_preparation import preparation
from .hunter_combat import evaluate
from .models import TbPersonagem, TbPersonagemCacador, TbPersonagemEscolha
from .versioned_classes import EVALUATOR, VOCABULARY


def contract(person, ruleset):
    if person is None or ruleset is None:
        return None
    profile = TbPersonagemCacador.objects.filter(
        personagem_classe__id_personagem=person).select_related('personagem_classe', 'ruleset').first()
    if profile is None:
        return None
    if profile.ruleset_id != ruleset.pk:
        raise ValueError('Hunter profile and derived ruleset differ.')
    data = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    spec = data.get('base_passives')
    if spec is None:
        return None
    if spec.get('version') != 1:
        raise ValueError('Unsupported Hunter passive contract.')
    return profile, spec


def filter_replaced_features(person, ruleset, features):
    binding = contract(person, ruleset)
    if binding is None:
        return features
    profile, spec = binding
    out = []
    for feature in features:
        if (feature[0] == 'classe'
                and getattr(feature[2], 'id_classe_id', None) == profile.personagem_classe.id_classe_id
                and getattr(feature[2], 'nome', '') in spec['replaces']):
            source = copy(feature[2])
            source.tags_json = []
            feature = (feature[0], feature[1], source, feature[3])
        out.append(feature)
    return out


@transaction.atomic
def choose_twilight_save(*, character_id, owner_id, ability, expected_version):
    """Fix the alternative save proficiency when Dexterity is already proficient."""
    if ability not in ('FOR', 'CON'):
        raise ValueError('Escolha Força ou Constituição.')
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'personagem_classe', 'ruleset').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de escolher a salvaguarda.')
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['order'] != 'ordem-do-crepusculo' or prepared['level'] < 6:
        raise ValueError('Reflexos das Sombras indisponível.')
    from .character_engine import derive
    sheet = derive(person, ruleset=profile.ruleset)
    if not sheet['saves']['DES']['proficiente']:
        raise ValueError('A proficiência concedida é Destreza; não há escolha alternativa.')
    choices = list(TbPersonagemEscolha.objects.filter(
        id_personagem=person, tipo='hunter_twilight_save'))
    if len(choices) > 1:
        raise ValueError('Há escolhas duplicadas de Reflexos das Sombras.')
    if choices:
        if choices[0].valor != ability:
            raise ValueError('A escolha de Reflexos das Sombras já foi registrada.')
        return profile
    TbPersonagemEscolha.objects.create(id_personagem=person,
        origem='Reflexos das Sombras', tipo='hunter_twilight_save', slot=0, valor=ability)
    profile.version += 1
    profile.save(update_fields=['version'])
    return profile


def apply(person, ruleset, state):
    binding = contract(person, ruleset)
    if binding is None:
        return
    profile, _ = binding
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    match = re.search(r'(\d+)\s*ft', state.get('velocidade') or '')
    # Unknown movement must stay unknown; do not invent a 30-foot racial speed.
    walk = int(match.group(1)) if match else 0
    effects = evaluate(prepared, intelligence=state['atributos']['INT']['valor'],
        wisdom=state['atributos']['SAB']['valor'], walking_speed=walk)
    if not match:
        effects['walking_speed'] = effects['climbing_speed'] = effects['swimming_speed'] = None
    state['cacador'] = effects
    state['ataques']['quantidade'] = max(state['ataques']['quantidade'], effects['attacks'])
    for sig in ('FOR', 'DES', 'CON'):
        state['saves'][sig]['bonus'] += effects['physical_save_bonus']
    if prepared['level'] >= 7:
        modes = state.setdefault('movimento_modos', {})
        for mode in ('climb', 'swim'):
            numeric = re.fullmatch(r'(\d+)ft', modes.get(mode, ''))
            if not numeric or (effects['walking_speed'] is not None and int(numeric[1]) <= effects['walking_speed']):
                modes[mode] = 'walk'
        if match:
            speed = effects['walking_speed']
            state['velocidade'] = '%g m / %d ft' % (round(speed * .3, 1), speed)
            state['velocidade_bonus'] = state.get('velocidade_bonus', 0) + 10
        else:
            state['avisos'].append('Caçador Implacável: +10 ft; informe o deslocamento base para calcular o total.')
    if effects['charmed_immune']:
        immunity = {'slug': 'enfeiticado', 'nome': 'Enfeitiçado'}
        if not any(c['slug'] in ('charmed', 'enfeiticado') for c in state['imunidades_condicao']):
            state['imunidades_condicao'].append(immunity)
        for label in ('Enfeitiçado (condição)', 'Possessão', 'Dominação'):
            if label not in state['imunidades']:
                state['imunidades'].append(label)
        advantage = 'Salvaguardas contra Amedrontado — Vontade Inabalável'
        if advantage not in state['vantagens']:
            state['vantagens'].append(advantage)
    if effects['blindsight']:
        existing = [s for s in state['sentidos'] if s.startswith('blindsight')]
        ranges = [int(m.group(1)) for s in existing for m in [re.search(r'(\d+)ft', s)] if m]
        state['sentidos'] = [s for s in state['sentidos'] if not s.startswith('blindsight')]
        state['sentidos'].append('blindsight %dft' % max([30] + ranges))
    if prepared['order'] == 'ordem-do-crepusculo' and prepared['level'] >= 3:
        # Caçador das Sombras adds 60ft to an existing darkvision range, or grants 60ft.
        # The ability to see through magical darkness is explicit; it does not alter
        # unrelated senses or grant blanket invisibility on the permanent sheet.
        darkvision = [s for s in state['sentidos'] if s.startswith('darkvision')]
        ranges = [int(m.group(1)) for s in darkvision
                  for m in [re.search(r'(\d+)ft', s)] if m]
        state['sentidos'] = [s for s in state['sentidos'] if not s.startswith('darkvision')]
        state['sentidos'].append('darkvision %dft' % ((max(ranges) if ranges else 0) + 60))
        bonus = max(1, state['atributos']['INT']['mod'], state['atributos']['SAB']['mod'])
        state['iniciativa'] += bonus
        state['crepusculo'] = {'initiative_bonus': bonus,
            'sees_magical_darkness': True, 'darkvision_bonus_ft': 60}
        if prepared['level'] >= 6:
            if not state['saves']['DES']['proficiente']:
                state['saves']['DES']['proficiente'] = True
                state['saves']['DES']['bonus'] += state['bonus_proficiencia']
                state['crepusculo']['save_proficiency'] = 'DES'
            else:
                choices = list(TbPersonagemEscolha.objects.filter(
                    id_personagem=person, tipo='hunter_twilight_save'))
                if len(choices) > 1:
                    raise ValueError('Há escolhas duplicadas de Reflexos das Sombras.')
                choice = choices[0].valor if choices else ''
                if choice and choice not in ('FOR', 'CON'):
                    raise ValueError('Escolha inválida de Reflexos das Sombras.')
                if choice:
                    if not state['saves'][choice]['proficiente']:
                        state['saves'][choice]['proficiente'] = True
                        state['saves'][choice]['bonus'] += state['bonus_proficiencia']
                    state['crepusculo']['save_proficiency'] = choice
                else:
                    state['crepusculo']['save_choice_pending'] = True
                    state['avisos'].append('Reflexos das Sombras: escolha Força ou Constituição.')
    data = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    swarm = data.get('swarm_passives')
    if swarm and prepared['order'] == swarm['order']:
        if swarm['version'] != 1:
            raise ValueError('Unsupported Swarm passive contract.')
        if prepared['level'] >= swarm['symbiosis_level']:
            modes = state.setdefault('movimento_modos', {})
            # Preserve a faster speed granted by another source.
            walking = effects['walking_speed']
            climbing = modes.get('climb', 'walk')
            climb_match = re.fullmatch(r'(\d+)ft', climbing)
            if not climb_match or (walking is not None and int(climb_match[1]) <= walking):
                climbing = 'walk'
            modes['climb'] = climbing
            state['enxame'] = dict(feather_fall=True, surprise_protection='while_conscious',
                surface_climbing='one_hand_free', hover=False,
                climbing_display=state['velocidade'] if climbing == 'walk' else climbing)
            for benefit in ('Não pode ser Surpreendido enquanto consciente — Sentidos Coletivos',
                            'Queda Suave permanente, sem Concentração — Queda Amortecida',
                            'Escala paredes e tetos com uma mão livre, sem teste — Escalada Orgânica'):
                if benefit not in state['vantagens']:
                    state['vantagens'].append(benefit)
            if prepared['level'] >= swarm['flight_level']:
                flight = modes.get('fly')
                flight_match = re.fullmatch(r'(\d+)ft', flight or '')
                climb_speed = walking if climbing == 'walk' else int(climbing[:-2])
                if not flight_match or (climb_speed is not None and int(flight_match[1]) <= climb_speed):
                    modes['fly'] = climbing
                state['enxame']['hover'] = True
                state['enxame']['flight_display'] = (state['velocidade']
                    if modes.get('fly') == 'walk' else modes.get('fly'))
                state['enxame']['athletics_die'] = '1' + prepared['progression']['hunter_die']
                state['vantagens'].append('+' + state['enxame']['athletics_die'] +
                    ' em Atletismo para Agarrar, Empurrar, evitar ou escapar de Agarrão — Força Multiplicada')
