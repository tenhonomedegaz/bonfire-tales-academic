"""Declared rune placements and teleports for a linked Primordial Traveler."""
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .hunter_preparation import preparation
from .hunter_spells import uses_tag_spell_grants
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemCacador
from .resource_engine import spend_resource


ORDER = 'ordem-dos-viajantes-primordiais'
FINAL_SPELLS = (
    'Arcane Gate', 'Word of Recall', 'Etherealness',
    "Mordenkainen's Magnificent Mansion", 'Teleport', 'Plane Shift',
)


def final_options(profile):
    if uses_tag_spell_grants(profile):
        return []
    from .versioned_spells import spell_catalog

    catalog = list(spell_catalog(profile.ruleset).values())
    options = []
    for english in FINAL_SPELLS:
        matches = [spell for spell in catalog
                   if (spell.nome_ingles or '').strip().casefold() == english.casefold()]
        if len(matches) != 1 or not matches[0].slug:
            raise ValueError('Magia de Caminho Final ausente ou ambígua na revisão: ' + english)
        spell = matches[0]
        options.append({'slug': spell.slug, 'name': spell.nome, 'level': spell.nivel})
    return options


def final_grants(profile):
    if uses_tag_spell_grants(profile):
        return []
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if (prepared['order'] != ORDER or prepared['level'] < 18
            or not any(row['id'] == 'caminho-final' for row in prepared['exclusive'])):
        return []
    selected = (profile.traveler or {}).get('final_choices', [])
    if not selected:
        return []
    options = {row['slug']: row for row in final_options(profile)}
    if any(slug not in options for slug in selected):
        raise ValueError('Escolha de Caminho Final incompatível com a revisão vinculada.')
    return [{'slug': slug, 'nivel': options[slug]['level'], 'fonte': 'Caminho Final'}
            for slug in selected]


def _uses(profile, kind, maximum):
    person = profile.personagem_classe.id_personagem
    key = f'hunter:{profile.pk}:traveler:{kind}'
    contract = dict(key=key, name='Ruptura do Selo' if kind == 'rupture' else 'Véu Desfeito',
                    maximum=maximum, reset='long_rest', origin='hunter-rework:traveler')
    row = person.recursos.filter(chave=key).first()
    current = max(0, maximum - max(0, row.maximo - row.atual)) if row else maximum
    return contract, current


def panel(profile):
    prepared = preparation(profile, selected=[], allow_pending_order=True)
    if prepared['order'] != ORDER or prepared['level'] < 3:
        return None
    state = dict(profile.traveler or {})
    mark = profile.mark or {}
    rupture_max = veil_max = rupture_current = veil_current = 0
    modifier = 0
    options = []
    tagged_grants = uses_tag_spell_grants(profile)
    final_eligible = not tagged_grants and prepared['level'] >= 18 and any(
        row['id'] == 'caminho-final' for row in prepared['exclusive'])
    if final_eligible:
        options = final_options(profile)
    if prepared['level'] >= 6:
        from .character_engine import derive
        person = profile.personagem_classe.id_personagem
        sheet = derive(person, ruleset=profile.ruleset)
        ability = {'int': 'INT', 'wis': 'SAB'}[profile.ability]
        modifier = sheet['atributos'][ability]['mod']
        maximum = max(1, modifier)
        rupture_max = maximum
        _, rupture_current = _uses(profile, 'rupture', maximum)
        if prepared['level'] >= 14:
            veil_max = maximum
            _, veil_current = _uses(profile, 'veil', maximum)
    return dict(state, version=profile.version, level=prepared['level'],
                runes=state.get('runes', []), marked_destination=bool(mark.get('active')),
                marked_target=mark.get('target', '') if mark.get('active') else '',
                leap_limit=18 if prepared['level'] >= 14 else 9,
                step_die=12 if prepared['level'] >= 17 else 10 if prepared['level'] >= 11
                         else 8 if prepared['level'] >= 5 else 6,
                rupture_current=rupture_current, rupture_max=rupture_max,
                veil_current=veil_current, veil_max=veil_max,
                ability_modifier=modifier,
                final_eligible=final_eligible,
                final_options=options,
                final_choices=[] if tagged_grants else state.get('final_choices', []),
                final_used=[] if tagged_grants else state.get('final_used', []),
                final_selection_open=False if tagged_grants else state.get('final_selection_open', False))


def _distance(value, *, limit, label):
    try:
        distance = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'Informe {label} em metros.') from exc
    if not distance.is_finite() or not 0 <= distance <= limit:
        raise ValueError(f'{label.capitalize()} deve estar entre 0 e {limit} metros.')
    return distance


@transaction.atomic
def command(*, character_id, owner_id, operation_id, expected_version, action,
            confirmed, label='', rune_id='', method='', path_m='', landing_m='',
            same_plane=False, attack_action=False, projectile_resolved=False,
            ally='', ally_near_m='', ally_landing_m='', ally_willing=False,
            marked_attacker=False, favored_attacker=False, attack_damage='',
            reduction_roll='', retaliation_target='', retaliation_m='',
            retaliation_roll_1='', retaliation_roll_2='', save_succeeded=False,
            turn_id='', primary_target='', extra_target='', spot_visible=False,
            spot_unoccupied=False, attack_resolved=False, extra_in_reach=False,
            final_spells=(), spell_slug=''):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if action in ('select_final', 'cast_final') and uses_tag_spell_grants(profile):
        raise ValueError('Use a escolha comum de magias da ficha nesta revisao.')
    operation_id = uuid.UUID(str(operation_id))
    version = int(expected_version)
    label, rune_id = str(label).strip(), str(rune_id).strip()
    fingerprint = hashlib.sha256(json.dumps([
        'hunter-traveler', owner_id, version, action, bool(confirmed), label,
        rune_id, method, str(path_m), str(landing_m), bool(same_plane),
        bool(attack_action), bool(projectile_resolved), ally, str(ally_near_m),
        str(ally_landing_m), bool(ally_willing), bool(marked_attacker),
        bool(favored_attacker), str(attack_damage), str(reduction_roll),
        retaliation_target, str(retaliation_m), str(retaliation_roll_1),
        str(retaliation_roll_2), bool(save_succeeded), turn_id, primary_target,
        extra_target, bool(spot_visible), bool(spot_unoccupied),
        bool(attack_resolved), bool(extra_in_reach), list(final_spells), spell_slug],
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
        raise ValueError('Confirme as distâncias e condições declaradas na mesa.')
    state = dict(profile.traveler or {})
    runes = list(state.get('runes', []))
    if action == 'place':
        if not label or len(label) > 160:
            raise ValueError('Identifique o espaço ou objeto da runa em até 160 caracteres.')
        _distance(path_m, limit=9, label='distância até a runa visível')
        runes.append({'id': str(uuid.uuid4()), 'label': label})
        state['runes'] = runes[-2:]
    elif action == 'teleport':
        if method not in ('step', 'leap', 'throw'):
            raise ValueError('Escolha um teleporte da Ordem.')
        if method == 'step' and not attack_action:
            raise ValueError('Passo Rúnico ocorre imediatamente antes de um ataque na ação Atacar.')
        if method == 'throw' and not projectile_resolved:
            raise ValueError('Arremesso Cintilante exige um projétil resolvido.')
        if method == 'throw':
            if rune_id:
                raise ValueError('Arremesso Cintilante usa o ponto onde o projétil parou.')
            limit = 9
            destination = 'ponto de impacto'
        elif rune_id == 'marked':
            if not current['marked_destination'] or not same_plane:
                raise ValueError('A presa deve estar marcada e no mesmo plano.')
            limit = Decimal('Infinity')
            destination = current['marked_target']
        else:
            rune = next((row for row in runes if row['id'] == rune_id), None)
            if rune is None:
                raise ValueError('Escolha uma das duas runas ativas.')
            limit = current['leap_limit'] if method == 'leap' else 9
            destination = rune['label']
        _distance(path_m, limit=limit, label='distância percorrida no teleporte')
        _distance(landing_m, limit=3, label='distância do pouso ao destino')
        if ally:
            if method != 'leap' or current['level'] < 14 or not ally_willing or len(ally) > 160:
                raise ValueError('Véu Desfeito exige Salto Direto, nível 14 e aliado voluntário.')
            _distance(ally_near_m, limit=Decimal('1.5'), label='distância do aliado')
            _distance(ally_landing_m, limit=Decimal('1.5'), label='pouso do aliado')
            contract, _ = _uses(profile, 'veil', current['veil_max'])
            success, _ = spend_resource(person, contract, 1)
            if not success:
                raise ValueError('Usos de Véu Desfeito esgotados até o descanso longo.')
        elif ally_near_m or ally_landing_m or ally_willing:
            raise ValueError('Informe o aliado voluntário para levá-lo no Salto Direto.')
        state['last_teleport'] = {'method': method, 'destination': destination,
                                  'marked': rune_id == 'marked',
                                  'path_m': str(path_m), 'landing_m': str(landing_m),
                                  'ally': ally}
    elif action == 'rupture':
        if current['level'] < 6 or not (favored_attacker or
                marked_attacker and (profile.mark or {}).get('active')):
            raise ValueError('Ruptura do Selo exige nível 6 e ataque de presa marcada ou Inimigo Favorito.')
        try:
            damage, roll = int(attack_damage), int(reduction_roll)
        except (ValueError, TypeError) as exc:
            raise ValueError('Informe o dano do ataque e a rolagem de 1d10.') from exc
        if damage < 0 or not 1 <= roll <= 10:
            raise ValueError('Informe dano não negativo e rolagem de 1d10 válida.')
        reduction = roll + current['ability_modifier'] + current['level']
        retaliate = damage <= reduction
        retaliation_damage = None
        if retaliate and retaliation_target:
            if len(retaliation_target) > 160:
                raise ValueError('Identifique a criatura hostil em até 160 caracteres.')
            _distance(retaliation_m, limit=18, label='distância da criatura hostil visível')
            try:
                rolls = (int(retaliation_roll_1), int(retaliation_roll_2))
            except (ValueError, TypeError) as exc:
                raise ValueError('Informe as duas rolagens do Dado de Caçador.') from exc
            if any(not 1 <= value <= current['step_die'] for value in rolls):
                raise ValueError('Rolagens do Dado de Caçador inválidas.')
            total = sum(rolls)
            retaliation_damage = total // 2 if save_succeeded else total
        elif retaliation_target:
            raise ValueError('Retaliação Planar exige dano reduzido a zero.')
        contract, _ = _uses(profile, 'rupture', current['rupture_max'])
        success, _ = spend_resource(person, contract, 1)
        if not success:
            raise ValueError('Usos de Ruptura do Selo esgotados até o descanso longo.')
        state['last_rupture'] = {'incoming': damage, 'reduction': reduction,
            'remaining': max(0, damage - reduction), 'retaliation_ready': retaliate,
            'target': retaliation_target if retaliate else '',
            'retaliation_damage': retaliation_damage}
    elif action == 'horizon':
        if current['level'] < 10 or not attack_resolved or not spot_visible or not spot_unoccupied:
            raise ValueError('Andarilho exige nível 10, ataque com arma resolvido e destino livre visível.')
        if not turn_id or len(turn_id) > 80 or not primary_target or len(primary_target) > 160:
            raise ValueError('Identifique o turno e o alvo do ataque com arma.')
        _distance(path_m, limit=3, label='teleporte após ataque')
        used = bool(state.get('horizon_turn') == turn_id and state.get('horizon_extra_used'))
        if extra_target:
            if (len(extra_target) > 160 or extra_target.casefold() == primary_target.casefold()
                    or not extra_in_reach or used):
                raise ValueError('Golpe em Cadeia exige alvo diferente ao alcance e uso livre neste turno.')
        elif extra_in_reach:
            raise ValueError('Indique o alvo diferente para Golpe em Cadeia.')
        state.update(horizon_turn=turn_id, horizon_extra_used=used or bool(extra_target),
                     last_teleport={'method': 'horizon', 'destination': 'espaço livre visível',
                                    'path_m': str(path_m), 'primary_target': primary_target,
                                    'extra_target': extra_target})
    elif action == 'select_final':
        selected = list(final_spells)
        allowed = {row['slug'] for row in current['final_options']}
        if (not current['final_eligible'] or not current['final_selection_open']
                or len(selected) != 2 or len(set(selected)) != 2
                or not set(selected) <= allowed):
            raise ValueError('Escolha duas magias distintas de Caminho Final após Descanso Longo.')
        state.update(final_choices=selected, final_used=[], final_selection_open=False)
    elif action == 'cast_final':
        if (not current['final_eligible'] or spell_slug not in current['final_choices']
                or spell_slug in current['final_used']):
            raise ValueError('Magia de Caminho Final indisponível até nova escolha após descanso.')
        from .hunter_resources import contract
        success, _ = spend_resource(person, contract(profile, preparation(profile)), 4)
        if not success:
            raise ValueError('Pontos de Segredo insuficientes para Caminho Final.')
        state['final_used'] = [*current['final_used'], spell_slug]
        state['last_final_cast'] = spell_slug
    else:
        raise ValueError('Evento de travessia inválido.')
    state['last_event'] = action
    profile.traveler = state
    profile.version += 1
    profile.save(update_fields=['traveler', 'version'])
    response = dict(state, version=profile.version)
    TbOperacaoRecurso.objects.create(id_personagem=person, operation_id=operation_id,
                                     fingerprint=fingerprint, resposta=response, status_http=200)
    return response


def grant_long_rest(person):
    for profile in TbPersonagemCacador.objects.select_for_update().select_related(
            'ruleset', 'personagem_classe').filter(personagem_classe__id_personagem=person):
        if uses_tag_spell_grants(profile):
            continue
        prepared = preparation(profile, selected=[], allow_pending_order=True)
        if (prepared['order'] != ORDER or prepared['level'] < 18
                or not any(row['id'] == 'caminho-final' for row in prepared['exclusive'])):
            continue
        state = dict(profile.traveler or {})
        state.update(final_choices=[], final_used=[], final_selection_open=True)
        profile.traveler = state
        profile.version += 1
        profile.save(update_fields=['traveler', 'version'])
