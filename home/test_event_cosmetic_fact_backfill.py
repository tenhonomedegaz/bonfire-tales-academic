"""Historical cosmetic redemptions regain their canonical fact exactly once."""

from io import StringIO
import json
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .event_cosmetics import redeem_event_cosmetic
from .models import EventCosmeticRedemption, TbEventoConquista
from .test_event_cosmetics import setup_offer


class EventCosmeticFactBackfillTests(TestCase):
    def setUp(self):
        self.user, _, self.character, self.cosmetic, self.offer = setup_offer()
        self.old = EventCosmeticRedemption.objects.create(
            request_id=uuid4(), offer=self.offer, user=self.user,
            character=self.character, cosmetico=self.cosmetic,
            cost_braseiros=25, balance_after=15)

    def command(self, **kwargs):
        output = StringIO()
        call_command('backfill_event_cosmetic_facts', stdout=output, **kwargs)
        return json.loads(output.getvalue())

    def test_preview_apply_and_repeat_preserve_original_snapshot(self):
        self.assertEqual(self.command()['facts_missing'], 1)
        self.assertFalse(TbEventoConquista.objects.exists())
        self.assertEqual(self.command(apply=True, expected_missing=1)['facts_created'], 1)
        fact = TbEventoConquista.objects.get()
        self.assertEqual((fact.chave_origem, fact.agregado_id, fact.conta_id,
                          fact.personagem_id),
                         (f'resgate:{self.old.request_id}', self.old.pk,
                          self.user.pk, self.character.pk))
        self.assertEqual(fact.ocorrido_em, self.old.created_at)
        self.assertEqual(fact.payload_json,
                         {'offer_id': self.offer.pk, 'cosmetic_id': self.cosmetic.pk,
                          'cost_braseiros': 25})
        self.assertEqual(self.command()['facts_missing'], 0)
        self.assertEqual(self.command(apply=True, expected_missing=0)['facts_created'], 0)
        self.assertEqual(TbEventoConquista.objects.count(), 1)

    def test_apply_rejects_stale_preview_without_mutation(self):
        with self.assertRaisesRegex(CommandError, 'requires --expected-missing'):
            self.command(apply=True)
        with self.assertRaisesRegex(CommandError, 'count changed'):
            self.command(apply=True, expected_missing=0)
        self.assertFalse(TbEventoConquista.objects.exists())

    def test_conflicting_fact_aborts_without_rewriting_history(self):
        self.command(apply=True, expected_missing=1)
        fact = TbEventoConquista.objects.get()
        TbEventoConquista.objects.filter(pk=fact.pk).update(payload_json={'cost_braseiros': 0})
        with self.assertRaisesRegex(CommandError, 'Conflicting event fact'):
            self.command(apply=True, expected_missing=0)
        self.assertEqual(TbEventoConquista.objects.get(pk=fact.pk).payload_json,
                         {'cost_braseiros': 0})

    def test_new_claim_fact_is_not_recreated(self):
        self.command(apply=True, expected_missing=1)
        other, _, character, cosmetic, offer = setup_offer()
        redemption, created = redeem_event_cosmetic(
            other, offer.pk, character.pk, uuid4(), 25)
        self.assertTrue(created)
        self.assertEqual(self.command()['facts_missing'], 0)
        self.assertEqual(self.command(apply=True, expected_missing=0)['facts_created'], 0)
        self.assertEqual(TbEventoConquista.objects.filter(agregado_id=redemption.pk).count(), 1)
        self.assertEqual(TbEventoConquista.objects.count(), 2)

    def test_free_historical_claim_keeps_zero_cost_and_no_character(self):
        free = EventCosmeticRedemption.objects.create(
            request_id=uuid4(), offer=self.offer, user=self.user,
            character=None, cosmetico=self.cosmetic,
            cost_braseiros=0, balance_after=None)
        self.assertEqual(self.command()['facts_missing'], 2)
        self.assertEqual(self.command(apply=True, expected_missing=2)['facts_created'], 2)
        fact = TbEventoConquista.objects.get(agregado_id=free.pk)
        self.assertIsNone(fact.personagem_id)
        self.assertEqual(fact.payload_json['cost_braseiros'], 0)
        self.assertEqual(fact.ocorrido_em, free.created_at)
