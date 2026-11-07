"""Focused pure contracts for the generic tags of Dadiva da Velocidade."""

from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from home.character_engine import apply_tags
from home.epic_talent_catalog import (ATTRIBUTE_TAGS, VERIFIED_EFFECTS,
                                      epic_candidates)
from home.models import (TbMagia, TbOperacaoRecurso, TbPersonagem,
                         TbPersonagemTalento, TbTalento)
from home.tag_engine.combat_encounter import CombatEncounter
from home.tag_engine.library import Library
from home.tag_engine.validator import validate_tags_json
from home.views import (_innate_spell_uses_from_features,
                        _sync_magias_concedidas)


SPEED_TAGS = tuple(VERIFIED_EFFECTS["dadiva-da-velocidade"])


def state(speed=30):
    return {
        "_ctx": {"lvl": 20, "classlvl": 20, "pb": 6, "dex_mod": 0},
        "pv": {"maximo_calculado": 20},
        "ca": 10,
        "velocidade": "%g m / %d ft" % (round(speed * 0.3, 1), speed),
        "recursos": {},
    }


def feature(name="Fonte sintetica", tags=SPEED_TAGS):
    return SimpleNamespace(nome=name, tags_json=list(tags))


class EpicSpeedPassiveTests(SimpleTestCase):
    @patch("home.character_engine._cond_nomes", return_value={
        "paralisado": "Paralisado", "restringido": "Restringido"})
    def test_applies_removes_coexists_and_deduplicates_passives(self, _conditions):
        applied = apply_tags(state(), [("talento", "Fonte", feature(), None)])
        self.assertEqual(applied["velocidade"], "18 m / 60 ft")
        self.assertEqual(
            {row["slug"] for row in applied["imunidades_condicao"]},
            {"paralisado", "restringido"})

        removed = apply_tags(state(), [])
        self.assertEqual(removed["velocidade"], "9 m / 30 ft")
        self.assertEqual(removed["imunidades_condicao"], [])

        coexists = apply_tags(state(), [
            ("talento", "Fonte", feature(), None),
            ("origem", "Outra", feature("Outra", ("speed:+10", "cond_immune:agarrado")), None),
        ])
        self.assertEqual(coexists["velocidade"], "21 m / 70 ft")
        self.assertEqual(
            {row["slug"] for row in coexists["imunidades_condicao"]},
            {"agarrado", "paralisado", "restringido"})

        duplicate = apply_tags(state(), [
            ("talento", "Fonte", feature(tags=SPEED_TAGS * 2), None)])
        self.assertEqual(duplicate["velocidade"], "18 m / 60 ft")
        self.assertEqual(
            {row["slug"] for row in duplicate["imunidades_condicao"]},
            {"paralisado", "restringido"})


class EpicSpeedInnateSpellTests(SimpleTestCase):
    def test_compiles_slotless_componentless_short_or_long_haste_once(self):
        uses = _innate_spell_uses_from_features(
            [("talento", "Fonte", feature(), None)], {"velocidade"}, state())
        meta = uses[("Fonte sintetica", "velocidade")]
        self.assertEqual(meta["maximo"], 1)
        self.assertEqual(meta["reset"], "short_or_long")
        self.assertEqual(meta["label"], "1/rest")
        self.assertTrue(meta["without_slot"])
        self.assertTrue(meta["without_components"])
        self.assertTrue(meta["without_lethargy"])

    def test_spell_contract_is_idempotent_and_source_scoped(self):
        duplicate = _innate_spell_uses_from_features(
            [("talento", "Fonte", feature(tags=SPEED_TAGS * 2), None)],
            {"velocidade"}, state())
        self.assertEqual(len(duplicate), 1)

        coexists = _innate_spell_uses_from_features([
            ("talento", "Fonte", feature(), None),
            ("origem", "Outra", feature("Outra", (
                "cast{spell:velocidade, uses{1, reset:long_rest}, without{slot}}",)), None),
        ], {"velocidade"}, state())
        self.assertEqual(coexists[("Fonte sintetica", "velocidade")]["reset"], "short_or_long")
        self.assertEqual(coexists[("Outra", "velocidade")]["reset"], "long_rest")


class EpicSpeedEscapeTests(SimpleTestCase):
    @staticmethod
    def encounter(tags=SPEED_TAGS):
        encounter = CombatEncounter([
            {'id': 'runner', 'team': 'allies', 'max_hp': 30,
             'defensive_tags': tags},
            {'id': 'enemy', 'team': 'enemies', 'max_hp': 30},
        ])
        encounter.conditions.resolve(
            ['instant{trigger=hit, '
             'apply:agarrado(duration:until_source_turn_start)}'],
            event='hit', source='enemy', target='runner')
        encounter.start_turn('runner', 'runner-1')
        return encounter

    def test_escape_tag_is_valid_and_spends_movement_without_action(self):
        self.assertEqual(validate_tags_json(SPEED_TAGS, Library()), [])
        candidate = next(row for row in epic_candidates()
                         if row['slug'] == 'dadiva-da-velocidade')
        self.assertEqual(candidate['tags_json'], ATTRIBUTE_TAGS + list(SPEED_TAGS))
        self.assertIn('Movimento sem Amarras', candidate['descricao'])
        encounter = self.encounter()
        self.assertEqual(encounter.escape_condition('agarrado', 'enemy', 30), 25)
        self.assertEqual(encounter.conditions.facts('runner', 'enemy'), {})
        self.assertFalse(encounter.action_used)
        self.assertEqual(encounter.events[-1],
                         ('escape', 'runner', 'enemy', 'agarrado', 5, 25))
        with self.assertRaises(ValueError):
            encounter.escape_condition('agarrado', 'enemy', 25)

    def test_requires_source_condition_turn_and_movement(self):
        without_source = self.encounter(tags=())
        with self.assertRaises(ValueError):
            without_source.escape_condition('agarrado', 'enemy', 30)
        self.assertIn('agarrado', without_source.conditions.facts('runner', 'enemy'))

        encounter = self.encounter()
        with self.assertRaises(ValueError):
            encounter.escape_condition('agarrado', 'enemy', 4)
        self.assertIn('agarrado', encounter.conditions.facts('runner', 'enemy'))
        with self.assertRaises(ValueError):
            encounter.escape_condition('paralisado', 'enemy', 30)
        encounter.end_turn()
        with self.assertRaises(ValueError):
            encounter.escape_condition('agarrado', 'enemy', 30)

    def test_multiple_grapplers_and_other_escape_source(self):
        tags = SPEED_TAGS + SPEED_TAGS + (
            'escape{action:move, condition:agarrado, cost:10ft}',)
        encounter = self.encounter(tags=tags)
        encounter.conditions.resolve(
            ['instant{trigger=hit, '
             'apply:agarrado(duration:until_source_turn_start)}'],
            event='hit', source='enemy-two', target='runner')
        self.assertEqual(encounter.escape_condition('agarrado', 'enemy', 5), 0)
        self.assertEqual(encounter.conditions.facts('runner', 'enemy'),
                         {'agarrado': {'other'}})
        self.assertEqual(encounter.conditions.facts('runner', 'enemy-two'),
                         {'agarrado': {'self'}})
        with self.assertRaises(ValueError):
            encounter.escape_condition('agarrado', 'enemy-two', 0)
        self.assertEqual(encounter.escape_condition('agarrado', 'enemy-two', 5), 0)
        self.assertEqual(encounter.conditions.facts('runner', 'enemy-two'), {})
        self.assertEqual(sum(event[0] == 'escape' for event in encounter.events), 2)


class EpicSpeedSheetCastTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username='epic-speed-owner')
        self.character = TbPersonagem.objects.create(dono=owner, nome='Velocista')
        self.spell = TbMagia.objects.create(
            nome='Velocidade', nome_ingles='Haste', slug='velocidade',
            nivel=3, componentes='V, S, M', concentracao=True)
        self.talent = TbTalento.objects.create(
            nome='Fonte epica sintetica', slug='fonte-epica-velocidade-teste',
            tipo='geral', etiqueta='combate', etiquetas_adicionais='epico',
            descricao='Fonte de teste.', tags_json=ATTRIBUTE_TAGS + list(SPEED_TAGS))
        self.owned = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=self.talent,
            categoria='epico', nome=self.talent.nome, detalhes='talent_attr:DES')
        _sync_magias_concedidas(self.character)
        self.owned_spell = self.character.magias.get(id_magia=self.spell)
        self.url = reverse('personagem_usar_magia_inata', args=[
            self.character.pk, self.owned_spell.pk])
        self.client.force_login(owner)

    def test_haste_cast_receipt_and_short_rest(self):
        from home.resource_engine import reset_resources

        operation_id = str(uuid.uuid4())
        response = self.client.post(self.url, {'operation_id': operation_id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sem letargia ao terminar.')
        receipt = TbOperacaoRecurso.objects.get(operation_id=operation_id)
        self.assertEqual(receipt.resposta['remaining'], 0)
        self.assertTrue(receipt.resposta['without_slot'])
        self.assertTrue(receipt.resposta['without_components'])
        self.assertTrue(receipt.resposta['without_lethargy'])
        state = self.character.estados.get(chave=f'spell:{self.owned_spell.pk}')
        self.assertTrue(state.ativo)
        self.assertTrue(state.payload_json['concentration'])
        self.assertTrue(state.payload_json['innate'])
        self.assertEqual(self.client.post(self.url, {
            'operation_id': operation_id}).status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.filter(
            operation_id=operation_id).count(), 1)
        state.refresh_from_db()
        self.assertTrue(state.ativo)
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 400)
        reset_resources(self.character, 'short_rest')
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 302)

    def test_concentrating_innate_replaces_prior_and_ends_on_condition(self):
        from home.resource_engine import activate_state

        activate_state(self.character, 'spell:prior', origin='magia:prior',
                       payload={'concentration': True})
        activate_state(self.character, 'spell:other', origin='magia:other',
                       payload={'concentration': False})
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 302)
        self.assertFalse(self.character.estados.get(chave='spell:prior').ativo)
        self.assertTrue(self.character.estados.get(chave='spell:other').ativo)
        self.assertTrue(self.character.estados.get(
            chave=f'spell:{self.owned_spell.pk}').ativo)
        event_url = reverse('oficina_evento_concentracao', args=[self.character.pk])
        self.assertEqual(self.client.post(event_url, {
            'operation_id': str(uuid.uuid4()), 'event': 'unconscious'
        }).status_code, 302)
        self.assertFalse(self.character.estados.get(
            chave=f'spell:{self.owned_spell.pk}').ativo)
        self.assertTrue(self.character.estados.get(chave='spell:other').ativo)

    @patch('home.hunter_mutagens.concentration_blocked', return_value=True)
    def test_blocked_concentration_does_not_spend_innate_use(self, _blocked):
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 400)
        self.assertFalse(self.character.estados.filter(ativo=True).exists())
        self.assertFalse(TbOperacaoRecurso.objects.exists())

    def test_choice_source_and_owner_gate(self):
        other = get_user_model().objects.create_user(username='epic-speed-other')
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 404)
        self.client.force_login(self.character.dono)
        self.owned.detalhes = ''
        self.owned.save(update_fields=['detalhes'])
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 400)
        self.owned.delete()
        self.assertEqual(self.client.post(self.url, {
            'operation_id': str(uuid.uuid4())}).status_code, 400)
