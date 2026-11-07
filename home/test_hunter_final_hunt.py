import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .hunter_catalog import compose_order_revision
from .hunter_mark import command, panel
from .hunter_preparation import preparation
from .hunter_resources import contract, use_secret
from .models import TbOperacaoRecurso
from .test_hunter_mark import HunterMarkTests


class HunterFinalHuntTests(TestCase):
    def setUp(self):
        HunterMarkTests.setUp(self)
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        import json
        order_ids = json.loads(output.getvalue())['order_ids']
        self.pc.id_subclasse_id = order_ids['ordem-dos-exterminadores']
        self.pc.nivel = 18
        self.pc.save(update_fields=['id_subclasse', 'nivel'])
        self.composed = compose_order_revision(self.new, class_id=self.cl.pk,
                                               order_ids=order_ids)
        self.profile.ruleset = self.composed
        self.profile.save(update_fields=['ruleset'])

    def use_mark(self, **changes):
        self.profile.refresh_from_db()
        payload = dict(character_id=self.person.pk, owner_id=self.user.pk,
            operation_id=uuid.uuid4(), expected_version=self.profile.version,
            action='apply', target='Dragão', confirmed=True, final_hunt=True)
        payload.update(changes)
        return command(**payload)

    def test_final_hunt_spends_once_expires_and_keeps_ordinary_mark(self):
        self.assertTrue(panel(self.profile)['final_hunt_eligible'])
        self.assertContains(self.client.get(self.url), 'Declarar Caçada Final')
        operation = uuid.uuid4()
        first = self.use_mark(operation_id=operation)
        self.assertEqual(first['final_hunt_remaining_seconds'], 60)
        self.assertEqual(self.use_mark(operation_id=operation, expected_version=0), first)
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual, 14)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['damage'], '2d12')
        sheet = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(sheet, 'Caçada Final ativa')
        command(character_id=self.person.pk, owner_id=self.user.pk,
            operation_id=uuid.uuid4(), expected_version=self.profile.version,
            action='elapsed', seconds=60, confirmed=True)
        self.profile.refresh_from_db()
        self.assertEqual((panel(self.profile)['damage'], self.profile.mark['active']),
                         ('1d12', True))
        self.assertEqual(self.profile.mark['remaining_seconds'], 3540)

    def test_rejects_invalid_context_balance_and_rollback(self):
        old = self.new
        self.profile.ruleset = old
        self.profile.save(update_fields=['ruleset'])
        with self.assertRaises(ValueError):
            self.use_mark()
        self.profile.ruleset = self.composed
        self.profile.save(update_fields=['ruleset'])
        prepared = preparation(self.profile)
        spec = contract(self.profile, prepared)
        with self.assertRaises(ValueError):
            use_secret(character_id=self.person.pk, owner_id=self.user.pk,
                secret_id='cacada-final', enhanced=False, operation_id=uuid.uuid4(),
                expected_version='ignored')
        with patch('home.hunter_mark.TbOperacaoRecurso.objects.create',
                   side_effect=RuntimeError('receipt')):
            with self.assertRaises(RuntimeError):
                self.use_mark()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark, {})
        self.assertFalse(self.person.recursos.exists())
        from .resource_engine import spend_resource
        spend_resource(self.person, spec, 17)
        with self.assertRaises(ValueError):
            self.use_mark()
        self.assertEqual(self.person.recursos.get(chave=spec['key']).atual, 1)
        self.assertFalse(TbOperacaoRecurso.objects.exists())

    def test_form_applies_only_to_eligible_owner_and_cannot_transfer_effect(self):
        self.client.force_login(self.user)
        form = dict(action='mark', mark_event='apply', target='Primeira presa',
            final_hunt='1', confirmed='1', operation_id=str(uuid.uuid4()), version=0)
        self.pc.nivel = 17
        self.pc.save(update_fields=['nivel'])
        self.assertEqual(self.client.post(self.url, form).status_code, 400)
        self.assertFalse(self.person.recursos.exists())
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.assertEqual(self.client.post(self.url, form).status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mark['final_hunt'])
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual, 14)
        ordinary = dict(form, target='Segunda presa', final_hunt='',
            operation_id=str(uuid.uuid4()), version=self.profile.version)
        self.assertEqual(self.client.post(self.url, ordinary).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['target'], 'Segunda presa')
        self.assertFalse(self.profile.mark['final_hunt'])
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual, 14)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, form).status_code, 404)
