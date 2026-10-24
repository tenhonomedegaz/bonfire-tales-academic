from django.test import SimpleTestCase, TestCase

from home.epic_talent_catalog import ATTRIBUTE_TAGS, VERIFIED_EFFECTS, epic_candidates
from home.tag_engine import CombatEncounter
from home.tag_engine.attack_effects import ignored_resistance_types, ignores_resistance
from home.tag_engine.evaluator import evaluate_tags
from home.tag_engine.validator import validate_tags_json
from home.tag_engine.library import Library


RELENTLESS = VERIFIED_EFFECTS['dadiva-do-ataque-implacavel']


class RelentlessAttackTests(SimpleTestCase):
    def encounter(self, offensive=RELENTLESS, defense='resist:cortante',
                  talent_score=18):
        encounter = CombatEncounter([
            {'id': 'atacante', 'team': 'a', 'max_hp': 20,
             'offensive_tags': offensive,
             'tag_context': {'talent_attr_score': talent_score}},
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

    def test_critical_bonus_uses_selected_score_and_weapon_damage_type(self):
        critical = self.encounter(talent_score=18)
        critical.attack('alvo', [], hit=True, critical=True, damage=10,
                        damage_type='cortante')
        self.assertEqual(critical.combatants['alvo']['hp'], 2)
        self.assertEqual(critical.events[-1][-1], 28)
        ordinary = self.encounter()
        ordinary.attack('alvo', [], hit=True, damage=10, damage_type='cortante')
        self.assertEqual(ordinary.combatants['alvo']['hp'], 20)
        removed = self.encounter(offensive=[])
        removed.attack('alvo', [], hit=True, critical=True, damage=10,
                       damage_type='cortante')
        self.assertEqual(removed.combatants['alvo']['hp'], 25)

    def test_critical_bonus_respects_immunity_and_resistance(self):
        immune = self.encounter(defense='immune:cortante')
        immune.attack('alvo', [], hit=True, critical=True, damage=10,
                      damage_type='cortante')
        self.assertEqual(immune.combatants['alvo']['hp'], 30)
        resistant = self.encounter(defense='resist:fogo')
        resistant.attack('alvo', [], hit=True, critical=True, damage=10,
                         damage_type='fogo')
        self.assertEqual(resistant.combatants['alvo']['hp'], 16)
        with self.assertRaises(ValueError):
            self.encounter().attack('alvo', [], hit=False, critical=True)

    def test_same_source_repeated_in_attack_is_idempotent_but_other_bonus_stacks(self):
        repeated = self.encounter()
        repeated.attack('alvo', RELENTLESS, hit=True, critical=True,
                        damage=10, damage_type='cortante')
        self.assertEqual(repeated.combatants['alvo']['hp'], 2)
        separate = self.encounter(offensive=RELENTLESS + [
            'always_active{crit_dmg:+2}',
        ])
        separate.attack('alvo', RELENTLESS, hit=True, critical=True,
                        damage=10, damage_type='cortante')
        self.assertEqual(separate.combatants['alvo']['hp'], 0)
        self.assertEqual(next(event for event in separate.events
                              if event[0] == 'attack')[-1], 30)


class RelentlessSheetTests(TestCase):
    def test_candidate_has_both_effects(self):
        candidate = next(row for row in epic_candidates()
                         if row['slug'] == 'dadiva-do-ataque-implacavel')
        self.assertEqual(candidate['tags_json'], ATTRIBUTE_TAGS + RELENTLESS)

    def test_owned_talent_annotates_only_matching_attack_and_removes_cleanly(self):
        from django.contrib.auth import get_user_model
        from home.character_engine import derive
        from home.models import (TbItemMundano, TbPersonagem,
                                 TbPersonagemItem, TbPersonagemTalento, TbTalento)

        owner = get_user_model().objects.create_user(username='epic-relentless')
        character = TbPersonagem.objects.create(
            dono=owner, nome='Ataque de teste', forca=16)
        weapon = TbItemMundano.objects.create(
            nome='Espada de teste', slug='espada-de-teste', categoria='arma',
            subcategoria='arma_marcial', tags_json=['dmg:1d8(cortante)'])
        TbPersonagemItem.objects.create(
            id_personagem=character, id_item_mundano=weapon,
            nome=weapon.nome, equipado=True, tags_json=weapon.tags_json)
        talent = TbTalento.objects.create(
            nome='Talento de teste', slug='talento-implacavel-teste',
            descricao='Teste', tags_json=ATTRIBUTE_TAGS + RELENTLESS)
        owned = TbPersonagemTalento.objects.create(
            id_personagem=character, id_talento=talent,
            categoria='epico', nome=talent.nome)

        def weapon_profile():
            return next(p for p in derive(character)['ataques']['perfis']
                        if p['nome'] == weapon.nome)

        self.assertEqual(weapon_profile()['tipo_dano'], 'cortante')
        self.assertNotIn('ignora_resistencia', weapon_profile())
        self.assertNotIn('dano_critico_extra', weapon_profile())
        owned.detalhes = 'talent_attr:FOR'
        owned.save(update_fields=['detalhes'])
        self.assertTrue(weapon_profile()['ignora_resistencia'])
        self.assertEqual(weapon_profile()['nota'].count('ignora resistência'), 1)
        self.assertEqual(derive(character)['atributos']['FOR']['valor'], 18)
        self.assertEqual(weapon_profile()['dano_critico_extra'], 18)
        self.assertIn('crítico: +18 cortante', weapon_profile()['nota'])
        self.assertEqual(weapon_profile()['nota'].count('crítico:'), 1)
        character.destreza = 31
        character.save(update_fields=['destreza'])
        owned.detalhes = 'talent_attr:DES'
        owned.save(update_fields=['detalhes'])
        self.assertEqual(derive(character)['atributos']['DES']['valor'], 31)
        self.assertEqual(weapon_profile()['dano_critico_extra'], 31)
        self.assertEqual(weapon_profile()['nota'].count('crítico:'), 1)
        owned.delete()
        self.assertNotIn('ignora_resistencia', weapon_profile())
        self.assertNotIn('dano_critico_extra', weapon_profile())
        self.assertNotIn('ignora resistência', weapon_profile()['nota'])
