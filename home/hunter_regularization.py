"""Read-only comparison for a legacy Hunter before any assisted conversion."""

import json

from django.db.models import Q
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify

from .content_versions import resolve_content
from .hunter_rework import prepare
from .models import (TbClassehabilidade, TbPersonagem, TbPersonagemClasse,
                     TbPersonagemCacador, TbPersonagemEscolha, TbOpcaojogo)
from .versioned_classes import VersionedClassCatalog
from .versioned_classes import EVALUATOR, VOCABULARY
from .versioned_options import VersionedOptions


LEGACY_CHOICE_ORIGINS = (
    'Preparos de Caçada', 'Estilo de Luta', 'Estilo de Luta Preparado',
    'Inimigo Favorito', 'Segredos de Caçador',
)


def _unresolved_class_choices(person, pc):
    names = set(TbClassehabilidade.objects.filter(
        id_classe_id=pc.id_classe_id).values_list('nome', flat=True))
    mastery_origin = 'Maestria de Arma (%s)' % pc.id_classe.nome
    return list(person.escolhas.filter(Q(origem__in=names | set(LEGACY_CHOICE_ORIGINS))
        | Q(origem=mastery_origin, tipo='maestria')
        | Q(tipo__icontains='hunter') | Q(tipo__icontains='cacador')
        | Q(tipo__icontains='estilo_luta')).order_by('slot', 'pk').values(
            'id', 'origem', 'tipo', 'valor', 'id_opcao_id', 'slot'))


def _starting_proficiency_choices(person, pc):
    """Class starting skill/tool picks remain owned across regularization."""
    return list(person.escolhas.filter(origem=pc.id_classe.nome,
        tipo__in=('pericia', 'ferramenta')).order_by('tipo', 'slot', 'pk').values(
            'id', 'origem', 'tipo', 'valor', 'slot'))


def _style_transfer(ruleset, pc, choices):
    """Only an exact, pinned option identity may retain a legacy fighting style."""
    styles = [choice for choice in choices
              if choice['origem'] in ('Estilo de Luta', 'Estilo de Luta Preparado')
              and choice['tipo'] in ('estilo_luta', 'estilo-de-luta', 'estilo')
              and choice['slot'] == 0]
    if pc.nivel < 2 or len(styles) != 1:
        return None
    choice = styles[0]
    options = VersionedOptions(ruleset).universe(dict(
        tipo='estilo-de-luta', nivel=pc.nivel,
        constraints={'from_kind': 'classe', 'from_slug': 'cacador'}))
    matches = [option for option in options
               if (option['id'] == choice['id_opcao_id'] if choice['id_opcao_id']
                   else option['slug'] == choice['valor'])]
    return ({'choice': choice, 'option': matches[0]}
            if len(matches) == 1 and not matches[0]['pre'] else None)


def _secret_transfers(choices, hunter_data, level):
    """Map only old secret rows whose persisted identity is unchanged."""
    if not hunter_data:
        return []
    available = {row['id']: row for row in hunter_data['secrets']
                 if row['level'] <= level}
    candidates = [row for row in choices
                  if row['tipo'] in ('segredo', 'segredo-cacador', 'segredo_cacador')
                  and row['valor'] in available]
    option_ids = [row['id_opcao_id'] for row in candidates if row['id_opcao_id']]
    option_slugs = dict(TbOpcaojogo.objects.filter(pk__in=option_ids)
                        .values_list('pk', 'slug'))
    mapped = []
    used = set()
    for row in candidates:
        secret_id = row['valor']
        if (secret_id in used or row['id_opcao_id']
                and option_slugs.get(row['id_opcao_id']) != secret_id):
            continue
        used.add(secret_id)
        mapped.append({'choice': row, 'secret': available[secret_id]})
    return mapped


def _favored_transfers(choices, hunter_data, level):
    """Identify old creature types without silently selecting the active subset."""
    spec = (hunter_data or {}).get('favored_enemies')
    if not spec:
        return []
    candidates = [row for row in choices if row['origem'] == 'Inimigo Favorito']
    if not candidates:
        return []
    allowed = {row['id']: row for row in spec['types']}
    by_name = {row['name']: row for row in spec['types']}
    option_ids = [row['id_opcao_id'] for row in candidates if row['id_opcao_id']]
    option_slugs = dict(TbOpcaojogo.objects.filter(pk__in=option_ids)
                        .values_list('pk', 'slug'))
    limit = sum(level >= milestone for milestone in spec['levels'])
    if not limit:
        return []
    mapped = []
    used = set()
    for row in candidates:
        match = allowed.get(row['valor']) or by_name.get(row['valor'])
        if (not match or match['id'] in used
                or row['id_opcao_id'] and option_slugs.get(row['id_opcao_id']) != match['id']):
            continue
        used.add(match['id'])
        mapped.append({'choice': row, 'favored': match})
    return mapped


def _mastery_transfers(person, pc, ruleset, choices, hunter_data):
    """Retain only three exact, proficient Hunter weapon/mastery pairs."""
    rules = (hunter_data or {}).get('weapon_masteries') or {}
    origin = 'Maestria de Arma (%s)' % pc.id_classe.nome
    candidates = [row for row in choices
                  if row['origem'] == origin and row['tipo'] == 'maestria']
    if (pc.nivel < rules.get('level', 999) or
            len(candidates) != rules.get('count') or
            any(row['id_opcao_id'] for row in candidates)):
        return []
    from .hunter_masteries import available_options
    available = {option['value']: option for option in available_options(person, ruleset)}
    values = [row['valor'] for row in candidates]
    if (any(value not in available for value in values) or
            len({value.split('|')[0] for value in values}) != len(values)):
        return []
    return [{'choice': row, 'option': available[row['valor']]}
            for row in candidates]


REQUIRED_REPLACEMENTS = (
    'hunter_order_replacements', 'hunter_choice_replacements',
    'hunter_passive_replacements', 'hunter_conditional_replacements',
    'hunter_spellcasting_replacement', 'hunter_mark_replacement',
    'hunter_secret_replacements',
)


def _reviewed_target(ruleset, class_id, hunter_data):
    payload = resolve_content(ruleset, 'class-catalog:%s' % class_id,
        evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
    source = hunter_data.get('source_sha256')
    mark = payload.get('hunter_mark_replacement') or {}
    return (bool(source) and mark.get('version') == 1
        and mark.get('duration_seconds') == 3600 and all(
        isinstance(payload.get(key), dict)
        and payload[key].get('source_sha256') == source
        for key in REQUIRED_REPLACEMENTS))


def _target_orders(ruleset, target, *, applying=False):
    payload = resolve_content(ruleset, 'class-catalog:%s' % target.classe.pk,
        evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
    marker = payload.get('hunter_order_replacements') or {}
    if 'order_ids' not in marker:
        return {} if applying else target.subclasses
    ids = marker['order_ids']
    if (not isinstance(ids, dict) or len(set(ids.values())) != len(ids)
            or any(pk not in target.subclasses or slugify(target.subclasses[pk].nome) != slug
                   for slug, pk in ids.items())):
        raise ValueError('O mapeamento das Ordens da revisão é inválido.')
    return {pk: target.subclasses[pk] for pk in ids.values()}


def preview_legacy_hunter(person, pc, ruleset, *, candidate_order_id=None):
    """Compare both catalogs without assuming feature or order equivalence."""
    if pc.id_personagem_id != person.pk or pc.id_classe.slug != 'cacador':
        raise ValueError('This character does not have a Hunter class.')
    if hasattr(pc, 'cacador_rework'):
        raise ValueError('This Hunter already has a bound revision.')

    target = VersionedClassCatalog(ruleset, pc.id_classe_id)
    target_orders = _target_orders(ruleset, target)
    if target.classe.slug != 'cacador':
        raise ValueError('The target ruleset has no Hunter class.')
    if candidate_order_id:
        try:
            order_id = int(candidate_order_id)
        except (TypeError, ValueError):
            raise ValueError('Selecione uma Ordem da revisão de destino.') from None
        if order_id not in target_orders:
            raise ValueError('Selecione uma Ordem da revisão de destino.')
    else:
        order_id = pc.id_subclasse_id if pc.id_subclasse_id in target_orders else None
    live = TbClassehabilidade.objects.filter(
        id_classe_id=pc.id_classe_id, niveladquirido__lte=pc.nivel,
    ).filter(Q(id_subclasse__isnull=True) | Q(id_subclasse_id=pc.id_subclasse_id))
    current = list(live.order_by('niveladquirido', 'nome', 'pk'))
    proposed = [feature for _, _, feature, _ in target.features(pc.nivel, order_id)]
    def rows(features):
        return [{'level': feature.niveladquirido, 'name': feature.nome,
                 'description': feature.descricao} for feature in features]

    choices = ['Escolher Inteligência ou Sabedoria para a revisão do Caçador.']
    if pc.nivel >= 3:
        choices.append('Confirmar a Ordem da revisão; a Ordem antiga não é convertida automaticamente.')
    if order_id is None and pc.nivel >= 3:
        choices.append('Selecionar uma Ordem da revisão antes de comparar suas habilidades exclusivas.')
    choices.append('Revisar manualmente Segredos, Linhas, magias preparadas e opções de classe.')
    try:
        hunter_data = resolve_content(ruleset, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
    except (ObjectDoesNotExist, ValueError):
        hunter_data = None
    choices_found = _unresolved_class_choices(person, pc)
    starting_choices = _starting_proficiency_choices(person, pc)
    style_transfer = _style_transfer(ruleset, pc, choices_found)
    secret_transfers = _secret_transfers(choices_found, hunter_data, pc.nivel)
    favored_transfers = _favored_transfers(choices_found, hunter_data, pc.nivel)
    mastery_transfers = _mastery_transfers(person, pc, ruleset, choices_found, hunter_data)
    favored_limit = (sum(pc.nivel >= level for level in
        hunter_data['favored_enemies']['levels']) if hunter_data and
        hunter_data.get('favored_enemies') else 0)
    mapped_ids = {row['choice']['id'] for row in secret_transfers}
    mapped_ids.update(row['choice']['id'] for row in favored_transfers)
    mapped_ids.update(row['choice']['id'] for row in mastery_transfers)
    if style_transfer:
        mapped_ids.add(style_transfer['choice']['id'])
    return {
        'ruleset_checksum': ruleset.checksum,
        'level': pc.nivel,
        'old_order_id': pc.id_subclasse_id,
        'old_order': pc.id_subclasse.nome if pc.id_subclasse_id else None,
        'candidate_order': target.subclasses[order_id].nome if order_id else None,
        'candidate_order_id': order_id,
        'available_orders': sorted(target_orders.values(), key=lambda order: order.nome),
        'current_features': rows(current),
        'proposed_features': rows(proposed),
        'choices': choices,
        'available_secrets': [row for row in hunter_data['secrets']
                              if row['level'] <= pc.nivel] if hunter_data else [],
        'target_has_hunter_rules': hunter_data is not None,
        'target_ready_for_binding': bool(hunter_data and
            _reviewed_target(ruleset, pc.id_classe_id, hunter_data)),
        'unresolved_class_choices': [row for row in choices_found
            if row['id'] not in mapped_ids],
        'preserved_starting_choices': starting_choices,
        'style_transfer': style_transfer,
        'secret_transfers': secret_transfers,
        'favored_transfers': favored_transfers,
        'mastery_transfers': mastery_transfers,
        'favored_limit': favored_limit,
        'favored_excess': len(favored_transfers) > favored_limit,
        'acquired_spells': list(person.magias.order_by('pk').values('nome', 'nivel', 'preparada', 'origem')),
        'wallet_pc': person.carteira_pc,
        'adventures': person.aventuras,
        'braseiros': person.braseiros,
    }


@transaction.atomic
def apply_regularization(*, person_id, owner_id, ruleset, ability, order_id,
                         selected, expected_level, expected_order_id, confirmed,
                         confirmed_style_id=None, confirmed_secret_ids=(),
                         confirmed_favored_ids=(), active_favored_ids=(),
                         confirmed_mastery_ids=()):
    """Bind a validated old Hunter exactly once; never rebuild possessions."""
    if confirmed != '1':
        raise ValueError('Confirme a regularização antes de aplicar.')
    person = TbPersonagem.objects.select_for_update().get(
        pk=person_id, dono_id=owner_id, arquivado=False)
    pc = TbPersonagemClasse.objects.select_for_update(of=('self',)).select_related(
        'id_classe', 'id_subclasse').get(id_personagem=person, id_classe__slug='cacador')
    if TbPersonagemCacador.objects.filter(personagem_classe=pc).exists():
        raise ValueError('Esta ficha já foi regularizada.')
    if pc.nivel != int(expected_level) or pc.id_subclasse_id != expected_order_id:
        raise ValueError('A ficha mudou desde a prévia. Recarregue antes de confirmar.')
    target = VersionedClassCatalog(ruleset, pc.id_classe_id)
    target_orders = _target_orders(ruleset, target, applying=True)
    if target.classe.slug != 'cacador':
        raise ValueError('A revisão escolhida não contém o Caçador.')
    if pc.nivel >= 3:
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            raise ValueError('Escolha uma Ordem da revisão.') from None
        if order_id not in target_orders:
            raise ValueError('Escolha uma Ordem da revisão.')
    elif order_id:
        raise ValueError('A Ordem só é escolhida a partir do nível 3.')
    else:
        order_id = None

    # A class choice without a reviewed mapping must not continue to grant its
    # legacy effect alongside the new class. Keep the row untouched for a future
    # assisted mapping instead of silently deleting or transferring it.
    unresolved = _unresolved_class_choices(person, pc)
    style_transfer = _style_transfer(ruleset, pc, unresolved)
    if style_transfer:
        if str(confirmed_style_id) != str(style_transfer['choice']['id']):
            raise ValueError('Confirme a transferência do Estilo de Luta antigo.')
        unresolved = [row for row in unresolved
                      if row['id'] != style_transfer['choice']['id']]
    hunter_data = resolve_content(ruleset, 'hunter-rework',
        evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
    if not _reviewed_target(ruleset, pc.id_classe_id, hunter_data):
        raise ValueError('A revisão de destino ainda não possui todas as substituições do Caçador.')
    secret_transfers = _secret_transfers(unresolved, hunter_data, pc.nivel)
    transfer_ids = {row['choice']['id'] for row in secret_transfers}
    if {str(value) for value in confirmed_secret_ids} != {str(value) for value in transfer_ids}:
        raise ValueError('Confirme a transferência de cada Segredo antigo com identidade exata.')
    unresolved = [row for row in unresolved if row['id'] not in transfer_ids]
    favored_transfers = _favored_transfers(unresolved, hunter_data, pc.nivel)
    favored_ids = {row['choice']['id'] for row in favored_transfers}
    if {str(value) for value in confirmed_favored_ids} != {str(value) for value in favored_ids}:
        raise ValueError('Confirme a transferência de cada Inimigo Favorito com identidade exata.')
    favored_limit = sum(pc.nivel >= level for level in
        hunter_data.get('favored_enemies', {}).get('levels', []))
    if len(favored_transfers) > favored_limit:
        active_ids = [str(value) for value in active_favored_ids]
        if (len(active_ids) != favored_limit or len(set(active_ids)) != favored_limit
                or not set(active_ids) <= {str(value) for value in favored_ids}):
            raise ValueError('Escolha quais Inimigos Favoritos antigos ficam ativos neste nível.')
    else:
        if active_favored_ids:
            raise ValueError('Recarregue a prévia de Inimigos Favoritos.')
        active_ids = [str(value) for value in favored_ids]
    active_favored = [row for row in favored_transfers
                      if str(row['choice']['id']) in active_ids]
    deferred_favored = [row['favored']['id'] for row in favored_transfers
                        if str(row['choice']['id']) not in active_ids]
    unresolved = [row for row in unresolved if row['id'] not in favored_ids]
    mastery_transfers = _mastery_transfers(person, pc, ruleset, unresolved, hunter_data)
    mastery_ids = {row['choice']['id'] for row in mastery_transfers}
    if {str(value) for value in confirmed_mastery_ids} != {str(value) for value in mastery_ids}:
        raise ValueError('Confirme a transferência de cada Maestria de Arma antiga.')
    unresolved = [row for row in unresolved if row['id'] not in mastery_ids]
    if unresolved:
        raise ValueError('Há escolhas antigas do Caçador sem mapeamento; revise-as antes de aplicar.')
    order_name = target.subclasses[order_id].nome if order_id else ''
    total = person.classes.aggregate(total=Sum('nivel'))['total']
    result = prepare(level=pc.nivel, total_level=total, ability=ability,
        order=slugify(order_name), selected=selected, data=hunter_data)
    available_ids = {row['id'] for row in result['available']}
    if any(row['secret']['id'] not in available_ids for row in secret_transfers):
        raise ValueError('Prepare os Segredos antigos correspondentes antes de aplicar.')
    from .character_engine import derive
    from .hunter_views import linked_sheet_context
    old_sheet = derive(person)
    old_order = pc.id_subclasse_id
    old_vitals = {'pv_maximo': person.pv_maximo, 'pv_atual': person.pv_atual,
                  'ca': person.ca}
    old_features = list(TbClassehabilidade.objects.filter(
        id_classe_id=pc.id_classe_id, niveladquirido__lte=pc.nivel)
        .filter(Q(id_subclasse__isnull=True) | Q(id_subclasse_id=old_order))
        .order_by('pk').values('id_habilidade', 'nome', 'niveladquirido'))
    starting_before = _starting_proficiency_choices(person, pc)
    spells_before = list(person.magias.select_for_update().order_by('pk').values())
    inventory_before = list(person.inventario.select_for_update().order_by('pk').values())
    adventures_before = list(person.aventuras_ledger.select_for_update().order_by('pk').values())
    wallet_before = (person.carteira_pc, person.aventuras, person.braseiros)
    pc.id_subclasse_id = order_id
    pc.save(update_fields=['id_subclasse'])
    profile = TbPersonagemCacador.objects.create(
        personagem_classe=pc, ruleset=ruleset, ability=ability,
        selected=result['selected'], regularization={
            'schema': 1, 'old_order_id': old_order, 'new_order_id': order_id,
            'old_level': pc.nivel, 'old_pv_max': old_sheet['pv']['maximo_calculado'],
            'old_vitals': old_vitals, 'old_features': old_features,
            'acquired_spell_ids': [row['id'] for row in spells_before],
            'preserved_starting_choices': starting_before,
            'ruleset_checksum': ruleset.checksum,
            'explicit_ability': ability, 'explicit_secrets': result['selected'],
            'transferred_style': style_transfer,
            'transferred_secrets': secret_transfers,
            'transferred_favored': favored_transfers,
            'transferred_masteries': mastery_transfers,
            'deferred_favored': deferred_favored,
        })
    if mastery_transfers:
        from .hunter_masteries import state as mastery_state
        current = mastery_state(profile)
        values = [row['choice']['valor'] for row in mastery_transfers]
        if (current is None or len(values) != current['count'] or
                not set(values) <= {row['value'] for row in current['options']}):
            raise ValueError('As Maestrias antigas não podem ser transferidas nesta revisão.')
        TbPersonagemEscolha.objects.filter(
            pk__in=mastery_ids, id_personagem=person).delete()
        for slot, value in enumerate(values):
            TbPersonagemEscolha.objects.create(id_personagem=person,
                origem='hunter:%s:mastery' % profile.pk,
                tipo='hunter-mastery', slot=slot, valor=value)
        TbPersonagemEscolha.objects.create(id_personagem=person,
            origem='hunter:%s:mastery' % profile.pk,
            tipo='hunter-mastery-rest', slot=0, valor='0')
    if secret_transfers:
        TbPersonagemEscolha.objects.filter(
            pk__in=transfer_ids, id_personagem=person).delete()
    if favored_transfers:
        TbPersonagemEscolha.objects.filter(
            pk__in=favored_ids, id_personagem=person).delete()
        for slot, transfer in enumerate(active_favored):
            TbPersonagemEscolha.objects.create(id_personagem=person,
                origem='hunter:%s:favored' % profile.pk, tipo='hunter-favored',
                slot=slot, valor=transfer['favored']['id'])
        from .hunter_choices import favored_state
        if not favored_state(profile)['valid']:
            raise ValueError('Os Inimigos Favoritos não podem ser transferidos nesta revisão.')
    if style_transfer:
        TbPersonagemEscolha.objects.filter(
            pk=style_transfer['choice']['id'], id_personagem=person).delete()
        TbPersonagemEscolha.objects.create(id_personagem=person,
            origem='hunter:%s:style' % profile.pk, tipo='hunter-style', slot=0,
            valor=json.dumps({'id': style_transfer['option']['id'],
                              'level': pc.nivel}))
        from .hunter_styles import style_state
        style = style_state(profile)
        if not style['valid'] or style['selected'] is None:
            raise ValueError('O Estilo de Luta não pode ser transferido nesta revisão.')
    new_sheet = linked_sheet_context(person, profile)['sheet']
    old_max = int(person.pv_maximo or old_sheet['pv']['maximo_calculado'] or 0)
    old_current = int(person.pv_atual or 0)
    new_max = int(new_sheet['pv']['maximo_calculado'] or 0)
    damage_taken = max(0, old_max - old_current)
    person.pv_maximo = new_max
    person.pv_atual = max(0, new_max - damage_taken)
    person.ca = int(new_sheet.get('ca') or person.ca or 10)
    person.save(update_fields=['pv_maximo', 'pv_atual', 'ca', 'atualizado_em'])
    if (person.carteira_pc, person.aventuras, person.braseiros) != wallet_before:
        raise ValueError('A regularização alterou patrimônio ou histórico.')
    if list(person.magias.order_by('pk').values()) != spells_before:
        raise ValueError('A regularização alterou magias adquiridas.')
    if list(person.inventario.order_by('pk').values()) != inventory_before:
        raise ValueError('A regularização alterou o inventário existente.')
    if list(person.aventuras_ledger.order_by('pk').values()) != adventures_before:
        raise ValueError('A regularização alterou o histórico de aventuras.')
    if _starting_proficiency_choices(person, pc) != starting_before:
        raise ValueError('A regularização alterou perícias ou ferramentas iniciais.')
    return profile
