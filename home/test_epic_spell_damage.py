"""Focused coverage for tagged spell damage die minimum."""

import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from home.epic_spell_damage import (
    SPELL_DIE_FLOOR_TAG, damage_spell_options, parse_damage_dice,
    resolve_spell_damage,
)
from home.epic_talent_catalog import ATTRIBUTE_TAGS, epic_candidates
from home.models import (
    TbMagia, TbOperacaoRecurso, TbPersonagem, TbPersonagemMagia,
    TbPersonagemTalento, TbTalento,
)
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


class SpellDamageTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.owner = get_user_model().objects.create_user(username=f"spell-{uuid.uuid4()}")
        self.other = get_user_model().objects.create_user(username=f"other-{uuid.uuid4()}")
        self.person = TbPersonagem.objects.create(dono=self.owner, nome="Conjurador")
        source = TbTalento.objects.create(
            nome="Fonte sintética", slug=f"spell-floor-{uuid.uuid4()}",
            tipo="geral", tags_json=ATTRIBUTE_TAGS + [SPELL_DIE_FLOOR_TAG])
        self.owned_talent = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=source,
            nome=source.nome, detalhes="talent_attr:INT")
        spell = TbMagia.objects.create(
            nome="Chama de teste", slug=f"test-fire-{uuid.uuid4()}",
            nivel=2, tags_json=["dmg:2d6(fogo)"])
        self.owned_spell = TbPersonagemMagia.objects.create(
            id_personagem=self.person, id_magia=spell,
            nome=spell.nome, nivel=2, preparada=True)

    def resolve(self, **changes):
        values = {"operation_id": uuid.uuid4(),
                  "owned_spell_id": self.owned_spell.pk,
                  "damage_type": "fogo", "dice": [(6, 1), (6, 2), (6, 5)],
                  "fixed": 4}
        values.update(changes)
        return resolve_spell_damage(self.person, **values)

    def test_complete_candidate_exposes_both_spell_effects(self):
        diagnostics = validate_tags_json([SPELL_DIE_FLOOR_TAG], Library())
        self.assertFalse([d for d in diagnostics if d.level == ERROR])
        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-do-conjurador-de-combate")
        from home.epic_concentration import FOCUS_TAG
        self.assertIn(SPELL_DIE_FLOOR_TAG, candidate["tags_json"])
        self.assertIn(FOCUS_TAG, candidate["tags_json"])
        self.assertFalse([d for d in validate_tags_json(
            candidate["tags_json"], Library()) if d.level == ERROR])

    def test_real_candidate_drives_damage_and_concentration(self):
        from home.epic_concentration import resolve_concentration_event
        from home.resource_engine import activate_state
        from home.tag_engine.combat_encounter import CombatEncounter

        candidate = next(row for row in epic_candidates()
                         if row["slug"] == "dadiva-do-conjurador-de-combate")
        source = TbTalento.objects.create(**candidate)
        self.owned_talent.id_talento = source
        self.owned_talent.nome = source.nome
        self.owned_talent.save(update_fields=["id_talento", "nome"])
        self.assertEqual(self.resolve()["applied_dice"], [3, 3, 5])
        activate_state(self.person, "spell:real", origin="magia:real",
                       payload={"concentration": True})
        self.assertEqual(resolve_concentration_event(
            self.person, operation_id=uuid.uuid4(), event="damage")['outcome'],
            "retained")
        game = CombatEncounter([
            {'id': 'caster', 'team': 'allies', 'max_hp': 30,
             'concentration': 'spell:real',
             'defensive_tags': candidate['tags_json']},
            {'id': 'foe', 'team': 'enemies', 'max_hp': 30},
        ])
        game.start_turn('foe', 'turn-1')
        game.attack('caster', (), hit=True, damage=4)
        self.assertEqual(game.concentration_state('caster'), {
            'source': 'spell:real', 'save_required': False})
        self.owned_talent.delete()
        self.assertEqual(damage_spell_options(self.person), [])
        self.assertEqual(resolve_concentration_event(
            self.person, operation_id=uuid.uuid4(), event="damage")['outcome'],
            "save_required")

    def test_damage_floor_preserves_other_rolls_fixed_and_receipt(self):
        self.assertEqual(len(damage_spell_options(self.person)), 1)
        operation = uuid.uuid4()
        result = self.resolve(operation_id=operation)
        self.assertEqual(result["original_dice"], [1, 2, 5])
        self.assertEqual(result["applied_dice"], [3, 3, 5])
        self.assertEqual(result["total"], 15)
        self.assertTrue(self.resolve(operation_id=operation)["replayed"])
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        with self.assertRaises(ValueError):
            self.resolve(operation_id=operation, fixed=5)
        self.assertEqual(parse_damage_dice("6:1, 6:2, 6:5"),
                         [(6, 1), (6, 2), (6, 5)])

    def test_source_spell_and_owner_gates(self):
        self.owned_spell.preparada = False
        self.owned_spell.save(update_fields=["preparada"])
        with self.assertRaises(ValueError):
            self.resolve()
        self.owned_spell.preparada = True
        self.owned_spell.save(update_fields=["preparada"])
        with self.assertRaises(ValueError):
            self.resolve(damage_type="frio")
        with self.assertRaises(ValueError):
            self.resolve(fixed=-100)
        self.owned_spell.id_magia.nivel = 0
        self.owned_spell.id_magia.save(update_fields=["nivel"])
        with self.assertRaises(ValueError):
            self.resolve()
        self.owned_spell.id_magia.nivel = 2
        self.owned_spell.id_magia.save(update_fields=["nivel"])
        self.owned_talent.detalhes = ""
        self.owned_talent.save(update_fields=["detalhes"])
        self.assertEqual(damage_spell_options(self.person), [])
        with self.assertRaises(ValueError):
            self.resolve()
        self.owned_talent.detalhes = "talent_attr:INT"
        self.owned_talent.save(update_fields=["detalhes"])
        url = reverse("personagem_resolver_dano_magia", args=[self.person.pk])
        form = {"operation_id": str(uuid.uuid4()),
                "owned_spell_id": self.owned_spell.pk,
                "damage_type": "fogo", "dice": "6:1,6:2", "fixed": 4}
        self.client.force_login(self.other)
        self.assertNotEqual(self.client.post(url, form).status_code, 302)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("ficha_detail", args=[self.person.pk])),
                            url)
        self.assertEqual(self.client.post(url, form).status_code, 302)
        self.owned_talent.delete()
        self.assertEqual(damage_spell_options(self.person), [])
        with self.assertRaises(ValueError):
            self.resolve()
