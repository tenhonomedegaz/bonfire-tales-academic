from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .hunter_rework import catalog, prepare
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def regularization_preview(request, pk):
    from django.conf import settings
    from .models import TbPersonagem, TbPersonagemClasse, TbRuleset
    from .hunter_regularization import preview_legacy_hunter, apply_regularization
    from .class_publication import published_catalog

    person = get_object_or_404(TbPersonagem, pk=pk, dono=request.user, arquivado=False)
    pc = get_object_or_404(TbPersonagemClasse, id_personagem=person, id_classe__slug='cacador')
    if hasattr(pc, 'cacador_rework'):
        from django.http import Http404
        raise Http404('Hunter already has a bound revision.')
    try:
        published = published_catalog(pc.id_classe)
        if published:
            ruleset = published[0]
        else:
            checksum = getattr(settings, 'HUNTER_CREATOR_RULESET_CHECKSUM', '')
            ruleset = TbRuleset.objects.filter(checksum=checksum).first() if checksum else None
    except (ObjectDoesNotExist, ValueError, KeyError, TypeError):
        ruleset = None
    comparison = None
    error = None
    if ruleset:
        try:
            if request.method == 'POST':
                if request.POST.get('ruleset_checksum') != ruleset.checksum:
                    raise ValueError('A revisão de destino mudou. Recarregue a prévia.')
                old_order = request.POST.get('expected_order_id') or None
                apply_regularization(person_id=person.pk, owner_id=request.user.pk,
                    ruleset=ruleset, ability=request.POST.get('ability'),
                    order_id=request.POST.get('order') or None,
                    selected=request.POST.getlist('secret'),
                    expected_level=request.POST.get('expected_level'),
                    expected_order_id=int(old_order) if old_order else None,
                    confirmed=request.POST.get('confirm'),
                    confirmed_style_id=request.POST.get('confirm_style_id'),
                    confirmed_secret_ids=request.POST.getlist('confirm_secret_id'),
                    confirmed_favored_ids=request.POST.getlist('confirm_favored_id'),
                    active_favored_ids=request.POST.getlist('active_favored_id'),
                    confirmed_mastery_ids=request.POST.getlist('confirm_mastery_id'),
                    replace_choice_ids=request.POST.getlist('replace_choice_id'))
                return redirect('hunter_sheet', pk=person.pk)
            comparison = preview_legacy_hunter(person, pc, ruleset,
                candidate_order_id=request.GET.get('order') if request.method == 'GET'
                else request.POST.get('order'))
        except (ValueError, ObjectDoesNotExist) as exc:
            error = str(exc)
            try:
                comparison = preview_legacy_hunter(person, pc, ruleset)
            except (ValueError, ObjectDoesNotExist):
                comparison = None
    else:
        error = 'A revisão de destino ainda não está configurada.'
    return render(request, 'home/pages/hunter_regularization.html', {
        'person': person, 'comparison': comparison, 'error': error,
    })


@login_required(login_url='/login/')
@require_GET
def laboratory(request):
    from .views import _criador_hunter_catalog_args, HunterCreatorCatalogUnavailable
    from .content_versions import resolve_content
    from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog
    from django.utils.text import slugify

    published = None
    try:
        binding = _criador_hunter_catalog_args()
        published = binding.get('hunter_ruleset')
        data = (resolve_content(published, 'hunter-rework',
                evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
                if published else catalog())
        class_catalog = (VersionedClassCatalog(published, binding['hunter_class_id'])
                         if published else None)
        order_ids = (resolve_content(published, 'class-catalog:%s' % binding['hunter_class_id'],
                     evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
                     .get('hunter_order_replacements', {}).get('order_ids', {})
                     if published else {})
    except (HunterCreatorCatalogUnavailable, ObjectDoesNotExist, ValueError):
        return render(request, 'home/pages/hunter_laboratory.html', {
            'error': 'A revisão publicada do Caçador está indisponível. Tente novamente após a correção do catálogo.',
        }, status=503)
    inputs = dict(level=request.GET.get('level', '1'),
                  total_level=request.GET.get('total_level') or request.GET.get('level', '1'),
                  ability=request.GET.get('ability', 'wis'), order=request.GET.get('order', ''),
                  selected=request.GET.getlist('secret'))
    error = None
    combat_inputs = {key: request.GET.get(key, default) for key, default in
                     [('intelligence', '10'), ('wisdom', '10'), ('walking_speed', '30')]}
    for key in ('marked', 'favored', 'secret_affected', 'first_attack', 'injured',
                'enemy_hit_this_turn', 'final_hunt', 'first_turn', 'in_dim_light',
                'using_attack_action'):
        combat_inputs[key] = request.GET.get(key) == '1'
    combat_inputs['third_attack_available'] = request.GET.get('third_used') != '1'
    combat_inputs['punishment_available'] = request.GET.get('punishment_used') != '1'
    combat_inputs['protective_ability'] = request.GET.get('protective_ability', 'int')
    combat = None
    from .hunter_swarm_combat import evaluate as swarm_evaluate, COMMANDS
    swarm_inputs = dict(commands=request.GET.getlist('swarm_command'),
        damage=request.GET.get('swarm_damage', '0'),
        barrier_ability=request.GET.get('barrier_ability', 'int'))
    for key in ('hit', 'own_turn', 'command_used', 'barrier_used'):
        swarm_inputs[key] = request.GET.get('swarm_' + key) == '1'
    swarm = None
    companion_examples = []
    try:
        result = prepare(**inputs, data=data)
        order_id = None
        if published and result['order']:
            order_id = order_ids.get(result['order'])
            if (order_id not in class_catalog.subclasses or
                    slugify(class_catalog.subclasses[order_id].nome) != result['order']):
                raise ValueError('A Ordem selecionada não tem identidade única na revisão publicada.')
        from .hunter_combat import evaluate
        combat = evaluate(result, **combat_inputs)
        swarm = swarm_evaluate(result, combat, **swarm_inputs,
            marked=combat_inputs['marked'], intelligence=combat_inputs['intelligence'],
            wisdom=combat_inputs['wisdom'])
        if result['order'] == 'ordem-da-alianca-selvagem':
            from .hunter_companion import companion_block
            from .battle_familiar import FORMS
            from .hunter_spellcasting import progression_at
            row = (progression_at(class_catalog.classe, result['level'], published)
                   if published else result['progression'])
            circle = max(2, max((i for i, slots in enumerate(row['slots'], 1) if slots), default=0))
            companion_examples = [dict(active=True,
                block=companion_block(dict(circle=circle, battle_form=form),
                    result['level'], result['proficiency'], combat['spell_attack']),
                rend_attacks=2 if result['level'] >= 10 else 1)
                for form in FORMS]
    except (ValueError, TypeError) as exc:
        error = str(exc)
        result = None
    from .hunter_rework import level_features
    features = level_features(result['level'], result['order']) if result and not published else []
    if published and result:
        features = [dict(level=feature.niveladquirido, name=feature.nome,
                         text=feature.descricao,
                         order=class_catalog.subclasses[order_id].nome
                               if feature.id_subclasse_id and order_id else '')
                    for _, _, feature, _ in class_catalog.features(result['level'], order_id)]
    return render(request, 'home/pages/hunter_laboratory.html', {
        'page_title': 'Laboratório do Caçador', 'orders': data['orders'],
        'inputs': inputs, 'result': result, 'error': error,
        'features': features,
        'companion_examples': companion_examples,
        'ruleset_checksum': published.checksum if published else '',
        'combat': combat, 'combat_inputs': combat_inputs,
        'swarm': swarm, 'swarm_inputs': swarm_inputs, 'swarm_commands': COMMANDS,
    }, status=400 if error else 200)


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def character_preparation(request, pk):
    from .models import TbPersonagem, TbPersonagemCacador
    from .hunter_preparation import preparation, save_preparation
    from .hunter_resources import state, use_secret
    from .hunter_masteries import state as mastery_state, save as save_masteries
    from .hunter_reaction import panel as reaction_panel, use as use_reaction
    from .hunter_choices import favored_state, save_favored
    from .hunter_mark import panel as mark_panel, command as mark_command
    from .hunter_expertise import choice_state, save_expertise
    from .hunter_styles import style_state, save_style
    from .hunter_spell_preparation import panel as spell_panel, save_spells
    from .hunter_passives import choose_twilight_save
    from .hunter_exterminator import choose_protective, protective_state
    from .hunter_companion import panel as companion_panel, command as companion_command
    from .hunter_awakening import panel as awakening_panel, command as awakening_command
    from .hunter_exorcist import panel as exorcist_panel, command as exorcist_command
    from .hunter_lantern import panel as lantern_panel, command as lantern_command
    from .hunter_mutagens import panel as mutagens_panel, command as mutagens_command
    from .hunter_traveler import panel as traveler_panel, command as traveler_command
    import uuid
    person = get_object_or_404(TbPersonagem, pk=pk, dono=request.user, arquivado=False)
    profile = get_object_or_404(TbPersonagemCacador.objects.select_related(
        'ruleset', 'personagem_classe'), personagem_classe__id_personagem=person)
    error = None
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'mark':
                mark_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'), expected_version=request.POST.get('version'),
                    action=request.POST.get('mark_event'), target=request.POST.get('target', ''),
                    seconds=request.POST.get('seconds') or 0, confirmed=request.POST.get('confirmed') == '1',
                    final_hunt=request.POST.get('final_hunt') == '1',
                    anticipate=request.POST.get('anticipate') == '1',
                    clues=request.POST.getlist('clue'),
                    target_type=request.POST.get('target_type', ''),
                    same_plane=request.POST.get('same_plane') == '1',
                    distance_miles=request.POST.get('distance_miles', ''),
                    mortuary_damage_type=request.POST.get('mortuary_damage_type', ''),
                    defenses={key: request.POST.get(key, '') for key in
                              ('immunities', 'resistances', 'vulnerabilities',
                               'condition_immunities')})
            elif request.POST.get('action') == 'companion':
                companion_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('version'),
                    action=request.POST.get('companion_event'),
                    battle_form=request.POST.get('battle_form', ''),
                    hp_amount=request.POST.get('companion_hp') or 0,
                    confirmed=request.POST.get('confirmed') == '1',
                    form=request.POST.get('form', ''),
                    creature_type=request.POST.get('creature_type', ''),
                    evolutions=request.POST.getlist('evolution'),
                    large=request.POST.get('large') == '1',
                    seconds=request.POST.get('seconds') or 0,
                    turn_key=request.POST.get('companion_turn', ''),
                    command_mode=request.POST.get('command_mode', 'bonus'),
                    rend_count=request.POST.get('rend_count') or 1,
                    extra_rend=request.POST.get('extra_rend') == '1',
                    target=request.POST.get('companion_target', ''),
                    spell_state_key=request.POST.get('companion_spell_state', ''),
                    self_only_no_area=request.POST.get('self_only_no_area') == '1',
                    companion_within_9m=request.POST.get('companion_within_9m') == '1')
            elif request.POST.get('action') == 'awakening':
                awakening_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('version'),
                    action=request.POST.get('awakening_event'),
                    confirmed=request.POST.get('confirmed') == '1',
                    seconds=request.POST.get('seconds') or 0,
                    initial_howl=request.POST.get('initial_howl') == '1')
            elif request.POST.get('action') == 'reaper_form':
                slot_choice = request.POST.get('slot_choice', '')
                exorcist_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('version'),
                    action=request.POST.get('reaper_event'),
                    confirmed=request.POST.get('confirmed') == '1',
                    mode=request.POST.get('mode', ''),
                    slot_level=slot_choice.partition(':')[0] or 0,
                    slot_version=slot_choice.partition(':')[2],
                    seconds=request.POST.get('seconds') or 0)
            elif request.POST.get('action') == 'mutagens':
                mutagens_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('version'),
                    action=request.POST.get('mutagen_event'), confirmed=request.POST.get('confirmed') == '1',
                    selected=request.POST.getlist('formula_choice'), formula=request.POST.get('formula', ''),
                    seconds=request.POST.get('seconds') or 0, movement=request.POST.get('movement', ''),
                    resistances=request.POST.getlist('resistance'),
                    turn_key=request.POST.get('mutagen_turn', ''),
                    healing_amount=request.POST.get('healing_amount') or 0,
                    replaced_formula=request.POST.get('replaced_formula', ''),
                    target=request.POST.get('mutagen_target', ''),
                    damage_type=request.POST.get('mutagen_damage_type', ''),
                    critical=request.POST.get('mutagen_critical') == '1',
                    favored=request.POST.get('mutagen_favored') == '1',
                    attack_kind=request.POST.get('mutagen_attack_kind', ''),
                    save_total=request.POST.get('mutagen_save_total') or 0)
            elif request.POST.get('action') == 'lantern':
                lantern_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('version'),
                    action=request.POST.get('lantern_event'),
                    confirmed=request.POST.get('confirmed') == '1',
                    form=request.POST.get('form', ''),
                    radius_m=request.POST.get('radius_m', ''),
                    target=request.POST.get('target', ''),
                    distance_m=request.POST.get('distance_m', ''),
                    undead=request.POST.get('undead') == '1',
                    total_cover=request.POST.get('total_cover') == '1',
                    corpse_id=request.POST.get('corpse_id', ''),
                    corpse_large_or_less=request.POST.get('corpse_large_or_less') == '1',
                    last_actions=request.POST.get('last_actions', ''),
                    rest_event=request.POST.get('rest_event', ''),
                    seconds=request.POST.get('seconds') or 0,
                    possessed=request.POST.get('possessed') == '1',
                    charisma_save_failed=request.POST.get('charisma_save_failed') == '1',
                    mode=request.POST.get('mode', ''),
                    roll_1=request.POST.get('roll_1') or 0,
                    roll_2=request.POST.get('roll_2') or 0,
                    target_undead=request.POST.get('target_undead') == '1',
                    target_possessor=request.POST.get('target_possessor') == '1',
                    turn_targets=request.POST.get('turn_targets', ''),
                    ritual_spell=request.POST.get('ritual_spell', ''),
                    ritual_site=request.POST.get('ritual_site', ''),
                    bind_site=request.POST.get('bind_site') == '1')
            elif request.POST.get('action') == 'traveler':
                traveler_command(character_id=pk, owner_id=request.user.pk,
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('version'),
                    action=request.POST.get('traveler_event'),
                    confirmed=request.POST.get('confirmed') == '1',
                    label=request.POST.get('label', ''),
                    rune_id=request.POST.get('rune_id', ''),
                    method=request.POST.get('method', ''),
                    path_m=request.POST.get('path_m', ''),
                    landing_m=request.POST.get('landing_m', ''),
                    same_plane=request.POST.get('same_plane') == '1',
                    attack_action=request.POST.get('attack_action') == '1',
                    projectile_resolved=request.POST.get('projectile_resolved') == '1',
                    ally=request.POST.get('ally', ''),
                    ally_near_m=request.POST.get('ally_near_m', ''),
                    ally_landing_m=request.POST.get('ally_landing_m', ''),
                    ally_willing=request.POST.get('ally_willing') == '1',
                    marked_attacker=request.POST.get('marked_attacker') == '1',
                    favored_attacker=request.POST.get('favored_attacker') == '1',
                    attack_damage=request.POST.get('attack_damage', ''),
                    reduction_roll=request.POST.get('reduction_roll', ''),
                    retaliation_target=request.POST.get('retaliation_target', ''),
                    retaliation_m=request.POST.get('retaliation_m', ''),
                    retaliation_roll_1=request.POST.get('retaliation_roll_1', ''),
                    retaliation_roll_2=request.POST.get('retaliation_roll_2', ''),
                    save_succeeded=request.POST.get('save_succeeded') == '1',
                    turn_id=request.POST.get('turn_id', ''),
                    primary_target=request.POST.get('primary_target', ''),
                    extra_target=request.POST.get('extra_target', ''),
                    spot_visible=request.POST.get('spot_visible') == '1',
                    spot_unoccupied=request.POST.get('spot_unoccupied') == '1',
                    attack_resolved=request.POST.get('attack_resolved') == '1',
                    extra_in_reach=request.POST.get('extra_in_reach') == '1',
                    final_spells=request.POST.getlist('final_spell'),
                    spell_slug=request.POST.get('spell_slug', ''))
            elif request.POST.get('action') == 'masteries':
                save_masteries(character_id=pk, owner_id=request.user.pk,
                    selected=request.POST.getlist('mastery'), expected_version=request.POST.get('version'))
            elif request.POST.get('action') == 'twilight_save':
                choose_twilight_save(character_id=pk, owner_id=request.user.pk,
                    ability=request.POST.get('ability'), expected_version=request.POST.get('version'))
            elif request.POST.get('action') == 'protective_choice':
                choose_protective(character_id=pk, owner_id=request.user.pk,
                    ability=request.POST.get('ability'), expected_version=request.POST.get('version'))
            elif request.POST.get('action') == 'reaction':
                use_reaction(character_id=pk, owner_id=request.user.pk,
                    ability=request.POST.get('reaction_ability'), trigger=request.POST.get('trigger'),
                    confirmed=request.POST.get('confirmed') == '1',
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('resource_version'))
            elif request.POST.get('action') == 'use':
                use_secret(character_id=pk, owner_id=request.user.pk,
                    secret_id=request.POST.get('secret'), enhanced=request.POST.get('enhanced') == '1',
                    operation_id=request.POST.get('operation_id'),
                    expected_version=request.POST.get('resource_version'))
            elif request.POST.get('action') == 'spells':
                save_spells(character_id=pk, owner_id=request.user.pk,
                            selected=request.POST.getlist('spell'),
                            expected_version=request.POST.get('version', ''))
            elif request.POST.get('action') == 'style':
                save_style(character_id=pk, owner_id=request.user.pk,
                           selected=request.POST.get('style'),
                           expected_version=request.POST.get('version', ''))
            elif request.POST.get('action') == 'expertise':
                save_expertise(character_id=pk, owner_id=request.user.pk,
                               selected=request.POST.getlist('expertise'),
                               expected_version=request.POST.get('version', ''))
            elif request.POST.get('action') == 'favored':
                save_favored(character_id=pk, owner_id=request.user.pk,
                             selected=request.POST.getlist('favored'),
                             expected_version=request.POST.get('version', ''))
            elif request.POST.get('action', 'prepare') == 'prepare':
                save_preparation(character_id=pk, owner_id=request.user.pk,
                                 selected=request.POST.getlist('secret'),
                                 expected_version=request.POST.get('version', ''))
            else:
                raise ValueError('Ação inválida.')
        except (ValueError, TypeError, ObjectDoesNotExist) as exc:
            error = str(exc)
            profile.refresh_from_db()
        else:
            return redirect('hunter_preparation', pk=pk)
    try:
        result = preparation(profile)
    except ValueError as exc:
        # A changed level/order may invalidate old preparation. Show valid options,
        # requiring explicit reselection rather than silently altering stored choices.
        error = error or str(exc)
        try:
            result = preparation(profile, selected=[])
        except (ValueError, ObjectDoesNotExist):
            result = None
    resource = state(profile, result) if result else None
    expertise, expertise_error, style, sheet, spells = None, None, None, None, None
    if result:
        from .character_engine import derive
        try:
            style = style_state(profile)
            sheet = derive(person, ruleset=profile.ruleset)
            expertise = choice_state(profile, sheet['pericias'])
            spells = spell_panel(profile, sheet)
        except (ValueError, ObjectDoesNotExist):
            expertise_error = 'A revisão da ficha precisa estar completa para escolher perícias com segurança.'
    use_options = ([dict(secret, operation_id=str(uuid.uuid4()))
                    for secret in result['available']
                    if secret['id'] not in ('cacada-final', 'forma-primordial-suprema',
                        'despertar-final', 'santuario-do-veu', 'forma-quimerica',
                        'caminho-final')]
                   if result else [])
    reactions = []
    masteries = None
    mastery_error = None
    if result:
        try:
            masteries = mastery_state(profile)
        except (ValueError, ObjectDoesNotExist):
            mastery_error = 'A revisão precisa conter os catálogos completos para escolher Maestrias.'
    if result:
        try:
            for ability in ('int', 'wis'):
                reaction = reaction_panel(profile, ability)
                if reaction:
                    reactions.append(dict(reaction, operation_id=str(uuid.uuid4())))
        except (ValueError, ObjectDoesNotExist) as exc:
            error = error or str(exc)
    return render(request, 'home/pages/hunter_preparation.html', {
        'person': person, 'profile': profile, 'result': result, 'error': error,
        'resource': resource,
        'use_options': use_options,
        'favored': favored_state(profile) if result else None,
        'expertise': expertise, 'expertise_error': expertise_error,
        'style': style,
        'hunter_sheet': sheet,
        'spell_preparation': spells,
        'reactions': reactions,
        'masteries': masteries,
        'mastery_error': mastery_error,
        'mark': mark_panel(profile), 'mark_operation_id': str(uuid.uuid4()),
        'companion': companion_panel(profile),
        'shareable_spell_states': list(person.estados.filter(
            ativo=True, chave__startswith='spell:', origem__startswith='magia:')),
        'companion_operation_id': str(uuid.uuid4()),
        'awakening': awakening_panel(profile),
        'awakening_operation_id': str(uuid.uuid4()),
        'exorcist': exorcist_panel(profile),
        'exorcist_operation_id': str(uuid.uuid4()),
        'lantern': lantern_panel(profile),
        'mutagens': mutagens_panel(profile), 'mutagens_operation_id': str(uuid.uuid4()),
        'lantern_operation_id': str(uuid.uuid4()),
        'traveler': traveler_panel(profile),
        'traveler_operation_id': str(uuid.uuid4()),
        'protective': protective_state(profile) if result else None,
    }, status=400 if error else 200)


def linked_sheet_context(person, profile):
    """Resolve every panel consumed by the pinned Hunter sheet, without writes."""
    from .character_engine import derive
    from .views import _magias_sheet_info, _consumiveis_ficha_cards
    from .hunter_mark import panel as mark_panel
    from .hunter_companion import panel as companion_panel
    from .hunter_awakening import panel as awakening_panel
    from .hunter_exorcist import panel as exorcist_panel
    from .hunter_lantern import panel as lantern_panel
    from .hunter_traveler import panel as traveler_panel
    from .hunter_exterminator import protective_state
    from .hunter_mutagens import panel as mutagens_panel

    sheet = derive(person, ruleset=profile.ruleset)
    spell_slots = _magias_sheet_info(person, sheet, [], ruleset=profile.ruleset)['slots']
    resource_cards = [card for card in _consumiveis_ficha_cards(
        person, sheet, ruleset=profile.ruleset, materialize=False)
        if card['kind'] == 'recurso']
    return {
        'sheet': sheet, 'spell_slots': spell_slots, 'resource_cards': resource_cards,
        'mark': mark_panel(profile), 'companion': companion_panel(profile),
        'awakening': awakening_panel(profile), 'exorcist': exorcist_panel(profile),
        'lantern': lantern_panel(profile), 'traveler': traveler_panel(profile),
        'protective': protective_state(profile), 'mutagens': mutagens_panel(profile),
    }


@login_required(login_url='/login/')
@require_GET
def character_sheet(request, pk):
    """Read the linked sheet without synchronizing or rewriting possessions."""
    from django.http import Http404
    from .models import TbPersonagem, TbPersonagemCacador
    from .permissions import pode_ver_ficha
    person = get_object_or_404(TbPersonagem, pk=pk)
    if not pode_ver_ficha(request.user, person):
        raise Http404()
    profile = get_object_or_404(TbPersonagemCacador.objects.select_related('ruleset', 'personagem_classe'),
        personagem_classe__id_personagem=person)
    error = None
    linked = {}
    try:
        linked = linked_sheet_context(person, profile)
    except (ValueError, ObjectDoesNotExist) as exc:
        import logging
        logging.getLogger(__name__).warning('Linked Hunter sheet calculation failed: %s', exc)
        error = 'A revisão vinculada está incompleta. Os valores da ficha não puderam ser calculados.'
        linked = {'sheet': None, 'spell_slots': [], 'resource_cards': []}
    return render(request, 'home/pages/hunter_sheet.html', dict(linked,
        person=person, profile=profile, error=error,
        can_prepare=person.dono_id == request.user.pk and not person.arquivado),
        status=409 if error else 200)
