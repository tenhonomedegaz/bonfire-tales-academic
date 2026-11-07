from django.urls import reverse
from django.test import override_settings
from unittest.mock import patch
import uuid

from .character_engine import derive
from . import character_engine
from .hunter_combat import evaluate
from .hunter_rework import prepare
from .hunter_preparation import preparation
from .hunter_resources import state as secret_state, use_secret
from .test_criador import _CriadorBase
from . import test_hunter_catalog, test_hunter_order_levelup


@override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='')
class HunterTwilightTests(_CriadorBase):
    setup_catalog = test_hunter_catalog.HunterCatalogTests.setup_catalog

    def setUp(self):
        test_hunter_order_levelup.HunterOrderLevelUpTests.setUp(self)
        self.pc.id_subclasse_id = self.order_ids['ordem-do-crepusculo']
        self.pc.save(update_fields=['id_subclasse'])
        self.person.inteligencia = 18
        self.person.sabedoria = 14
        self.person.save(update_fields=['inteligencia', 'sabedoria'])

    def test_linked_sheet_has_initiative_and_darkvision_without_legacy_leak(self):
        for level in (3, 6, 14, 20):
            self.pc.nivel = level
            self.pc.save(update_fields=['nivel'])
            current = derive(self.person, ruleset=self.ruleset)
            legacy = derive(self.person)
            self.assertEqual(current['iniciativa'], legacy['iniciativa'] + 4)
            self.assertIn('darkvision 60ft', current['sentidos'])
            self.assertEqual(current['crepusculo']['initiative_bonus'], 4)
            if level >= 6:
                self.assertTrue(current['saves']['DES']['proficiente'])
                self.assertEqual(current['saves']['DES']['bonus'],
                                 legacy['saves']['DES']['bonus'] + current['bonus_proficiencia'])
            self.assertNotIn('crepusculo', legacy)
        self.client.force_login(self.user)
        sheet = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(sheet, 'Caçador das Sombras')
        self.assertContains(sheet, 'Visão no Escuro ampliada')

    def test_conditional_attacks_and_mark_do_not_become_permanent(self):
        for level in (3, 10, 14):
            prepared = prepare(level=level, ability='int', order='ordem-do-crepusculo')
            baseline = evaluate(prepared)
            self.assertFalse(baseline['twilight_extra_attack'])
            self.assertFalse(baseline['twilight_marked_invisible'])
            first = evaluate(prepared, first_turn=True, using_attack_action=True)
            self.assertTrue(first['twilight_extra_attack'])
            self.assertEqual(first['twilight_extra_damage'], level)
            later = evaluate(prepared, in_dim_light=True, using_attack_action=True,
                             marked=True)
            self.assertEqual(later['twilight_extra_attack'], level >= 14)
            self.assertEqual(later['twilight_extra_damage'], level // 2 if level >= 14 else 0)
            self.assertTrue(later['twilight_marked_invisible'])
            self.assertTrue(later['twilight_mark_blocks_special_sight'])
            self.assertEqual(bool(later['twilight_miss_die']), level >= 10)
            self.assertEqual(later['twilight_shadow_step'], level >= 10)
        self.client.force_login(self.user)
        response = self.client.get(reverse('hunter_laboratory'), dict(level=14,
            order='ordem-do-crepusculo', ability='int', first_turn='1',
            in_dim_light='1', using_attack_action='1', marked='1'))
        self.assertContains(response, 'Crepúsculo: efeitos das condições informadas')
        self.assertContains(response, 'Ataque adicional da Ordem nesta ação: sim')

    def test_existing_dexterity_save_requires_explicit_fixed_alternative(self):
        self.pc.nivel = 6
        self.pc.save(update_fields=['nivel'])
        original = character_engine._saves
        def already_proficient(*args, **kwargs):
            saves = original(*args, **kwargs)
            saves['DES']['proficiente'] = True
            saves['DES']['bonus'] += args[2]
            return saves
        with patch('home.character_engine._saves', side_effect=already_proficient):
            sheet = derive(self.person, ruleset=self.ruleset)
            self.assertTrue(sheet['crepusculo']['save_choice_pending'])
            self.client.force_login(self.user)
            url = reverse('hunter_preparation', args=[self.person.pk])
            page = self.client.get(url)
            self.assertContains(page, 'Escolha outro teste de resistência')
            response = self.client.post(url, dict(action='twilight_save', ability='FOR', version=0))
            self.assertEqual(response.status_code, 302)
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.version, 1)
            chosen = derive(self.person, ruleset=self.ruleset)
            self.assertEqual(chosen['crepusculo']['save_proficiency'], 'FOR')
            self.assertTrue(chosen['saves']['FOR']['proficiente'])
            self.assertEqual(self.client.post(url, dict(action='twilight_save',
                ability='CON', version=1)).status_code, 400)
            self.assertEqual(self.client.post(url, dict(action='twilight_save',
                ability='FOR', version=0)).status_code, 400)
            self.client.force_login(self._novo_usuario('twilight-outsider'))
            self.assertEqual(self.client.post(url, dict(action='twilight_save',
                ability='CON', version=1)).status_code, 404)

    def test_night_hunting_field_uses_exclusive_secret_reserve_once(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        prepared = preparation(self.profile)
        self.assertIn('campo-de-caca-noturno',
                      [row['id'] for row in prepared['exclusive']])
        self.assertNotIn('campo-de-caca-noturno',
                         [row['id'] for row in prepared['options']])
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('hunter_preparation',
            args=[self.person.pk])), 'Campo de Caça Noturno')
        operation = uuid.uuid4()
        command = dict(character_id=self.person.pk, owner_id=self.user.pk,
            secret_id='campo-de-caca-noturno', enhanced=False, operation_id=operation,
            expected_version=secret_state(self.profile, prepared)['version'])
        result = use_secret(**command)
        self.assertEqual((result['spent'], result['current']), (4, 14))
        self.assertEqual(use_secret(**command), result)
