import uuid

from django.test import TestCase
from django.urls import reverse

from .hunter_lantern import command, panel


class HunterLanternTests(TestCase):
    def setUp(self):
        from .test_hunter_mortuary import HunterMortuaryTests
        HunterMortuaryTests.setUp(self)

    def lantern(self, action, *, operation_id=None, version=None, **changes):
        self.profile.refresh_from_db()
        arguments = dict(character_id=self.person.pk, owner_id=self.user.pk,
                         operation_id=operation_id or uuid.uuid4(),
                         expected_version=self.profile.version if version is None else version,
                         action=action, confirmed=True)
        arguments.update(changes)
        return command(**arguments)

    def test_fortitude_healing_bonus_on_drunk_vial_once_per_turn(self):
        from .epic_talent_catalog import epic_candidates
        from .epic_healing_bonus import begin_healing_turn
        from .test_epic_healing_bonus import pin_current_origins
        from .models import TbTalento, TbPersonagemTalento
        talent = TbTalento.objects.create(**next(
            row for row in epic_candidates() if row['slug'] == 'dadiva-da-fortitude'))
        TbPersonagemTalento.objects.create(id_personagem=self.person, id_talento=talent,
                                           nome=talent.nome, detalhes='talent_attr:CON')
        pin_current_origins(self.profile)
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.person.pv_atual = 1
        self.person.pv_maximo = 100
        self.person.save(update_fields=['pv_atual', 'pv_maximo'])
        self.lantern('vial', mode='drink', target='self', distance_m='0', roll_1=1, roll_2=1)
        self.person.refresh_from_db()
        first = self.person.pv_atual
        self.lantern('vial', mode='drink', target='self', distance_m='0', roll_1=1, roll_2=1)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, first + 12)
        begin_healing_turn(self.person, operation_id=uuid.uuid4(),
                           turn_ref='lantern-turn-2', confirmed=True)
        self.lantern('vial', mode='drink', target='self', distance_m='0', roll_1=1, roll_2=1)
        self.person.refresh_from_db()
        self.assertGreater(self.person.pv_atual, first + 24)

    def test_light_detection_replay_and_replacement(self):
        self.assertIsNotNone(panel(self.profile))
        response = self.client.get(self.url)
        self.assertContains(response, 'Lanterna do Véu')
        self.lantern('configure', form='Lanterna de ferro')
        self.assertEqual(self.lantern('light', radius_m='3')['radius_m'], '3')
        with self.assertRaises(ValueError):
            self.lantern('light', radius_m='1')
        self.assertFalse(self.lantern('detect', distance_m='18', undead=True,
                                      total_cover=True)['last_detection'])
        self.assertTrue(self.lantern('detect', distance_m='18', undead=True)['last_detection'])
        self.assertEqual(self.lantern('corpse', corpse_id='Corpo 1',
            corpse_large_or_less=True, last_actions='Abriu a porta')['last_replay']['actions'],
            'Abriu a porta')
        with self.assertRaises(ValueError):
            self.lantern('corpse', corpse_id='corpo 1', corpse_large_or_less=True,
                         last_actions='Abriu a porta')
        self.lantern('lost')
        with self.assertRaises(ValueError):
            self.lantern('replace', rest_event='short_rest', seconds=3599)
        self.assertTrue(self.lantern('replace', rest_event='short_rest', seconds=3600)['held'])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Lanterna do Véu')
        with self.assertRaises(ValueError):
            self.lantern('ceremony')

    def test_rite_vials_and_reaper_state_survive_each_other(self):
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['vial_max'], 4)
        self.assertEqual(panel(self.profile)['vials'], 4)
        self.lantern('configure', form='Lanterna de ferro')
        operation_id = uuid.uuid4()
        version = self.profile.__class__.objects.get(pk=self.profile.pk).version
        first = self.lantern('ceremony', operation_id=operation_id, version=version,
                             target='Hospedeiro', distance_m='9', possessed=True,
                             charisma_save_failed=True)
        self.assertTrue(first['last_ceremony']['expelled'])
        self.assertEqual(first['vials'], 4)
        again = self.lantern('ceremony', operation_id=operation_id, version=version,
                             target='Hospedeiro', distance_m='9', possessed=True,
                             charisma_save_failed=True)
        self.assertEqual(again, first)
        with self.assertRaises(ValueError):
            self.lantern('ceremony', operation_id=operation_id, version=version,
                         target='Outro', distance_m='9', possessed=True)
        self.person.pv_atual = 1
        self.person.pv_maximo = 30
        self.person.save(update_fields=['pv_atual', 'pv_maximo'])
        self.assertEqual(self.lantern('vial', mode='drink', target='self', distance_m='0',
                                      roll_1=3, roll_2=4)['last_vial']['amount'], 17)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 18)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['vials'], 3)
        for _ in range(3):
            self.lantern('vial', mode='throw', target='Espectro', distance_m='9',
                         roll_1=4, target_undead=True)
        with self.assertRaises(ValueError):
            self.lantern('vial', mode='throw', target='Espectro', distance_m='9',
                         roll_1=4, target_undead=True)
        self.lantern('ceremony')
        thrown = self.lantern('vial', mode='throw', target='Espectro', distance_m='9',
                              roll_1=4, target_undead=True)
        self.assertEqual(thrown['last_vial']['amount'], 8)
        self.assertTrue(thrown['last_vial']['blocks_target_healing_until_next_turn'])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Frascos Consagrados')
        from .hunter_exorcist import command as reaper_command
        self.profile.refresh_from_db()
        reaper_command(character_id=self.person.pk, owner_id=self.user.pk,
                       operation_id=uuid.uuid4(), expected_version=self.profile.version,
                       action='activate', confirmed=True, mode='free')
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.exorcist['active'])
        self.assertEqual(self.profile.exorcist['lantern']['last_vial']['amount'], 8)
        self.lantern('lost')
        self.assertEqual(self.lantern('ceremony')['vials'], 1)
        self.assertEqual(self.lantern('vial', mode='throw', target='Espectro',
                                      distance_m='9', roll_1=3)['last_vial']['amount'], 3)
        for _ in range(6):
            self.lantern('ceremony')
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['vials'], panel(self.profile)['vial_max'])

    def test_http_ownership_order_and_level_gate(self):
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        payload = dict(action='lantern', lantern_event='ceremony',
                       operation_id=str(uuid.uuid4()), version=self.profile.version,
                       confirmed='1')
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(panel(self.profile.__class__.objects.get(pk=self.profile.pk))['vials'], 4)
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(panel(self.profile))
        self.assertEqual(self.client.post(self.url, dict(payload,
            operation_id=str(uuid.uuid4()), version=self.profile.version)).status_code, 400)
        with self.assertRaises(self.person.__class__.DoesNotExist):
            self.lantern('detect', owner_id=self.user.pk + 999, undead=True, distance_m='1')

    def test_turn_undead_multiple_targets_recovery_and_receipt(self):
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        dice = panel(self.profile)['turn_dice']
        rolls = ','.join(['4'] * dice)
        targets = f'Espectro | 6 | falhou | {rolls}\nZumbi | 9 | sucesso | {rolls}'
        op, version = uuid.uuid4(), self.profile.version
        response = self.lantern('turn_undead', operation_id=op,
                                version=version, turn_targets=targets)
        self.assertEqual(response['last_turn'][0]['radiant_damage'], 4 * dice)
        self.assertEqual(response['last_turn'][1]['radiant_damage'], 2 * dice)
        self.assertEqual(response['last_turn'][0]['frightened_and_incapacitated_seconds'], 60)
        self.assertFalse(response['turn_ready'])
        self.assertEqual(self.lantern('turn_undead', operation_id=op,
                                      version=version, turn_targets=targets), response)
        with self.assertRaises(ValueError):
            self.lantern('turn_undead', turn_targets=targets)
        with self.assertRaises(ValueError):
            self.lantern('turn_undead', turn_targets=f'Espectro | 10 | falhou | {rolls}')
        restored = self.lantern('restore_turn')
        self.assertTrue(restored['turn_ready'])
        self.lantern('turn_undead', turn_targets=targets)
        self.assertEqual(self.client.post(reverse('personagem_descansar',
            args=[self.person.pk]), {'tipo': 'curto', 'next': self.url}).status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['turn_ready'])
        self.assertEqual(self.client.post(self.url, {
            'action': 'lantern', 'lantern_event': 'turn_undead',
            'operation_id': str(uuid.uuid4()), 'version': self.profile.version,
            'turn_targets': targets, 'confirmed': '1',
        }).status_code, 302)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Afastar Mortos-Vivos')

    def test_revealing_light_and_speak_dead_long_rest_only(self):
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertFalse(panel(self.profile)['revealing_light'])
        self.lantern('light', radius_m='3')
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['revealing_light'])
        available = panel(self.profile)['speak_max']
        self.assertEqual(self.client.post(self.url, {
            'action': 'lantern', 'lantern_event': 'speak_dead',
            'operation_id': str(uuid.uuid4()), 'version': self.profile.version,
            'target': 'Cadáver A', 'confirmed': '1',
        }).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['speak_remaining'], available - 1)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'curto', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['speak_remaining'], available - 1)
        self.assertEqual(self.client.post(reverse('personagem_descansar',
            args=[self.person.pk]), {'tipo': 'longo', 'next': self.url}).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['speak_remaining'], available)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Luz Reveladora ativa')
        self.lantern('lost')
        self.profile.refresh_from_db()
        self.assertFalse(panel(self.profile)['revealing_light'])
        with self.assertRaises(ValueError):
            self.lantern('speak_dead', target='Cadáver B')

    def test_sanctuary_ritual_recall_rebinding_and_replacement(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['sanctuary_eligible'])
        from .hunter_preparation import preparation
        from .hunter_resources import state as secrets_state
        before = secrets_state(self.profile, preparation(self.profile, selected=[]))['current']
        vials = panel(self.profile)['vials']
        op, version = uuid.uuid4(), self.profile.version
        args = dict(operation_id=op, version=version, ritual_spell='hallow',
                    ritual_site='Capela', bind_site=True)
        first = self.lantern('sanctuary_ritual', **args)
        self.assertEqual(first['sanctuary_site'], 'Capela')
        self.assertEqual(first['vials'], vials - 1)
        self.assertEqual(self.lantern('sanctuary_ritual', **args), first)
        with self.assertRaises(ValueError):
            self.lantern('sanctuary_ritual', **dict(args, ritual_site='Outro local'))
        self.profile.refresh_from_db()
        self.assertEqual(secrets_state(self.profile, preparation(self.profile, selected=[]))['current'],
                         before - 4)
        self.assertEqual(self.lantern('sanctuary_recall')['last_recall']['site'], 'Capela')
        self.profile.refresh_from_db()
        self.assertEqual(secrets_state(self.profile, preparation(self.profile, selected=[]))['current'],
                         before - 8)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Capela vinculado')
        self.assertEqual(self.client.post(reverse('personagem_descansar',
            args=[self.person.pk]), {'tipo': 'longo', 'next': self.url}).status_code, 302)
        self.profile.refresh_from_db()
        response = self.client.post(self.url, {
            'action': 'lantern', 'lantern_event': 'sanctuary_ritual',
            'operation_id': str(uuid.uuid4()), 'version': self.profile.version,
            'ritual_spell': 'forbiddance', 'ritual_site': 'Torre',
            'bind_site': '1', 'confirmed': '1',
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['sanctuary_site'], 'Torre')
        self.lantern('lost')
        self.lantern('replace', rest_event='short_rest', seconds=3600)
        self.profile.refresh_from_db()
        self.assertFalse(panel(self.profile)['sanctuary_site'])
        with self.assertRaises(ValueError):
            self.lantern('sanctuary_recall')

    def test_sanctuary_gate_and_atomic_insufficient_points(self):
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            self.lantern('sanctuary_ritual', ritual_spell='hallow',
                         ritual_site='Capela', bind_site=True)
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            self.lantern('sanctuary_ritual', ritual_spell='hallow',
                         ritual_site='Capela', bind_site=True, confirmed=False)
        from .hunter_preparation import preparation
        from .hunter_resources import contract
        from .resource_engine import spend_resource
        prepared = preparation(self.profile, selected=[])
        success, _ = spend_resource(self.person, contract(self.profile, prepared),
                                    prepared['points'])
        self.assertTrue(success)
        version = self.profile.version
        with self.assertRaises(ValueError):
            self.lantern('sanctuary_ritual', ritual_spell='hallow',
                         ritual_site='Capela', bind_site=True)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.version, version)
        self.assertFalse(panel(self.profile)['sanctuary_site'])
        self.assertEqual(panel(self.profile)['vials'], panel(self.profile)['vial_max'])
