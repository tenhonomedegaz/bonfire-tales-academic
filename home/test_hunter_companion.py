import uuid
import json
from io import StringIO

from django.core.management import call_command
from django.urls import reverse

from .hunter_catalog import compose_order_revision
from .hunter_companion import command, panel
from .hunter_rework import catalog
from .hunter_resources import use_secret
from .models import (TbOperacaoRecurso, TbPersonagem, TbPersonagemClasse,
                     TbPersonagemCacador, TbPersonagemEstado, TbPersonagemMagia, TbMagia)
from .test_criador import _CriadorBase
from .test_hunter_catalog import HunterCatalogTests


class HunterCompanionTests(_CriadorBase):
    setup_catalog = HunterCatalogTests.setup_catalog

    def setUp(self):
        self.setup_catalog()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        self.order_ids = json.loads(output.getvalue())['order_ids']
        self.ruleset = compose_order_revision(self.new, class_id=self.classe.pk,
                                               order_ids=self.order_ids)
        self.user = self._novo_usuario('companion')
        self.person = TbPersonagem.objects.create(dono=self.user, nome='Aliado', nivel=3)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.classe, nivel=3, principal=True)
        self.profile = TbPersonagemCacador.objects.create(personagem_classe=self.pc,
            ruleset=self.ruleset, ability='int')
        self.pc.id_subclasse_id = self.order_ids['ordem-da-alianca-selvagem']
        self.pc.save(update_fields=['id_subclasse'])
        self.client.force_login(self.user)
        self.url = reverse('hunter_preparation', args=[self.person.pk])

    def summon(self, *, operation_id=None, version=None, **changes):
        self.profile.refresh_from_db()
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
                      operation_id=operation_id or str(uuid.uuid4()),
                      expected_version=self.profile.version if version is None else version,
                      action='summon', confirmed=True, form='Lobo de bruma', battle_form='bruto',
                      creature_type='Fera', evolutions=['audicao-faro'])
        values.update(changes)
        return command(**values)

    def test_summon_ritual_replay_rest_and_sheet(self):
        initial = panel(self.profile)
        self.assertEqual((initial['available_circle'], initial['hp_bonus'],
                          initial['evolution_limit']), (2, 30, 1))
        op = str(uuid.uuid4())
        posted = self.client.post(self.url, dict(action='companion',
            companion_event='summon', operation_id=op, version=0, confirmed='1',
            form='Lobo de bruma', battle_form='bruto', creature_type='Fera', evolution=['audicao-faro']))
        self.assertEqual(posted.status_code, 302)
        first = self.profile.__class__.objects.get(pk=self.profile.pk).companion
        self.assertEqual((first['cost'], first['circle'], first['active']), (0, 2, True))
        self.assertEqual(self.summon(operation_id=op, version=0)['active'], True)
        self.assertEqual(TbOperacaoRecurso.objects.filter(operation_id=op).count(), 1)
        self.assertContains(self.client.get(self.url), 'Lobo de bruma')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Lobo de bruma')
        second = self.summon(form='Águia', creature_type='Celestial',
                             evolutions=['camuflagem'])
        self.assertEqual(second['cost'], 1)
        resource = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(resource.maximo - resource.atual, 1)
        self.profile.refresh_from_db()
        ended = command(character_id=self.person.pk, owner_id=self.user.pk,
                        operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                        action='fell', confirmed=True)
        self.assertFalse(ended['active'])
        self.assertEqual(resource.maximo - resource.atual, 1)
        rest = self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                                {'tipo': 'longo', 'next': self.url})
        self.assertIn(rest.status_code, (200, 302))
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['free_ready'])
        self.assertEqual(self.summon()['cost'], 0)

    def test_companion_uses_pinned_favored_enemies_and_spell_ability(self):
        from .hunter_choices import save_favored

        self.person.inteligencia = 8
        self.person.sabedoria = 16
        self.person.save(update_fields=['inteligencia', 'sabedoria'])
        self.profile.ability = 'wis'
        self.profile.save(update_fields=['ability'])
        self.summon()
        self.profile.refresh_from_db()
        before = panel(self.profile)
        self.assertEqual(before['favored_types'], [])
        self.assertEqual(before['favored_damage'], 0)
        self.assertEqual(before['favored_pending'], 1)

        save_favored(character_id=self.person.pk, owner_id=self.user.pk,
                     selected=['dragoes'], expected_version=self.profile.version)
        self.profile.refresh_from_db()
        shared = panel(self.profile)
        self.assertEqual(shared['favored_types'], ['Dragões'])
        self.assertEqual(shared['favored_damage'], 3)
        self.assertEqual(shared['favored_pending'], 0)
        self.assertContains(self.client.get(self.url),
                            'Inimigos Favoritos compartilhados: Dragões')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Inimigos Favoritos do espírito: Dragões')

    def test_invalid_choices_and_stale_write_leave_no_effect(self):
        with self.assertRaises(ValueError):
            self.summon(battle_form='')
        for evolutions in ([], ['audicao-faro', 'camuflagem'], ['sopro:fogo', 'sopro:fogo']):
            with self.assertRaises(ValueError):
                self.summon(evolutions=evolutions)
        with self.assertRaises(ValueError):
            self.summon(large=True)
        with self.assertRaises(TbPersonagem.DoesNotExist):
            self.summon(owner_id=self.user.pk + 999)
        self.assertFalse(self.profile.companion)
        self.assertEqual(self.person.recursos.count(), 0)
        self.summon()
        with self.assertRaises(ValueError):
            self.summon(version=0)

    def test_communion_shares_recorded_personal_spell_only_with_current_summon(self):
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        self.person.nivel = 14
        self.person.save(update_fields=['nivel'])
        self.summon(evolutions=['audicao-faro', 'camuflagem',
                                'escalada', 'folego'])
        spell = TbMagia.objects.create(nome='Escudo Pessoal de Teste',
            slug='escudo-pessoal-comunhao-teste', nivel=0, alcance='Auto',
            duracao='Até ser dissipada')
        owned = TbPersonagemMagia.objects.create(id_personagem=self.person,
            id_magia=spell, nome=spell.nome, nivel=spell.nivel,
            preparada=True, origem=self.classe.nome)
        cast = self.client.post(reverse('oficina_conjurar_magia', args=[self.person.pk]),
                                {'magia_personagem': owned.pk})
        self.assertEqual(cast.status_code, 302)
        effect = TbPersonagemEstado.objects.get(id_personagem=self.person,
            chave='spell:%s' % owned.pk, ativo=True)
        self.profile.refresh_from_db()
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
            operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
            action='share_spell', confirmed=True, spell_state_key=effect.chave,
            self_only_no_area=True, companion_within_9m=True)
        with self.assertRaises(ValueError):
            command(**dict(values, companion_within_9m=False))
        effect.refresh_from_db()
        self.assertNotIn('shared_companion_summon_id', effect.payload_json)
        posted = self.client.post(self.url, dict(action='companion',
            companion_event='share_spell', operation_id=values['operation_id'],
            version=values['expected_version'], confirmed='1',
            companion_spell_state=effect.chave, self_only_no_area='1',
            companion_within_9m='1'))
        self.assertEqual(posted.status_code, 302)
        first = command(**values)
        self.assertEqual(command(**values), first)
        effect.refresh_from_db()
        self.assertEqual(effect.payload_json['shared_companion_summon_id'],
                         first['summon_id'])
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['shared_spells'], [spell.nome])
        self.assertContains(self.client.get(self.url), spell.nome)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Comunhão Primordial nesta invocação')
        with self.assertRaises(ValueError):
            command(**dict(values, operation_id=str(uuid.uuid4()),
                           expected_version=self.profile.version))
        self.summon(evolutions=['audicao-faro', 'camuflagem',
                                'escalada', 'folego'])
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['shared_spells'], [])

    def test_breath_uses_pinned_hunter_dc_and_die_once_per_turn(self):
        from .character_engine import derive

        self.summon(evolutions=['sopro:fogo'])
        self.profile.refresh_from_db()
        spirit = panel(self.profile)
        sheet = derive(self.person, ruleset=self.ruleset)
        attrs = sheet['atributos']
        self.assertEqual(spirit['breath_type'], 'fogo')
        self.assertEqual(spirit['breath_damage'],
                         f"{max(1, attrs['INT']['mod'], attrs['SAB']['mod'])}d6")
        self.assertEqual(spirit['breath_dc'],
                         8 + sheet['bonus_proficiencia'] + attrs['INT']['mod'])
        op = str(uuid.uuid4())
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
            operation_id=op, expected_version=self.profile.version,
            action='breath', confirmed=True, turn_key='encontro-1/rodada-1/turno-1')
        first = command(**values)
        self.assertEqual(first['last_breath'], dict(
            turn=values['turn_key'], damage=spirit['breath_damage'],
            damage_type='fogo', dc=spirit['breath_dc'], area='cone de 15 pés',
            save='Destreza', on_success='metade'))
        self.assertEqual(command(**values), first)
        self.assertEqual(TbOperacaoRecurso.objects.filter(operation_id=op).count(), 1)
        self.assertContains(self.client.get(self.url), 'Último sopro')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            spirit['breath_damage'])
        self.profile.refresh_from_db()
        values.update(operation_id=str(uuid.uuid4()), expected_version=self.profile.version)
        with self.assertRaises(ValueError):
            command(**values)
        self.assertEqual(self.summon(evolutions=['sopro:frio'])['cost'], 1)
        self.profile.refresh_from_db()
        values.update(operation_id=str(uuid.uuid4()), expected_version=self.profile.version)
        with self.assertRaises(ValueError):
            command(**values)
        values['turn_key'] = 'encontro-1/rodada-2/turno-1'
        second = command(**values)
        self.assertEqual(second['last_breath']['damage_type'], 'frio')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.companion['breath_turns'],
                         ['encontro-1/rodada-1/turno-1', values['turn_key']])

    def test_command_spends_one_turn_and_reaction_across_rend_and_breath(self):
        self.summon(evolutions=['sopro:fogo'])
        self.profile.refresh_from_db()
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
                      operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                      action='command', confirmed=True, turn_key='encounter/round-1/hunter',
                      command_mode='bonus', rend_count=1)
        first = command(**values)
        self.assertEqual(first['last_command']['rend_attacks'], 1)
        self.assertEqual(command(**values), first)
        self.assertContains(self.client.get(self.url), 'Último Comando')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'encounter/round-1/hunter')
        self.profile.refresh_from_db()
        values.update(operation_id=str(uuid.uuid4()), expected_version=self.profile.version)
        with self.assertRaises(ValueError):
            command(**values)
        with self.assertRaises(ValueError):
            command(**dict(values, action='breath'))
        for invalid in (dict(command_mode='attack'), dict(rend_count=2)):
            with self.assertRaises(ValueError):
                command(**dict(values, turn_key='encounter/round-2/hunter', **invalid))
        with self.assertRaises(ValueError):
            command(**dict(values, action='breath', command_mode='attack',
                           turn_key='encounter/round-2/hunter'))
        with self.assertRaises(ValueError):
            command(**dict(values, action='breath', extra_rend=True,
                           turn_key='encounter/round-2/hunter'))
        self.assertEqual(self.profile.__class__.objects.get(pk=self.profile.pk).version,
                         first['version'])

        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.person.nivel = 10
        self.person.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        advanced = command(**dict(values, expected_version=self.profile.version,
                                  turn_key='encounter/round-2/hunter',
                                  command_mode='attack', rend_count=2))
        self.assertEqual(advanced['last_command']['rend_attacks'], 2)
        self.assertEqual(advanced['last_command']['mode'], 'attack')
        self.profile.refresh_from_db()
        self.assertContains(self.client.get(self.url), 'Instinto Compartilhado')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Instinto Compartilhado')
        with self.assertRaises(ValueError):
            command(**dict(values, operation_id=str(uuid.uuid4()),
                           expected_version=self.profile.version,
                           action='breath', turn_key='encounter/round-2/hunter'))
        posted = self.client.post(self.url, dict(action='companion',
            companion_event='breath', operation_id=str(uuid.uuid4()),
            version=self.profile.version, confirmed='1',
            companion_turn='encounter/round-3/hunter', command_mode='attack',
            extra_rend='1'))
        self.assertEqual(posted.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.companion['last_command']['action'], 'Sopro Primordial')
        self.assertEqual(self.profile.companion['last_command']['mode'], 'attack')
        self.assertEqual(self.profile.companion['last_command']['rend_attacks'], 1)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Retalhar adicional')

    def test_shared_mark_records_only_declared_rend_hits_on_active_target(self):
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.person.nivel = 10
        self.person.save(update_fields=['nivel'])
        self.summon(evolutions=['audicao-faro', 'camuflagem', 'escalada'])
        self.profile.refresh_from_db()
        self.profile.mark = dict(active=True, target='Ogro', remaining_seconds=3600)
        self.profile.save(update_fields=['mark'])
        self.profile.refresh_from_db()
        command(character_id=self.person.pk, owner_id=self.user.pk,
                operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                action='command', confirmed=True, turn_key='encounter/round-1',
                rend_count=2)
        self.profile.refresh_from_db()
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
                      operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                      action='mark_hit', confirmed=True, turn_key='encounter/round-1',
                      target='Ogro')
        first = command(**values)
        self.assertEqual(first['last_mark_hit']['damage'], '1d8')
        self.assertEqual(command(**values), first)
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            command(**dict(values, operation_id=str(uuid.uuid4()),
                           expected_version=self.profile.version, target='Dragão'))
        second = command(**dict(values, operation_id=str(uuid.uuid4()),
                                expected_version=self.profile.version))
        self.assertEqual(second['last_mark_hit']['hit'], 2)
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            command(**dict(values, operation_id=str(uuid.uuid4()),
                           expected_version=self.profile.version))
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Último acerto da Marca Compartilhada')
        self.assertContains(self.client.get(self.url), 'acerto 2')

    def test_selected_totemic_effects_render_with_hunter_progression(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.person.nivel = 18
        self.person.save(update_fields=['nivel'])
        first = self.summon(evolutions=[
            'audicao-faro', 'investida', 'resistencia:fogo',
            'sopro:frio', 'ecolocalizacao'], large=True)
        self.assertTrue(first['active'])
        self.profile.refresh_from_db()
        info = panel(self.profile)
        effects = ' '.join(info['evolution_effects'])
        for rule in ('audição ou olfato', '1d12', 'Força CD',
                     'Resistência a dano de fogo', 'Destreza CD',
                     'Visão às Cegas de 30 pés'):
            self.assertIn(rule, effects)
        self.assertTrue(info['large_grapple_advantage'])
        self.assertEqual(info['shared_mark_damage'], 'd12')
        sheet = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(sheet, 'Visão às Cegas de 30 pés')
        self.assertContains(sheet, 'Marca Compartilhada')
        second = self.summon(evolutions=[
            'camuflagem', 'escalada', 'folego', 'anfibio', 'matilha'])
        self.assertEqual(second['cost'], 1)
        self.profile.refresh_from_db()
        effects = ' '.join(panel(self.profile)['evolution_effects'])
        for rule in ('Furtividade', 'paredes e tetos', '1 hora',
                     'respirar ar e água', 'aliado a até 5 pés'):
            self.assertIn(rule, effects)
        self.assertNotIn('Visão às Cegas', effects)

    def test_totemic_choice_limit_matches_published_page_at_each_level(self):
        from .hunter_rework import level_features

        source = next(row for row in level_features(18, 'ordem-da-alianca-selvagem')
                      if row['id'] == '080-nivel-3-evolucao-totemica')
        for milestone in (3, 6, 10, 14, 18):
            self.assertIn(f'{milestone}º', source['text'])
        for level in range(3, 21):
            self.pc.nivel = level
            self.pc.save(update_fields=['nivel'])
            self.person.nivel = level
            self.person.save(update_fields=['nivel'])
            self.profile.refresh_from_db()
            with self.subTest(level=level):
                info = panel(self.profile)
                self.assertIsNotNone(info)
                self.assertEqual(info['evolution_limit'],
                                 sum(level >= milestone for milestone in (3, 6, 10, 14, 18)))
                self.assertEqual(len(info['options']), 20)

    def test_published_totemic_resistances_change_only_on_next_summon(self):
        self.pc.nivel = 6
        self.pc.save(update_fields=['nivel'])
        self.person.nivel = 6
        self.person.save(update_fields=['nivel'])
        first = self.summon(evolutions=['resistencia:fogo', 'resistencia:frio'])
        self.assertEqual(first['evolutions'], ['resistencia:fogo', 'resistencia:frio'])
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['evolution_limit'], 2)
        self.assertIn('Resistência a dano de fogo.', panel(self.profile)['evolution_effects'])
        self.assertIn('Resistência a dano de frio.', panel(self.profile)['evolution_effects'])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Resistência a dano de frio')
        with self.assertRaises(ValueError):
            self.summon(evolutions=['resistencia:fogo', 'resistencia:fogo'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.companion['evolutions'],
                         ['resistencia:fogo', 'resistencia:frio'])
        second = self.summon(evolutions=['resistencia:ácido', 'resistencia:elétrico'])
        self.assertEqual(second['evolutions'], ['resistencia:ácido', 'resistencia:elétrico'])
        self.profile.refresh_from_db()
        self.assertNotIn('Resistência a dano de fogo.', panel(self.profile)['evolution_effects'])
        self.assertIn('Resistência a dano de ácido.', panel(self.profile)['evolution_effects'])

    def test_legacy_order_cannot_use_companion(self):
        self.pc.id_subclasse_id = 116
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(panel(self.profile))
        with self.assertRaises(ValueError):
            self.summon()

    def test_supreme_form_cost_duration_and_exclusive_source(self):
        from .hunter_rework import level_features
        source = next(row for row in level_features(18, 'ordem-da-alianca-selvagem')
                      if row['id'] == '194-nivel-18-forma-primordial-suprema')
        secret = next(row for row in catalog()['exclusive_secrets']
                      if row['id'] == 'forma-primordial-suprema')
        self.assertEqual(secret['text'], source['text'])
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['supreme_eligible'])
        self.summon(evolutions=['audicao-faro', 'camuflagem', 'escalada',
                                'resistencia:fogo', 'sopro:frio'], large=True)
        self.profile.refresh_from_db()
        op = str(uuid.uuid4())
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
                      operation_id=op, expected_version=self.profile.version,
                      action='supreme', confirmed=True)
        active = command(**values)
        self.assertEqual((active['cost'], active['supreme_remaining_seconds']), (4, 3600))
        self.assertEqual(command(**values), active)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['circle'], 9)
        self.assertEqual(panel(self.profile)['block']['hp_current'], 245)
        self.assertEqual(panel(self.profile)['block']['size'], 'Enorme')
        with self.assertRaises(ValueError):
            use_secret(character_id=self.person.pk, owner_id=self.user.pk,
                secret_id='forma-primordial-suprema', enhanced=False,
                operation_id=str(uuid.uuid4()), expected_version='invalid')
        with self.assertRaises(ValueError):
            command(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                    action='supreme', confirmed=True)
        self.profile.refresh_from_db()
        ended = command(character_id=self.person.pk, owner_id=self.user.pk,
                        operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                        action='elapsed', seconds=3600, confirmed=True)
        self.assertFalse(ended['supreme'])
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['circle'], self.profile.companion['circle'])
        resource = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(resource.maximo - resource.atual, 4)

    def test_block_damage_healing_replay_and_explicit_legacy_shape(self):
        self.summon(battle_form='voador')
        self.profile.refresh_from_db()
        block = panel(self.profile)['block']
        self.assertEqual((block['hp_max'], block['ac'], block['fly_m']), (50, 15, 9))
        self.assertEqual(block['check_save_bonus'], 3)
        self.assertEqual(block['rend_damage'], '1d8+5')
        self.assertContains(self.client.get(self.url), 'Sobrevoo')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])), 'PV 50/50')
        values = dict(character_id=self.person.pk, owner_id=self.user.pk,
                      operation_id=str(uuid.uuid4()), expected_version=self.profile.version,
                      action='damage', hp_amount=12, confirmed=True)
        result = command(**values)
        self.assertEqual(command(**values), result)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['block']['hp_current'], 38)
        response = self.client.post(self.url, dict(action='companion', companion_event='heal',
            operation_id=str(uuid.uuid4()), version=self.profile.version,
            confirmed='1', companion_hp=5))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['block']['hp_current'], 43)
        # Existing appearances do not imply a mechanical shape or grant a free heal.
        state = dict(self.profile.companion)
        del state['battle_form']
        self.profile.companion = state
        self.profile.save(update_fields=['companion'])
        self.assertIsNone(panel(self.profile)['block'])
        self.assertContains(self.client.get(self.url), 'invocação antiga')
        command(**dict(values, operation_id=str(uuid.uuid4()),
                       expected_version=self.profile.version, action='choose_block',
                       battle_form='espreitador', hp_amount=43))
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['block']['hp_current'], 43)
        command(**dict(values, operation_id=str(uuid.uuid4()),
                       expected_version=self.profile.version, action='stalk',
                       turn_key='stalk-turn'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.companion['last_command']['rend_attacks'], 0)
        with self.assertRaises(ValueError):
            command(**dict(values, operation_id=str(uuid.uuid4()),
                           expected_version=self.profile.version, action='command',
                           turn_key='stalk-turn'))
        command(**dict(values, operation_id=str(uuid.uuid4()),
                       expected_version=self.profile.version, hp_amount=43))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.companion['active'])
