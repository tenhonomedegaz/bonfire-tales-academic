from django.test import SimpleTestCase, TestCase

from home.epic_talent_catalog import PARTIAL_EFFECTS
from home.tag_engine import CombatEncounter
from home.tag_engine.attack_effects import ignored_resistance_types, ignores_resistance
from home.tag_engine.evaluator import evaluate_tags
from home.tag_engine.validator import validate_tags_json
from home.tag_engine.library import Library


RELENTLESS = PARTIAL_EFFECTS['dadiva-do-ataque-implacavel']


class RelentlessAttackTests(SimpleTestCase):
    def encounter(self, offensive=RELENTLESS, defense='resist:cortante'):
        encounter = CombatEncounter([
            {'id': 'atacante', 'team': 'a', 'max_hp': 20,
             'offensive_tags': offensive},
            {'id': 'alvo', 'team': 'b', 'max_hp': 30,
             'defensive_tags': ['always_active', defense]},
        ])
        encounter.start_turn('atacante', 1)
        return encounter

    def test_catalog_tags_validate_and_ignore_only_declared_types(self):
        self.assertEqual(validate_tags_json(RELENTLESS, Library()), [])
        result = evaluate_tags(RELENTLESS, {'resolve_runtime': True})
        ignored = ignored_resistance_types(result.operations)
        self.assertEqual(ignored, {'concussao', 'cortante', 'perfurante'})
        self.assertTrue(ignores_resistance(ignored, 'cortante'))
        self.assertFalse(ignores_resistance(ignored, 'fogo'))

    def test_hit_ignores_resistance_and_removal_restores_it(self):
        for tags, expected in ((RELENTLESS, 20), ([], 25)):
            with self.subTest(tags=tags):
                encounter = self.encounter(offensive=tags)
                encounter.attack('alvo', [], hit=True, damage=10,
                                 damage_type='cortante')
                self.assertEqual(encounter.combatants['alvo']['hp'], expected)

    def test_immunity_still_wins_and_other_type_keeps_resistance(self):
        immune = self.encounter(defense='immune:cortante')
        immune.attack('alvo', [], hit=True, damage=10, damage_type='cortante')
        self.assertEqual(immune.combatants['alvo']['hp'], 30)
        other = self.encounter(defense='resist:fogo')
        other.attack('alvo', [], hit=True, damage=10, damage_type='fogo')
        self.assertEqual(other.combatants['alvo']['hp'], 25)


class RelentlessSheetTests(TestCase):
    def test_owned_talent_annotates_only_matching_attack_and_removes_cleanly(self):
        from django.contrib.auth import get_user_model
        from home.character_engine import derive
        from home.models import (TbItemMundano, TbPersonagem,
                                 TbPersonagemItem, TbPersonagemTalento, TbTalento)

        owner = get_user_model().objects.create_user(username='epic-relentless')
        character = TbPersonagem.objects.create(dono=owner, nome='Ataque de teste')
        weapon = TbItemMundano.objects.create(
            nome='Espada de teste', slug='espada-de-teste', categoria='arma',
            subcategoria='arma_marcial', tags_json=['dmg:1d8(cortante)'])
        TbPersonagemItem.objects.create(
            id_personagem=character, id_item_mundano=weapon,
            nome=weapon.nome, equipado=True, tags_json=weapon.tags_json)
        talent = TbTalento.objects.create(
            nome='Talento de teste', slug='talento-implacavel-teste',
            descricao='Teste', tags_json=RELENTLESS)
        owned = TbPersonagemTalento.objects.create(
            id_personagem=character, id_talento=talent,
            categoria='epico', nome=talent.nome)

        def weapon_profile():
            return next(p for p in derive(character)['ataques']['perfis']
                        if p['nome'] == weapon.nome)

        self.assertEqual(weapon_profile()['tipo_dano'], 'cortante')
        self.assertTrue(weapon_profile()['ignora_resistencia'])
        self.assertEqual(weapon_profile()['nota'].count('ignora resistência'), 1)
        owned.delete()
        self.assertNotIn('ignora_resistencia', weapon_profile())
        self.assertNotIn('ignora resistência', weapon_profile()['nota'])
