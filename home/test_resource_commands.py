import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from home.models import TbOperacaoRecurso, TbPersonagem, TbPersonagemRecurso
from home.resource_commands import execute_slot_command, _current_slot
from home.resource_engine import ensure_resource, mutate_resource, reset_resources, spend_resource


CONTRACT = {'key': 'spell-slot:1', 'legacy_name': 'spell-slot:1',
            'name': 'spell-slot:1', 'maximum': 2, 'reset': 'long_rest'}


class CommandSetup:
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='slot-owner')
        self.character = TbPersonagem.objects.create(dono=self.user, nome='Conjurador')
        self.url = reverse('personagem_usar_slot_magia', args=[self.character.pk])
        self.client.force_login(self.user)

    def version(self):
        return _current_slot(self.character, 1, 2)['version']

    def command(self, operation_id=None, expected_version=None, **changes):
        data = dict(user_id=self.user.pk, level=1, action='gastar',
                    operation_id=operation_id or uuid.uuid4(),
                    expected_version=expected_version or self.version(), total_factory=lambda: 2)
        data.update(changes)
        return execute_slot_command(self.character, **data)


class ResourceCommandTests(CommandSetup, TestCase):
    def test_repeated_operation_spends_once_even_after_other_commands(self):
        operation, initial = uuid.uuid4(), self.version()
        first, status = self.command(operation, initial)
        self.assertEqual(status, 200)
        self.assertEqual(first['slot']['atual'], 1)
        self.command(action='desfazer')
        replay, status = self.command(operation, initial)
        self.assertEqual(status, 200)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['slot']['atual'], 2)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 2)

    def test_changed_payload_cannot_reuse_an_operation(self):
        operation, initial = uuid.uuid4(), self.version()
        self.command(operation, initial)
        error, status = self.command(operation, initial, action='desfazer')
        self.assertEqual((status, error['code']), (409, 'operation_conflict'))
        self.assertEqual(error['slot']['atual'], 1)

    def test_stale_tab_receives_current_state_without_spending(self):
        initial = self.version()
        self.command(expected_version=initial)
        error, status = self.command(expected_version=initial)
        self.assertEqual((status, error['code']), (409, 'stale_version'))
        self.assertEqual(error['slot']['atual'], 1)

    def test_rest_prevents_aba_and_replay_does_not_spend_again(self):
        self.command()
        before_rest = self.version()
        reset_resources(self.character, 'long_rest')
        mutate_resource(self.character, CONTRACT, -1)
        self.assertEqual(_current_slot(self.character, 1, 2)['atual'], 1)
        self.assertNotEqual(self.version(), before_rest)
        error, status = self.command(expected_version=before_rest)
        self.assertEqual(status, 409)

    def test_limits_and_invalid_input_never_change_counter(self):
        for action in ['desfazer', 'bogus']:
            result, status = self.command(action=action)
            self.assertIn(status, [400, 409])
        self.command()
        self.command()
        result, status = self.command()
        self.assertEqual((status, result['slot']['atual']), (409, 0))
        self.assertEqual(self.command(operation_id='invalid')[1], 400)
        self.assertEqual(self.command(level=0)[1], 400)
        self.assertEqual(self.command(expected_version='bad')[1], 400)

    def test_receipt_failure_rolls_back_spend(self):
        initial = self.version()
        with patch.object(TbOperacaoRecurso.objects, 'create', side_effect=RuntimeError('storage')):
            with self.assertRaises(RuntimeError):
                self.command()
        self.assertEqual(self.version(), initial)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 0)
        self.assertEqual(TbPersonagemRecurso.objects.count(), 0)

    def test_sync_preserves_version_and_spending_updates_it(self):
        ensure_resource(self.character, CONTRACT)
        initial = self.version()
        ensure_resource(self.character, CONTRACT)
        self.assertEqual(initial, self.version())
        spend_resource(self.character, CONTRACT)
        self.assertNotEqual(initial, self.version())

    def test_legacy_counter_is_preserved_on_first_command(self):
        legacy = TbPersonagemRecurso.objects.create(
            id_personagem=self.character, nome='spell-slot:1', atual=1, maximo=2)
        response, status = self.command()
        self.assertEqual((status, response['slot']['atual']), (200, 0))
        self.assertEqual(TbPersonagemRecurso.objects.get().pk, legacy.pk)

    def test_changed_capacity_projects_spent_slots_before_the_next_command(self):
        from home.views import _spell_slot_rows

        resource = ensure_resource(self.character, CONTRACT)
        mutate_resource(self.character, CONTRACT, -1)
        old_version = self.version()
        # Um slot já gasto: subir o teto de 2 para 3 deixa 2 disponíveis.
        before = _spell_slot_rows(self.character, {1: 3})[0]
        self.assertEqual(before['atual'], 2)
        resource.refresh_from_db()
        self.assertEqual((resource.atual, resource.maximo), (1, 2),
                         'Projetar a ficha não pode sincronizar o banco.')
        stale, status = self.command(expected_version=old_version, total_factory=lambda: 3)
        self.assertEqual((status, stale['slot']['atual']), (409, 2))
        result, status = self.command(expected_version=before['version'], total_factory=lambda: 3)
        self.assertEqual((status, result['slot']['atual']), (200, 1))
        resource.refresh_from_db()
        self.assertEqual((resource.atual, resource.maximo), (1, 3))

    def test_reduced_capacity_cannot_spend_a_slot_already_consumed(self):
        ensure_resource(self.character, dict(CONTRACT, maximum=3))
        mutate_resource(self.character, dict(CONTRACT, maximum=3), -2)
        snapshot = _current_slot(self.character, 1, 2)
        self.assertEqual(snapshot['atual'], 0)
        result, status = self.command(expected_version=snapshot['version'])
        self.assertEqual((status, result['code'], result['slot']['atual']),
                         (409, 'slot_limit', 0))
        result, status = self.command(action='desfazer')
        self.assertEqual((status, result['slot']['atual']), (200, 1))

    def test_display_uses_canonical_resource_even_if_its_name_changes(self):
        from home.views import _spell_slot_rows

        resource = ensure_resource(self.character, CONTRACT)
        mutate_resource(self.character, CONTRACT, -1)
        resource.nome = 'Espaços do primeiro círculo'
        resource.save(update_fields=['nome'])
        row = _spell_slot_rows(self.character, {1: 2})[0]
        self.assertEqual(row['atual'], 1)
        self.assertEqual(row['version'], self.version())

    def post(self, **changes):
        data = dict(nivel='1', acao='gastar', operation_id=str(uuid.uuid4()),
                    expected_version=self.version())
        data.update(changes)
        with patch('home.character_engine.derive', return_value={}), patch(
                'home.views._magias_sheet_info', return_value={'slots': [{'nivel': 1, 'total': 2}]}):
            return self.client.post(self.url, data, HTTP_ACCEPT='application/json')

    def test_owner_staff_other_and_visitor_permissions(self):
        self.assertEqual(self.post().status_code, 200)
        other = get_user_model().objects.create_user(username='slot-other')
        self.client.force_login(other)
        self.assertEqual(self.post().status_code, 404)
        other.is_staff = True
        other.save(update_fields=['is_staff'])
        self.assertEqual(self.post().status_code, 200)
        self.client.logout()
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 2)

    def test_html_fallback_redirect_is_internal_and_keeps_tab(self):
        with patch('home.character_engine.derive', return_value={}), patch(
                'home.views._magias_sheet_info', return_value={'slots': [{'nivel': 1, 'total': 2}]}):
            response = self.client.post(self.url, {'nivel': 1, 'next': 'https://outside.test/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('ficha_detail', args=[self.character.pk]) + '?aba=magias')

    def test_old_html_form_requires_refresh_without_spending(self):
        for data in ({'nivel': 1}, {'nivel': 1, 'operation_id': str(uuid.uuid4())},
                     {'nivel': 1, 'expected_version': self.version()}):
            with self.subTest(fields=list(data)):
                with patch('home.character_engine.derive', return_value={}), patch(
                        'home.views._magias_sheet_info', return_value={
                            'slots': [{'nivel': 1, 'total': 2}]}):
                    response = self.client.post(self.url, data)
                self.assertRedirects(response, reverse('ficha_detail',
                                     args=[self.character.pk]) + '?aba=magias',
                                     fetch_redirect_response=False)
                self.assertTrue(any('Atualize a ficha' in str(message) for message in
                                    response.wsgi_request._messages))
                self.assertEqual(TbOperacaoRecurso.objects.count(), 0)
                self.assertEqual(TbPersonagemRecurso.objects.count(), 0)

    @override_settings(SPELL_SLOT_PARTIAL_ENABLED=False)
    def test_html_form_keeps_concurrency_and_replay_protection_with_fetch_disabled(self):
        data = dict(nivel='1', acao='gastar', operation_id=str(uuid.uuid4()),
                    expected_version=self.version())
        with patch('home.character_engine.derive', return_value={}), patch(
                'home.views._magias_sheet_info', return_value={'slots': [{'nivel': 1, 'total': 2}]}):
            for _ in range(2):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse('ficha_detail', args=[self.character.pk]) + '?aba=magias')
            self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
            data['operation_id'] = str(uuid.uuid4())
            conflict = self.client.post(self.url, data)
        self.assertEqual(TbPersonagemRecurso.objects.get().atual, 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 2)
        self.assertTrue(any('mudaram' in str(message) for message in
                            conflict.wsgi_request._messages))

    @override_settings(SPELL_SLOT_PARTIAL_ENABLED=False)
    def test_feature_switch_keeps_data_and_refuses_ajax_mutation(self):
        self.command()
        version = self.version()
        self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.version(), version)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)

    def test_csrf_is_required(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {'nivel': 1}, HTTP_ACCEPT='application/json').status_code, 403)

    def test_build_restore_keeps_receipt_and_replaces_version(self):
        from home.character_history import capture_build, restore_build
        ensure_resource(self.character, CONTRACT)
        snapshot = capture_build(self.character)
        operation, initial = uuid.uuid4(), self.version()
        self.command(operation, initial)
        restore_build(self.character, snapshot)
        self.assertNotEqual(self.version(), initial)
        response, status = self.command(operation, initial)
        self.assertEqual(status, 200)
        self.assertTrue(response['replayed'])
        self.assertEqual(response['slot']['atual'], 2)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)


class ConcurrentResourceCommandTests(CommandSetup, TransactionTestCase):
    def race(self, same_operation):
        version, operation = self.version(), uuid.uuid4()
        barrier = Barrier(2)
        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.command(operation if same_operation else uuid.uuid4(), version)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, range(2)))

    def test_simultaneous_duplicate_is_applied_once(self):
        results = self.race(True)
        self.assertEqual([status for _, status in results], [200, 200])
        self.assertEqual(sum(response['replayed'] for response, _ in results), 1)
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        self.assertEqual(TbPersonagemRecurso.objects.get().atual, 1)

    def test_two_tabs_on_same_version_have_one_conflict(self):
        results = self.race(False)
        self.assertEqual(sorted(status for _, status in results), [200, 409])
        self.assertEqual(TbPersonagemRecurso.objects.get().atual, 1)
