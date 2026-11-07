import json
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .hunter_catalog import compose_choice_revision, compose_order_revision
from .hunter_traveler import FINAL_SPELLS, command, panel
from .models import TbMagia


class TravelerRuneTests(TestCase):
    def setUp(self):
        from .test_hunter_mark import HunterMarkTests

        HunterMarkTests.setUp(self)
        for index, english in enumerate(FINAL_SPELLS):
            TbMagia.objects.create(nome=f'Magia final {index}', nome_ingles=english,
                                   slug=f'caminho-final-{index}', nivel=6 + index % 2)
        self.bind(self.data)
        self.new = compose_choice_revision(self.ruleset, class_id=self.cl.pk,
            feature_ids=self.features, mark_feature_id=self.mark_feature.pk)
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        self.profile.ruleset = compose_order_revision(self.new, class_id=self.cl.pk,
                                                       order_ids=orders)
        self.profile.save(update_fields=['ruleset'])
        self.pc.id_subclasse_id = orders['ordem-dos-viajantes-primordiais']
        self.pc.nivel = 3
        self.pc.save(update_fields=['id_subclasse', 'nivel'])
        self.profile.refresh_from_db()

    def run_event(self, action, *, operation_id=None, version=None, **changes):
        self.profile.refresh_from_db()
        args = dict(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=operation_id or uuid.uuid4(),
                    expected_version=self.profile.version if version is None else version,
                    action=action, confirmed=True, label='', rune_id='',
                    method='', path_m='', landing_m='', same_plane=False,
                    attack_action=False, projectile_resolved=False)
        args.update(changes)
        return command(**args)

    def test_two_runes_teleports_mark_and_order_gate(self):
        self.assertIsNotNone(panel(self.profile))
        op = uuid.uuid4()
        first = self.run_event('place', operation_id=op, label='Pedra', path_m='9')
        self.assertEqual(first, self.run_event('place', operation_id=op,
                                              version=0, label='Pedra', path_m='9'))
        with self.assertRaises(ValueError):
            self.run_event('place', operation_id=op, version=0,
                           label='Outra', path_m='9')
        second = self.run_event('place', label='Árvore', path_m='3')
        third = self.run_event('place', label='Portão', path_m='8')
        self.assertEqual([row['label'] for row in third['runes']], ['Árvore', 'Portão'])
        with self.assertRaises(ValueError):
            self.run_event('teleport', rune_id=first['runes'][0]['id'], method='leap',
                           path_m='1', landing_m='0')
        with self.assertRaises(ValueError):
            self.run_event('teleport', rune_id=second['runes'][-1]['id'], method='step',
                           path_m='1', landing_m='0')
        step = self.run_event('teleport', rune_id=third['runes'][-1]['id'],
                              method='step', path_m='9', landing_m='3', attack_action=True)
        self.assertEqual(step['last_teleport']['destination'], 'Portão')
        self.profile.mark = {'active': True, 'target': 'Lich', 'remaining_seconds': 100}
        self.profile.save(update_fields=['mark'])
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            self.run_event('teleport', rune_id='marked', method='leap',
                           path_m='200', landing_m='2')
        marked = self.run_event('teleport', rune_id='marked', method='leap',
                                path_m='200', landing_m='2', same_plane=True)
        self.assertEqual(marked['last_teleport']['destination'], 'Lich')
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(panel(self.profile))
        with self.assertRaises(ValueError):
            self.run_event('place', label='Porta', path_m='1')

    def test_http_rune_limits_sheet_and_level14_leap(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, dict(action='traveler',
            traveler_event='place', label='Obelisco', path_m='9.1',
            operation_id=str(uuid.uuid4()), version=0, confirmed='1'))
        self.assertEqual(response.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.traveler, {})
        response = self.client.post(self.url, dict(action='traveler',
            traveler_event='place', label='Obelisco', path_m='9',
            operation_id=str(uuid.uuid4()), version=0, confirmed='1'))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Obelisco')
        rune = self.profile.traveler['runes'][0]['id']
        with self.assertRaises(ValueError):
            self.run_event('teleport', method='leap', rune_id=rune,
                           path_m='18', landing_m='1')
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['leap_limit'], 18)
        self.run_event('teleport', method='leap', rune_id=rune,
                       path_m='18', landing_m='1')
        with self.assertRaises(ValueError):
            self.run_event('teleport', method='throw', path_m='9', landing_m='1')
        self.run_event('teleport', method='throw', path_m='9', landing_m='1',
                       projectile_resolved=True)

    def test_rupture_reaction_damage_receipt_and_long_rest(self):
        with self.assertRaises(ValueError):
            self.run_event('rupture', favored_attacker=True,
                           attack_damage='20', reduction_roll='5')
        self.pc.nivel = 6
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        maximum = panel(self.profile)['rupture_max']
        with self.assertRaises(ValueError):
            self.run_event('rupture', attack_damage='20', reduction_roll='5')
        with self.assertRaises(ValueError):
            self.run_event('rupture', favored_attacker=True,
                           attack_damage='20', reduction_roll='11')
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['rupture_current'], maximum)
        op = uuid.uuid4()
        result = self.run_event('rupture', operation_id=op, favored_attacker=True,
                                attack_damage='99', reduction_roll='1')
        self.assertEqual(result['last_rupture']['reduction'],
                         1 + panel(self.profile)['ability_modifier'] + 6)
        self.assertGreater(result['last_rupture']['remaining'], 0)
        replay = self.run_event('rupture', operation_id=op, version=0,
                                favored_attacker=True, attack_damage='99', reduction_roll='1')
        self.assertEqual(replay, result)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['rupture_current'], maximum - 1)
        self.client.force_login(self.user)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['rupture_current'], maximum)
        self.profile.mark = {'active': True, 'target': 'Lich'}
        self.profile.save(update_fields=['mark'])
        result = self.run_event('rupture', marked_attacker=True,
            attack_damage='5', reduction_roll='10', retaliation_target='Espectro',
            retaliation_m='18', retaliation_roll_1='1', retaliation_roll_2='1',
            save_succeeded=True)
        self.assertTrue(result['last_rupture']['retaliation_ready'])
        self.assertEqual(result['last_rupture']['retaliation_damage'], 1)
        self.assertContains(self.client.get(self.url), 'Retaliação Planar')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Ruptura do Selo')

    def test_veil_ally_restrictions_and_long_rest(self):
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        maximum = panel(self.profile)['veil_max']
        rune = self.run_event('place', label='Pedra', path_m='3')['runes'][0]['id']
        options = dict(method='leap', rune_id=rune, path_m='18', landing_m='1',
                       ally='Ari', ally_near_m='1', ally_landing_m='1', ally_willing=True)
        with self.assertRaises(ValueError):
            self.run_event('teleport', **dict(options, ally_near_m='2'))
        with self.assertRaises(ValueError):
            self.run_event('teleport', **dict(options, method='step',
                                              attack_action=True))
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['veil_current'], maximum)
        self.assertContains(self.client.get(self.url), 'Véu Desfeito')
        first = self.run_event('teleport', **options)
        self.assertEqual(first['last_teleport']['ally'], 'Ari')
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['veil_current'], maximum - 1)
        self.client.force_login(self.user)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['veil_current'], maximum)

    def test_horizon_extra_attack_is_once_per_declared_turn(self):
        options = dict(turn_id='turno-1', primary_target='Lich', extra_target='Espectro',
                       path_m='3', attack_resolved=True, spot_visible=True,
                       spot_unoccupied=True, extra_in_reach=True)
        with self.assertRaises(ValueError):
            self.run_event('horizon', **options)
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            self.run_event('horizon', **dict(options, extra_target='Lich'))
        with self.assertRaises(ValueError):
            self.run_event('horizon', **dict(options, path_m='3.1'))
        first = self.run_event('horizon', **options)
        self.assertEqual(first['last_teleport']['extra_target'], 'Espectro')
        with self.assertRaises(ValueError):
            self.run_event('horizon', **options)
        self.run_event('horizon', **dict(options, extra_target='', extra_in_reach=False))
        second = self.run_event('horizon', **dict(options, turn_id='turno-2'))
        self.assertEqual(second['horizon_turn'], 'turno-2')

    def test_final_path_pinned_spell_selection_cast_and_rest(self):
        from .hunter_spells import granted_spells

        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        options = panel(self.profile)['final_options']
        self.assertEqual(len(options), 6)
        chosen = [options[0]['slug'], options[1]['slug']]
        with self.assertRaises(ValueError):
            self.run_event('select_final', final_spells=chosen)
        self.client.force_login(self.user)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['final_selection_open'])
        with self.assertRaises(ValueError):
            self.run_event('select_final', final_spells=[chosen[0], chosen[0]])
        self.assertEqual(self.client.post(self.url, dict(action='traveler',
            traveler_event='select_final', final_spell=chosen,
            operation_id=str(uuid.uuid4()), version=self.profile.version,
            confirmed='1')).status_code, 302)
        self.profile.refresh_from_db()
        grants = granted_spells(self.person, self.profile.ruleset)
        self.assertTrue(set(chosen) <= {row['slug'] for row in grants})
        self.assertContains(self.client.get(self.url), 'Caminho Final')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            options[0]['name'])
        op = uuid.uuid4()
        cast = self.run_event('cast_final', operation_id=op, spell_slug=chosen[0])
        secret = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(secret.maximo - secret.atual, 4)
        self.assertEqual(cast, self.run_event('cast_final', operation_id=op,
                                             version=2, spell_slug=chosen[0]))
        secret.refresh_from_db()
        self.assertEqual(secret.maximo - secret.atual, 4)
        with self.assertRaises(ValueError):
            self.run_event('cast_final', spell_slug=chosen[0])
        self.run_event('cast_final', spell_slug=chosen[1])
        secret.refresh_from_db()
        self.assertEqual(secret.maximo - secret.atual, 8)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['final_choices'], [])
        self.assertFalse(set(chosen) & {row['slug'] for row in
                         granted_spells(self.person, self.profile.ruleset)})
