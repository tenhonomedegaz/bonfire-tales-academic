import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .test_hunter_spells import HunterSpellGrantTests as Fixtures
from .models import TbOperacaoRecurso
from .hunter_preparation import preparation
from .hunter_resources import state, use_secret


class HunterResourceFlowTests(TestCase):
    setUp = Fixtures.setUp
    bind = Fixtures.bind

    def test_exclusive_secrets_require_their_own_flow_without_generic_spending(self):
        for secret, message in (
                ('despertar-final', 'painel da Forma Desperta'),
                ('santuario-do-veu', 'painel da Lanterna do Véu'),
                ('forma-quimerica', 'painel de mutagênicos'),
                ('caminho-final', 'nenhum ponto foi gasto')):
            with self.assertRaisesMessage(ValueError, message):
                use_secret(character_id=self.person.pk, owner_id=self.user.pk,
                    secret_id=secret, enhanced=False, operation_id=str(uuid.uuid4()),
                    expected_version='unused')
        self.assertEqual(self.person.recursos.count(), 0)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 0)

    def command(self, secret='granada-de-luz', enhanced=False):
        return {'action': 'use', 'secret': secret, 'enhanced': '1' if enhanced else '0',
                'operation_id': str(uuid.uuid4()),
                'resource_version': state(self.profile, preparation(self.profile))['version']}

    def test_use_upgrade_replay_and_limits(self):
        self.assertEqual(self.person.recursos.count(), 0)
        self.assertContains(self.client.get(self.url), 'Registrar uso')
        self.assertEqual(self.person.recursos.count(), 0)
        command = self.command(enhanced=True)
        self.assertEqual(self.client.post(self.url, command).status_code, 302)
        resource = self.person.recursos.get()
        self.assertEqual((resource.atual, resource.maximo, resource.reset), (1, 3, 'long_rest'))
        self.assertEqual(self.client.post(self.url, command).status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        self.assertEqual(self.client.post(self.url, dict(command, enhanced='0')).status_code, 400)
        self.assertEqual(self.client.post(self.url, self.command(enhanced=True)).status_code, 400)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 1)
        self.assertEqual(self.client.post(self.url, self.command()).status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 0)
        self.assertEqual(self.client.post(self.url, self.command()).status_code, 400)

    def test_stale_preparation_and_unprepared_secret_rejected(self):
        stale = self.command()
        self.client.post(self.url, {'version': 0, 'secret': ['sinal-veritas']})
        self.profile.refresh_from_db()
        self.assertEqual(self.client.post(self.url, stale).status_code, 400)
        self.assertEqual(self.client.post(self.url, self.command('sinal-exitium')).status_code, 400)
        self.assertEqual(self.person.recursos.count(), 0)
        self.assertEqual(self.client.post(self.url, self.command('sinal-veritas')).status_code, 302)

    def test_long_rest_recovers_short_rest_does_not_and_replay_stays_free(self):
        command = self.command(enhanced=True)
        self.client.post(self.url, command)
        url = reverse('personagem_descansar', args=[self.person.pk])
        self.assertEqual(self.client.post(url, {'tipo': 'curto'}).status_code, 302)
        resource = self.person.recursos.get(chave__startswith='hunter:')
        self.assertEqual(resource.atual, 1)
        self.assertEqual(self.client.post(url, {'tipo': 'longo'}).status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 3)
        self.assertEqual(self.client.post(self.url, command).status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 3)

    def test_level_growth_preserves_spent_points_and_receipt_failure_rolls_back(self):
        self.client.post(self.url, self.command())
        self.pc.nivel = 5
        self.pc.save()
        self.profile.refresh_from_db()
        self.assertEqual(state(self.profile, preparation(self.profile))['current'], 4)
        with patch('home.hunter_resources.TbOperacaoRecurso.objects.create', side_effect=RuntimeError('receipt')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.command())
        resource = self.person.recursos.get()
        self.assertEqual((resource.atual, resource.maximo), (2, 3))

    def test_owner_and_operation_validation(self):
        command = self.command()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, command).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, dict(command, operation_id='bad')).status_code, 400)
        self.assertEqual(self.person.recursos.count(), 0)
