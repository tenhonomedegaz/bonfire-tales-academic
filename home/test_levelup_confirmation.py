"""Focused confirmation safety tests, using synthetic content only."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from home.models import (
    TbClasse, TbPersonagem, TbPersonagemClasse, TbRaca, TbTracoracial,
)
from home.test_criador import _CriadorBase


class LevelUpConfirmationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('levelup-confirm-owner')
        race = TbRaca.objects.create(nome='Confirmation race', slug='confirmation-race')
        self.feat = TbTracoracial.objects.create(
            id_raca=race, nome='Milestone choice', descricao='',
            talento_racial=True, nivel_requisito=5)
        classe = TbClasse.objects.create(nome='Confirmation class', slug='confirmation-class')
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome='Confirmation character', id_raca=race,
            nivel=4, aventuras=500)
        self.pc = TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=classe, nivel=4, principal=True)
        self.url = reverse('personagem_levelup_aplicar', args=[self.person.pk])
        self.preview_url = reverse('personagem_levelup_preview', args=[self.person.pk])
        self.actions = [
            {'tipo': 'subir_nivel', 'payload': {'classe': classe.pk}},
            {'tipo': 'talento_racial', 'payload': {'nivel': 5, 'talento': self.feat.nome}},
        ]
        self.client.force_login(self.owner)

    def post(self, actions=None, **extra):
        return self.client.post(self.url, data={
            'acoes': self.actions if actions is None else actions, **extra,
        }, content_type='application/json')

    def assert_unchanged(self):
        self.person.refresh_from_db()
        self.pc.refresh_from_db()
        self.assertEqual(self.person.nivel, 4)
        self.assertEqual(self.pc.nivel, 4)
        self.assertFalse(self.person.talentos.exists())
        self.assertFalse(self.person.revisoes_build.exists())

    def test_level_four_to_five_racial_choice_preview_and_confirmation(self):
        preview = self.client.post(self.preview_url, data={'acoes': self.actions},
                                   content_type='application/json')
        self.assertTrue(preview.json()['ready'], preview.content)
        self.assertEqual(preview.json()['preview']['nivel'], 5)
        self.assert_unchanged()
        response = self.post()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['ficha']['nivel'], 5)
        self.assertEqual(self.person.talentos.get().nome, self.feat.nome)
        self.assertEqual(self.person.revisoes_build.count(), 1)

    def test_response_failure_rolls_back_level_choices_and_history(self):
        self.client.raise_request_exception = False
        with patch('home.views._criador_preview_resumo', side_effect=RuntimeError('response failed')):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assert_unchanged()

    def test_json_serialization_failure_also_rolls_back(self):
        self.client.raise_request_exception = False
        with patch('home.views._criador_preview_resumo', return_value={'bad': object()}):
            self.assertEqual(self.post(request_id='serialization-retry').status_code, 500)
        self.assert_unchanged()
        self.assertEqual(self.post(request_id='serialization-retry').status_code, 200)

    def test_history_failure_rolls_back_the_receipt_and_batch(self):
        self.client.raise_request_exception = False
        with patch('home.character_history.register_revision', side_effect=RuntimeError('history failed')):
            self.assertEqual(self.post(request_id='history-retry').status_code, 500)
        self.assert_unchanged()
        self.assertEqual(self.post(request_id='history-retry').status_code, 200)

    def test_invalid_choice_rolls_back_everything(self):
        self.actions[-1]['payload']['talento'] = 'Not available'
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assert_unchanged()

    def test_same_request_replays_response_without_second_advance(self):
        actions = self.actions[:1]
        first = self.post(actions, request_id='confirmation-retry')
        self.assertEqual(first.status_code, 200, first.content)
        again = self.post(actions, request_id='confirmation-retry')
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(again.json(), first.json())
        self.person.refresh_from_db()
        self.assertEqual(self.person.nivel, 5)
        self.assertEqual(self.person.revisoes_build.count(), 1)

    def test_request_id_cannot_be_reused_for_different_actions(self):
        self.assertEqual(self.post(request_id='confirmation-conflict').status_code, 200)
        response = self.post(self.actions[:1], request_id='confirmation-conflict')
        self.assertEqual(response.status_code, 409)
        self.person.refresh_from_db()
        self.assertEqual(self.person.nivel, 5)

    def test_reverted_confirmation_cannot_be_replayed_or_reapplied(self):
        self.assertEqual(self.post(request_id='reverted-retry').status_code, 200)
        revision = self.person.revisoes_build.get()
        undone = self.client.post(reverse('personagem_reverter_revisao',
                                         args=[self.person.pk, revision.pk]))
        self.assertEqual(undone.status_code, 302)
        self.assertEqual(self.post(request_id='reverted-retry').status_code, 409)
        self.person.refresh_from_db()
        self.assertEqual(self.person.nivel, 4)
        self.assertFalse(self.person.talentos.exists())

    def test_old_receipt_does_not_replay_after_a_later_revision(self):
        self.assertEqual(self.post(request_id='old-confirmation').status_code, 200)
        self.assertEqual(self.post(self.actions[:1], request_id='next-confirmation').status_code, 200)
        self.assertEqual(self.post(request_id='old-confirmation').status_code, 409)
        self.person.refresh_from_db()
        self.assertEqual(self.person.nivel, 6)
        self.assertEqual(self.person.revisoes_build.count(), 2)

    def test_invalid_json_and_request_ids_are_rejected(self):
        for url in (self.url, self.preview_url):
            for raw in ('{', 'null', '{"acoes":{}}'):
                response = self.client.post(url, data=raw, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()['ok'])
        for request_id in ('', [], 'x' * 129):
            self.assertEqual(self.post(request_id=request_id).status_code, 400)
        self.assert_unchanged()

    def test_incompatible_pinned_catalog_is_not_replaced_with_live_content(self):
        from home.content_versions import create_revision, seal_ruleset
        from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
        payload = inventory_class(self.pc.id_classe_id)
        payload['collections']['home.tbclasse'][0].pop('tagline')
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.pc.id_classe_id, payload),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.pc.ruleset = ruleset
        self.pc.save(update_fields=['ruleset'])
        with self.assertRaisesMessage(ValueError, 'Incompatible class snapshot fields.'):
            self.post()
        self.assert_unchanged()
        self.assertEqual(self.pc.ruleset_id, ruleset.pk)

    def test_legacy_subclass_absent_from_pinned_catalog_is_not_silently_converted(self):
        from home.models import TbSubclasse
        from home.versioned_classes import seal_class_snapshot
        ruleset = seal_class_snapshot(self.pc.id_classe_id)
        legacy = TbSubclasse.objects.create(
            id_classe=self.pc.id_classe, nome='Preserved legacy order', slug='preserved-legacy-order')
        self.pc.ruleset = ruleset
        self.pc.id_subclasse = legacy
        self.pc.save(update_fields=['ruleset', 'id_subclasse'])
        with self.assertRaisesMessage(ValueError, 'Subclass is not part of this ruleset.'):
            self.post()
        self.assert_unchanged()
        self.assertEqual(self.pc.ruleset_id, ruleset.pk)
        self.assertEqual(self.pc.id_subclasse_id, legacy.pk)

    def test_malformed_batches_are_rejected_without_partial_writes(self):
        self.client.raise_request_exception = False
        for actions in ('bad', [None], [self.actions[0], None],
                        [{'tipo': []}], [{'tipo': 'subir_nivel', 'payload': ['bad']}],
                        [self.actions[0], self.actions[0]]):
            with self.subTest(actions=actions):
                response = self.post(actions)
                self.assertEqual(response.status_code, 400, response.content[:300])
                self.assertFalse(response.json()['ok'])
                self.assert_unchanged()

    def test_ownership_and_csrf_remain_required(self):
        other = User.objects.create_user('levelup-confirm-other')
        self.client.force_login(other)
        self.assertEqual(self.post().status_code, 404)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(self.url, data={'acoes': self.actions},
                         content_type='application/json').status_code, 403)
        self.assert_unchanged()


class LevelUpRacialFixtureTests(_CriadorBase):
    def test_real_nephilim_choice_confirms_for_unbound_legacy_class(self):
        from home.models import TbEssencia
        user = self._novo_usuario('levelup-racial-fixture')
        classe = TbClasse.objects.get(slug='cacador')
        person = TbPersonagem.objects.create(
            dono=user, nome='Legacy racial fixture', nivel=4, aventuras=500,
            id_raca=TbRaca.objects.get(slug='humano'),
            id_essencia=TbEssencia.objects.get(slug='nephilim'))
        pc = TbPersonagemClasse.objects.create(
            id_personagem=person, id_classe=classe, nivel=4, principal=True)
        feat = TbTracoracial.objects.get(id_essencia=person.id_essencia,
                                         nome='Revelação Nephilim')
        self.client.force_login(user)
        response = self.client.post(reverse('personagem_levelup_aplicar', args=[person.pk]),
            data={'acoes': [
                {'tipo': 'subir_nivel', 'payload': {'classe': classe.pk}},
                {'tipo': 'talento_racial', 'payload': {'nivel': 5, 'talento': feat.nome}},
            ]}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['ficha']['nivel'], 5)
        self.assertTrue(person.talentos.filter(nome=feat.nome, nivel=5).exists())
        pc.refresh_from_db()
        self.assertIsNone(pc.ruleset_id)
