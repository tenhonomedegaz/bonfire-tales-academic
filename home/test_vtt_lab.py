"""Private laboratory contracts. Run ``py -m home.test_vtt_lab --isolated``.

The standalone runner never imports bonfire.settings or project URLs and only
creates selected tables and the new migration in SQLite memory.
"""

import sys

if __name__ == '__main__' and '--isolated' in sys.argv:
    from django.conf import settings
    settings.configure(
        SECRET_KEY='isolated-vtt-lab-tests', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'], VTT_LAB_ENABLED=True,
        SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
        MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware',
                    'django.contrib.auth.middleware.AuthenticationMiddleware'],
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], STATIC_URL='/static/',
        TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True}],
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    import django
    django.setup()

import ast
import hashlib
import importlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch
from uuid import uuid4

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, connection, migrations, transaction
from django.db.migrations.state import ProjectState
from django.db.models.query import QuerySet
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path, reverse

from home import vtt_lab as lab
from home.models import (TbAntecedente, TbEssencia, TbLinhagem, TbPersonagem, TbRaca, UserProfile)
from home.vtt_lab_models import VttLabReceipt, VttLabSession, initial_lab_state


urlpatterns = [
    path('vtt/laboratorio/', lab.laboratory, name='vtt_lab'),
    path('vtt/laboratorio/api/sessoes/', lab.sessions, name='vtt_lab_sessions'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/', lab.session_snapshot, name='vtt_lab_session'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/medir/', lab.measure, name='vtt_lab_measure'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/caminho/', lab.movement_preview, name='vtt_lab_movement_preview'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/comandos/', lab.commands, name='vtt_lab_commands'),
]


def export_fixture(character):
    return {'versao_contrato': 1, 'versao_menor': 1,
            'personagem': {'pk': character.pk, 'nome': character.nome, 'nivel_total': character.nivel},
            'derive': {'pv_max': character.pv_maximo,
                       'movimento': {'schema': 1, 'unit': 'ft', 'speeds': {'walk': 30}, 'warnings': []}},
            'estado_mesa': {'pv_atual': character.pv_maximo, 'pv_temp': 0, 'morte_s': 0, 'morte_f': 0},
            'moedas': {'pc_total': character.carteira_pc}, 'habilidades': [], 'magias': [], 'avisos': []}


@override_settings(ROOT_URLCONF=__name__, VTT_LAB_ENABLED=True, ALLOWED_HOSTS=['testserver'])
class VttLabTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user('lab-admin', is_active=True, is_superuser=True, is_staff=True)
        cls.other_admin = User.objects.create_user('lab-other', is_active=True, is_superuser=True)
        cls.regular = User.objects.create_user('lab-user')
        cls.staff = User.objects.create_user('lab-staff', is_staff=True)
        cls.inactive = User.objects.create_user('lab-inactive', is_superuser=True, is_active=False)
        # Avoid character-save reward signals: fixture insertion must not run unrelated grants.
        cls.character = TbPersonagem.objects.bulk_create([TbPersonagem(
            dono=cls.regular, nome='Real DB character', nivel=3, pv_maximo=27, pv_atual=8,
            carteira_pc=345, aventuras=4, braseiros=7, foto_url='/media/characters/portrait.png')])[0]

    def setUp(self):
        self.client.force_login(self.admin)
        self.export = self.enterContext(patch.object(lab, 'exportar_personagem', side_effect=export_fixture))
        self.source_rules = self.enterContext(patch.object(lab, 'character_rules', return_value={
            'defensive_tags': [], 'offensive_tags': [], 'tag_context': {},
            'actions': [{'id': 'manual', 'nome': 'Ataque declarado', 'tags': []}], 'warnings': []}))
        from home.tag_engine.library import Library
        self.enterContext(patch.object(lab, 'Library', side_effect=lambda: Library(prefer_db=False)))

    def create(self, **data):
        return self.client.post(reverse('vtt_lab_sessions'), json.dumps({'nome': 'Private lab', **data}),
                                content_type='application/json')

    def session(self, with_character=False):
        response = self.create(**({'personagem_id': self.character.pk} if with_character else {}))
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def command(self, session, kind='next_turn', revision=None, command_id=None, **fields):
        body = {'command_id': str(command_id or uuid4()),
                'expected_revision': session['revision'] if revision is None else revision,
                'type': kind, **fields}
        return self.client.post(reverse('vtt_lab_commands', args=[session['id']]),
                                json.dumps(body), content_type='application/json')

    def assert_error(self, response, status, code=None):
        self.assertEqual(response.status_code, status, response.content)
        data = response.json()
        self.assertEqual(set(data), {'error', 'message'})
        if code:
            self.assertEqual(data['error'], code)
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])

    def test_disabled_and_user_gates_before_database_or_export(self):
        factory = RequestFactory()
        for view, args, method in [(lab.laboratory, [], 'get'), (lab.sessions, [], 'get'),
                                   (lab.sessions, [], 'post'), (lab.session_snapshot, [uuid4()], 'get'),
                                   (lab.measure, [uuid4()], 'get'),
                                   (lab.movement_preview, [uuid4()], 'get'),
                                   (lab.commands, [uuid4()], 'post')]:
            request = getattr(factory, method)('/vtt/laboratorio/')
            request.user = self.admin
            with override_settings(VTT_LAB_ENABLED=False), self.assertNumQueries(0):
                self.assertEqual(view(request, *args).status_code, 404)
            for actor in (AnonymousUser(), self.regular, self.staff, self.inactive):
                request.user = actor
                with self.assertNumQueries(0):
                    self.assertEqual(view(request, *args).status_code, 403)
        self.export.assert_not_called()

    def test_html_contract_csrf_cookie_and_no_shared_profile_processors(self):
        UserProfile.objects.filter(user=self.admin).delete()
        with patch.object(lab, 'render_to_string', return_value='<html>Lab</html>') as render:
            response = self.client.get(reverse('vtt_lab'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', response.cookies)
        args = render.call_args.args
        self.assertEqual(args[0], 'home/vtt_lab.html')
        self.assertEqual(args[1]['vtt_lab_api_url'], '/vtt/laboratorio/api/sessoes/')
        self.assertNotIn('request', render.call_args.kwargs)
        self.assertFalse(UserProfile.objects.filter(user=self.admin).exists())

    def test_csrf_is_explicit_for_both_write_endpoints(self):
        session = self.session()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url in (reverse('vtt_lab_sessions'), reverse('vtt_lab_commands', args=[session['id']])):
            self.assert_error(client.post(url, '{}', content_type='application/json'), 403, 'csrf_failed')
        with patch.object(lab, 'render_to_string', return_value='Lab'):
            client.get(reverse('vtt_lab'))
        response = client.post(reverse('vtt_lab_sessions'), '{"nome":"CSRF accepted"}',
                               content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201)

    def test_wrong_methods_are_json_errors_and_framework_body_limit_is_bounded(self):
        session = self.session()
        urls = [(reverse('vtt_lab'), 'post'), (reverse('vtt_lab_sessions'), 'delete'),
                (reverse('vtt_lab_session', args=[session['id']]), 'post'),
                (reverse('vtt_lab_commands', args=[session['id']]), 'get')]
        for url, method in urls:
            self.assert_error(getattr(self.client, method)(url), 405, 'method_not_allowed')
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1):
            self.assert_error(self.create(), 413, 'body_too_large')

    def test_create_default_state_envelope_and_defaults_not_shared(self):
        session = self.session()
        self.assertEqual(set(session), {'id', 'nome', 'revision', 'state', 'updated_at'})
        self.assertEqual(session['revision'], 0)
        self.assertEqual(session['state'], initial_lab_state())
        second = self.session()
        changed = self.command(session).json()
        self.assertEqual(changed['state']['turn'], 1)
        self.assertEqual(VttLabSession.objects.get(pk=second['id']).state['turn'], 0)

    def test_owner_isolation_in_list_snapshot_and_commands(self):
        session = self.session()
        self.client.force_login(self.other_admin)
        self.assertEqual(self.client.get(reverse('vtt_lab_sessions')).json(), {'sessions': []})
        self.assert_error(self.client.get(reverse('vtt_lab_session', args=[session['id']])), 404)
        self.assert_error(self.command(session), 404)
        self.assertEqual(VttLabReceipt.objects.count(), 0)

    def test_list_omits_snapshots_and_get_is_read_only(self):
        session = self.session(True)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse('vtt_lab_sessions'))
            detail = self.client.get(reverse('vtt_lab_session', args=[session['id']]))
        self.assertEqual(detail.json(), session)
        self.assertEqual(set(response.json()['sessions'][0]), {'id', 'nome', 'revision', 'updated_at'})
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
                             for query in captured.captured_queries))
        self.assertEqual(self.export.call_count, 1)

    def test_import_from_create_has_real_source_hash_and_safe_portrait(self):
        session = self.session(True)
        token = session['state']['tokens'][0]
        actual = self.export.call_args.args[0]
        self.assertEqual(actual.pk, self.character.pk)
        self.assertEqual(token['nome'], self.character.nome)
        self.assertEqual(token['hp'], 27)
        self.assertEqual(token['max_hp'], 27)
        self.assertEqual(token['source']['personagem_id'], self.character.pk)
        self.assertEqual(token['source']['export_hash'], hashlib.sha256(
            lab.serializar(token['snapshot']).encode('utf-8')).hexdigest())
        self.assertEqual(token['portrait'], '/media/characters/portrait.png')
        self.assertEqual((token['x'], token['y'], token['z']), (0, 0, 0))

    def test_portrait_allows_http_https_and_root_paths_but_not_executable_urls(self):
        for value, expected in [('https://images.example.invalid/p.png', True),
                                ('http://images.example.invalid/p.png', True),
                                ('/characters/portrait.png', True), ('/media/p.png', True),
                                ('javascript:alert(1)', False), ('data:image/png;base64,a', False),
                                ('//external.invalid/p.png', False), ('/\\external/p.png', False),
                                ('/p.png\n', False), ('relative.png', False)]:
            with self.subTest(value=value):
                TbPersonagem.objects.filter(pk=self.character.pk).update(foto_url=value)
                token = self.session(True)['state']['tokens'][0]
                self.assertEqual('portrait' in token, expected)
                if expected:
                    self.assertEqual(token['portrait'], value)

    def test_import_command_manual_hp_move_and_turn_never_change_official_character(self):
        before = TbPersonagem.objects.values().get(pk=self.character.pk)
        current = self.session()
        current = self.command(current, 'import_character', personagem_id=self.character.pk).json()
        token = current['state']['tokens'][0]
        exported = deepcopy(token['snapshot'])
        current = self.command(current, 'move_token', token_id=token['id'], x=23, y=17, z=2).json()
        current = self.command(current, 'set_hp', token_id=token['id'], hp=5).json()
        current = self.command(current).json()
        self.assertEqual(current['revision'], 4)
        self.assertEqual(current['state']['tokens'][0]['hp'], 5)
        self.assertEqual(current['state']['tokens'][0]['snapshot'], exported)
        self.assertEqual(TbPersonagem.objects.values().get(pk=self.character.pk), before)
        self.assertEqual(current['state']['turn'], 1)
        self.assertEqual(VttLabReceipt.objects.count(), 4)

    def test_replay_before_revision_check_and_after_other_commands_returns_current_state(self):
        initial = self.session()
        key = uuid4()
        first = self.command(initial, command_id=key)
        second = self.command(first.json()).json()
        replay = self.command(initial, command_id=key)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), second)
        self.assertEqual(replay['X-VTT-Lab-Replayed'], 'true')
        self.assertEqual(VttLabReceipt.objects.count(), 2)

    def test_stale_revision_and_conflicting_uuid_have_no_side_effects(self):
        session = self.session()
        key = uuid4()
        current = self.command(session, command_id=key).json()
        self.assert_error(self.command(session), 409, 'revision_conflict')
        self.assert_error(self.command(current, command_id=key), 409, 'command_conflict')
        self.assertEqual(VttLabSession.objects.get().revision, 1)
        self.assertEqual(VttLabReceipt.objects.count(), 1)

    def test_invalid_json_content_type_names_fields_and_body_limits(self):
        url = reverse('vtt_lab_sessions')
        for data in ('{', 'null', '[]', '42', '{"nome":NaN}'):
            self.assert_error(self.client.post(url, data, content_type='application/json'), 400)
        self.assert_error(self.client.post(url, {'nome': 'form'}), 415)
        for name in ('', '   ', 'x' * 121, None, 4, 'bad\x00name'):
            self.assert_error(self.create(nome=name), 400)
        self.assert_error(self.create(owner=self.other_admin.pk), 400)
        self.assert_error(self.create(state=initial_lab_state()), 400)
        self.assert_error(self.client.post(url, ' ' * (lab.MAX_BODY_BYTES + 1), content_type='application/json'), 413)
        self.assertEqual(VttLabSession.objects.count(), 0)

    def test_command_validation_rejects_unknown_boolean_revision_ids_and_huge_numbers(self):
        session = self.session(True)
        token_id = session['state']['tokens'][0]['id']
        for command in ({'type': 'unknown'}, {'expected_revision': True}, {'expected_revision': -1},
                        {'expected_revision': 1.2}, {'command_id': 'bad'}, {'unexpected': 'patch'}):
            body = {'type': 'next_turn', 'expected_revision': 0, 'command_id': str(uuid4()), **command}
            response = self.client.post(reverse('vtt_lab_commands', args=[session['id']]),
                                        json.dumps(body), content_type='application/json')
            self.assert_error(response, 400)
        for x, y, z in [(24, 0, 0), (0, 18, 0), (-1, 0, 0), (0, 0, 101),
                        (True, 0, 0), (0, False, 0), (0, 0, True),
                        (1.5, 0, 0), (0, 1.5, 0), (0, 0, 1.5),
                        (1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0),
                        ('1', 0, 0), (10 ** 100, 0, 0), (float('inf'), 0, 0)]:
            self.assert_error(self.command(session, 'move_token', token_id=token_id, x=x, y=y, z=z), 400)
        for hp in (-1, 28, True, '5', 1.2):
            self.assert_error(self.command(session, 'set_hp', token_id=token_id, hp=hp), 400)
        self.assert_error(self.command(session, 'set_hp', token_id=str(uuid4()), hp=1), 404)
        self.assertEqual(VttLabSession.objects.get().state, session['state'])
        self.assertEqual(VttLabReceipt.objects.count(), 0)

    def test_hp_zero_and_maximum_are_valid(self):
        session = self.session(True)
        token_id = session['state']['tokens'][0]['id']
        current = self.command(session, 'set_hp', token_id=token_id, hp=0).json()
        current = self.command(current, 'set_hp', token_id=token_id, hp=27).json()
        self.assertEqual(current['state']['tokens'][0]['hp'], 27)

    def test_import_missing_invalid_or_failing_character_rolls_back_create_and_command(self):
        for value in (None, True, -1, '1'):
            self.assert_error(self.create(personagem_id=value), 400)
        self.assert_error(self.create(personagem_id=2147483647), 404)
        self.assertEqual(VttLabSession.objects.count(), 0)
        session = self.session()
        self.export.side_effect = RuntimeError('private/internal/detail')
        self.assert_error(self.command(session, 'import_character', personagem_id=self.character.pk), 422)
        self.assert_error(self.create(personagem_id=self.character.pk), 422)
        self.assertEqual(VttLabSession.objects.get().state, session['state'])
        self.assertEqual(VttLabReceipt.objects.count(), 0)

    def test_export_guard_prevents_writes_even_when_exporter_swallows_exception(self):
        def unsafe_export(character):
            try:
                TbPersonagem.objects.filter(pk=character.pk).update(carteira_pc=999999)
            except RuntimeError:
                pass
            return export_fixture(character)
        self.export.side_effect = unsafe_export
        self.assert_error(self.create(personagem_id=self.character.pk), 422, 'export_failed')
        self.character.refresh_from_db()
        self.assertEqual(self.character.carteira_pc, 345)
        self.assertEqual(VttLabSession.objects.count(), 0)

    def test_receipt_failure_rolls_back_state_revision_and_event(self):
        session = self.session()
        with patch.object(VttLabReceipt.objects, 'create', side_effect=IntegrityError('private SQL detail')):
            self.assert_error(self.command(session), 503, 'storage_error')
        actual = VttLabSession.objects.get()
        self.assertEqual(actual.state, session['state'])
        self.assertEqual(actual.revision, 0)
        self.assertEqual(actual.atualizado_em.isoformat(), session['updated_at'])
        self.assertEqual(VttLabReceipt.objects.count(), 0)

    def test_commands_lock_owned_row_and_only_mutate_lab_tables(self):
        session = self.session(True)
        with patch.object(QuerySet, 'select_for_update', autospec=True, side_effect=lambda query: query) as lock:
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(self.command(session).status_code, 200)
        lock.assert_called_once()
        mutations = [query['sql'] for query in captured.captured_queries
                     if query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(len(mutations), 2)
        self.assertTrue(all('TB_VttLabSession' in sql or 'TB_VttLabReceipt' in sql for sql in mutations))

    def test_tokens_events_export_and_state_have_finite_limits(self):
        session = self.session(True)
        with patch.object(lab, 'MAX_TOKENS', 1):
            self.assert_error(self.command(session, 'import_character', personagem_id=self.character.pk), 409)
        with patch.object(lab, 'MAX_EXPORT_BYTES', 1):
            self.assert_error(self.create(personagem_id=self.character.pk), 413)
        with patch.object(lab, 'MAX_STATE_BYTES', 1):
            self.assert_error(self.command(session), 413)
            self.assert_error(self.create(), 413)
        with patch.object(lab, 'MAX_EVENTS', 3):
            for _ in range(5):
                session = self.command(session).json()
        self.assertEqual([event['revision'] for event in session['state']['events']], [3, 4, 5])
        self.assertEqual(VttLabReceipt.objects.count(), 5)

    def test_receipt_uniqueness_and_default_factory_independence(self):
        session = self.session()
        self.command(session)
        receipt = VttLabReceipt.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            VttLabReceipt.objects.create(session=receipt.session, command_id=receipt.command_id,
                                         payload_hash='a' * 64, revision=1)
        first, second = initial_lab_state(), initial_lab_state()
        first['board']['width'] = 1
        self.assertEqual(second['board']['width'], 24)

    def test_real_export_adapter_without_loading_project_urls_or_official_writes(self):
        from home.management.commands import export_personagem_vtt as exporter
        from contextlib import ExitStack
        classes = Mock()
        classes.select_related.return_value.order_by.return_value = []
        resources = Mock()
        resources.filter.return_value.exclude.return_value.exists.return_value = False
        with ExitStack() as stack:
            stack.enter_context(patch.object(TbPersonagem, 'classes', new=property(lambda character: classes)))
            stack.enter_context(patch.object(TbPersonagem, 'recursos', new=property(lambda character: resources)))
            stack.enter_context(patch('home.character_engine.derive', return_value={
                'nivel_total': self.character.nivel, 'pv': {'maximo_calculado': self.character.pv_maximo},
                'carteira': {'pc_total': self.character.carteira_pc}}))
            for helper in ('_recursos_espacos_magia', '_recursos_dados_de_vida',
                           '_recursos_consumiveis_export', '_habilidades', '_magias'):
                stack.enter_context(patch.object(exporter, helper, return_value=[]))
            self.export.side_effect = exporter.exportar_personagem
            response = self.create(personagem_id=self.character.pk)
        self.assertEqual(response.status_code, 201, response.content)
        snapshot = response.json()['state']['tokens'][0]['snapshot']
        self.assertEqual(snapshot['personagem']['pk'], self.character.pk)
        self.assertEqual(snapshot['derive']['pv_max'], 27)
        self.assertEqual(snapshot['moedas']['pc_total'], 345)
        self.assertNotIn('bonfire.settings', sys.modules)
        self.assertNotIn('home.urls', sys.modules)

    def test_creature_import_is_source_bound_and_failure_rolls_back(self):
        creature = SimpleNamespace(pk=7, nome='Criatura de teste', slug='teste', escala_com_dono=False,
            pv='30', ca='13', statblock_json={'hp': {'average': 30}, 'actions': [
                {'name': 'Golpe', 'tags_json': []}]}, tags_json=['always_active', 'resist:fogo'], imagem_url='/static/brand/draconic.webp')
        with patch.object(lab.TbBestiario.objects, 'get', return_value=creature):
            session = self.session()
            response = self.command(session, 'import_creature', criatura_id=7)
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()['state']['tokens'][0]
        self.assertEqual(token['source']['criatura_id'], 7)
        self.assertEqual(token['hp'], 30)
        self.assertIn('resist:fogo', token['rules']['defensive_tags'])
        session = response.json()
        with patch.object(lab.TbBestiario.objects, 'get', return_value=creature), patch.object(
                lab, 'creature_snapshot', side_effect=ValueError('Escala com dono requer contexto.')):
            failed = self.command(session, 'import_creature', criatura_id=7)
        self.assert_error(failed, 422, 'creature_import_failed')
        stored = VttLabSession.objects.get(pk=session['id'])
        self.assertEqual(stored.revision, session['revision'])
        self.assertEqual(len(stored.state['tokens']), 1)

    def test_combat_http_replay_pinned_tags_and_official_data_unchanged(self):
        before = TbPersonagem.objects.values().get(pk=self.character.pk)
        self.source_rules.return_value['defensive_tags'] = ['always_active', 'resist:fogo']
        first = self.session(True)
        second_response = self.command(first, 'import_character', personagem_id=self.character.pk)
        self.assertEqual(second_response.status_code, 200, second_response.content)
        session = second_response.json()
        actor, target = [entry['id'] for entry in session['state']['tokens']]
        response = self.command(session, 'combat_start', teams={actor: 'A', target: 'B'})
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        denied = self.command(session, 'set_hp', token_id=target, hp=1)
        self.assert_error(denied, 409, 'combat_active')
        response = self.command(session, 'combat_start_turn', actor_id=actor)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        command_id = str(uuid4())
        payload = {'target_id': target, 'action_id': 'manual', 'hit': True, 'damage': 5, 'damage_type': 'fogo'}
        response = self.command(session, 'combat_attack', command_id=command_id, **payload)
        self.assertEqual(response.status_code, 200, response.content)
        attacked = response.json()
        self.assertEqual(attacked['state']['tokens'][1]['hp'], 25)
        repeated = self.command(session, 'combat_attack', command_id=command_id, **payload)
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertEqual(repeated.json()['revision'], attacked['revision'])
        self.assertEqual(repeated.json()['state']['tokens'][1]['hp'], 25)
        extra_action = self.command(attacked, 'combat_attack', **payload)
        self.assert_error(extra_action, 422, 'combat_invalid')
        self.assertEqual(VttLabSession.objects.get(pk=attacked['id']).revision, attacked['revision'])
        response = self.command(attacked, 'combat_end_turn')
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        response = self.command(session, 'combat_start_turn', actor_id=target)
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'combat_heal', target_id=target, amount=1)
        self.assertEqual(response.status_code, 200, response.content)
        healed = response.json()
        self.assertEqual(healed['state']['tokens'][1]['hp'], 26)
        reopened = self.client.get(reverse('vtt_lab_session', args=[healed['id']])).json()
        self.assertEqual(reopened['state']['combat'], healed['state']['combat'])
        response = self.command(healed, 'combat_end')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()['state']['combat']['active'])
        self.assertEqual(TbPersonagem.objects.values().get(pk=self.character.pk), before)

    def test_ruler_is_owner_scoped_read_only_and_matches_current_revision(self):
        session = self.session(True)
        response = self.command(session, 'import_character', personagem_id=self.character.pk)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        a, b = session['state']['tokens']
        response = self.command(session, 'move_token', token_id=b['id'], x=3, y=4, z=2)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        url = reverse('vtt_lab_measure', args=[session['id']])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url, {'origin_id': a['id'], 'target_id': b['id']})
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(result['meters'], 13.5)
        self.assertEqual(result['revision'], session['revision'])
        self.assertFalse(result['path_validated'])
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for query in queries.captured_queries))
        self.assert_error(self.client.get(url, {'origin_id': a['id'], 'target_id': str(uuid4())}), 422)
        self.client.force_login(self.other_admin)
        self.assert_error(self.client.get(url, {'origin_id': a['id'], 'target_id': b['id']}), 404)

    def test_invalid_resource_export_keeps_read_only_sheet_with_explicit_warning(self):
        def incomplete(character):
            data = export_fixture(character)
            data['recursos'] = [{'id_fonte': 'TbRecursoclasse:?', 'nome': 'Sem identidade', 'max': 1}]
            return data
        self.export.side_effect = incomplete
        response = self.create(personagem_id=self.character.pk)
        self.assertEqual(response.status_code, 201, response.content)
        token = response.json()['state']['tokens'][0]
        self.assertEqual(token['resources'], {})
        self.assertEqual(token['hp'], 27)
        self.assertTrue(any('Recursos parciais:' in message for message in token['rules']['warnings']))

    def test_resource_cost_is_atomic_with_action_and_request_replay(self):
        def with_resources(character):
            data = export_fixture(character)
            data['recursos'] = [{'id_fonte': 'tag:foco', 'nome': 'Foco', 'max': 1, 'reset': 'long-rest'}]
            return data
        self.export.side_effect = with_resources
        self.source_rules.return_value['actions'] = [{'id': 'focused', 'nome': 'Fonte de teste',
            'tags': ['instant{resource_cost:foco:1}']}]
        session = self.session(True)
        response = self.command(session, 'import_character', personagem_id=self.character.pk)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        a, b = [token['id'] for token in session['state']['tokens']]
        response = self.command(session, 'combat_start', teams={a: 'A', b: 'B'})
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'combat_start_turn', actor_id=a)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        operation_id = str(uuid4())
        payload = dict(target_id=b, action_id='focused', hit=False, damage=0, damage_type='fogo')
        response = self.command(session, 'combat_attack', command_id=operation_id, **payload)
        self.assertEqual(response.status_code, 200, response.content)
        spent = response.json()
        self.assertEqual(spent['state']['tokens'][0]['resources']['tag:foco']['current'], 0)
        self.assertEqual(spent['state']['tokens'][1]['hp'], 27)
        repeated = self.command(session, 'combat_attack', command_id=operation_id, **payload)
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertEqual(repeated.json()['revision'], spent['revision'])
        self.assert_error(self.command(spent, 'set_resource', token_id=a, resource_id='tag:foco', current=1), 409, 'combat_active')
        response = self.command(spent, 'combat_end_turn')
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'combat_start_turn', actor_id=a)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        failed = self.command(session, 'combat_attack', **dict(payload, hit=True, damage=7))
        self.assert_error(failed, 422, 'combat_invalid')
        saved = VttLabSession.objects.get(pk=session['id'])
        self.assertEqual(saved.revision, session['revision'])
        self.assertFalse(saved.state['combat']['view']['action_used'])
        self.assertEqual(saved.state['tokens'][1]['hp'], 27)
        response = self.command(session, 'combat_end')
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'set_resource', token_id=a, resource_id='tag:foco', current=1)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['state']['tokens'][0]['resources']['tag:foco']['current'], 1)
        failed = self.command(response.json(), 'set_resource', token_id=a, resource_id='tag:foco', current=2)
        self.assert_error(failed, 400)

    def test_image_map_metadata_is_persistent_idempotent_and_not_a_movement_rule(self):
        session=self.session()
        before=deepcopy(session['state']['board'])
        config={'background':{'url':'/static/test-map.webp','cell_px':64,'origin_x':-12.5,'origin_y':32,'opacity':0.8},
                'grid_opacity':0.3}
        command_id=str(uuid4())
        response=self.command(session,'configure_presentation',command_id=command_id,presentation=config)
        self.assertEqual(response.status_code,200,response.content)
        current=response.json()
        self.assertEqual(current['state']['presentation'],config)
        self.assertEqual(current['state']['board'],before)
        replay=self.command(session,'configure_presentation',command_id=command_id,presentation=config)
        self.assertEqual(replay.status_code,200)
        self.assertEqual(replay.json()['revision'],1)
        bad=deepcopy(config);bad['background']['url']='data:image/png;base64,abc'
        self.assert_error(self.command(current,'configure_presentation',presentation=bad),422,'presentation_invalid')
        saved=self.client.get(reverse('vtt_lab_session',args=[session['id']])).json()
        self.assertEqual(saved['state']['presentation'],config)
        cleared=self.command(saved,'configure_presentation',presentation={'background':None,'grid_opacity':0})
        self.assertEqual(cleared.status_code,200,cleared.content)
        self.assertIsNone(cleared.json()['state']['presentation']['background'])

    def test_walk_preview_and_commit_respect_terrain_budget_and_receipt(self):
        first = self.session(True)
        response = self.command(first, 'import_character', personagem_id=self.character.pk)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        actor, enemy = [entry['id'] for entry in session['state']['tokens']]
        response = self.command(session, 'configure_board', blocked_cells=[{'x': 0, 'y': 2}],
                                terrain_cells={'0,1': 'difficult'})
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'combat_start', teams={actor: 'A', enemy: 'B'})
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'combat_start_turn', actor_id=actor)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        url = reverse('vtt_lab_movement_preview', args=[session['id']])
        with CaptureQueriesContext(connection) as queries:
            preview = self.client.get(url, {'x': 0, 'y': 3, 'z': 0})
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()['cost_units'], 72)
        self.assertEqual(preview.json()['revision'], session['revision'])
        self.assertNotIn({'x': 0, 'y': 2, 'z': 0}, preview.json()['path'])
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for query in queries.captured_queries))
        self.assert_error(self.command(session, 'move_token', token_id=actor, x=0, y=3, z=0), 409, 'combat_active')
        self.assert_error(self.command(session, 'configure_board', blocked_cells=[], terrain_cells={}), 409, 'combat_active')
        self.assert_error(self.command(session,'configure_presentation',presentation={'background':None,'grid_opacity':0.25}),409,'combat_active')
        command_id = str(uuid4())
        response = self.command(session, 'combat_move', command_id=command_id, x=0, y=3, z=0)
        self.assertEqual(response.status_code, 200, response.content)
        moved = response.json()
        self.assertEqual(moved['state']['tokens'][0]['y'], 3)
        self.assertEqual(moved['state']['combat']['view']['movement'][actor]['remaining_units'], 0)
        self.assertFalse(moved['state']['combat']['view']['action_used'])
        replay = self.command(session, 'combat_move', command_id=command_id, x=0, y=3, z=0)
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(replay.json()['revision'], moved['revision'])
        self.assert_error(self.command(moved, 'combat_move', x=1, y=3, z=0), 422, 'combat_invalid')
        self.assertEqual(VttLabSession.objects.get(pk=session['id']).revision, moved['revision'])
        response = self.command(moved, 'combat_end_turn')
        self.assertEqual(response.status_code, 200, response.content)
        response = self.command(response.json(), 'combat_start_turn', actor_id=actor)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['state']['combat']['view']['movement'][actor]['remaining_units'], 72)
        self.client.force_login(self.other_admin)
        self.assert_error(self.client.get(url, {'x': 0, 'y': 3, 'z': 0}), 404)

    def test_schema_only_migration_matches_models_and_routes_are_wired(self):
        migration = importlib.import_module('home.migrations.0167_vtt_lab').Migration('0167_vtt_lab', 'home')
        self.assertTrue(all(isinstance(op, migrations.CreateModel) for op in migration.operations))
        state = ProjectState.from_apps(apps)
        for name in ('vttlabreceipt', 'vttlabsession'):
            state.remove_model('home', name)
        for operation in migration.operations:
            operation.state_forwards('home', state)
        expected = ProjectState.from_apps(apps)
        for name in ('vttlabsession', 'vttlabreceipt'):
            self.assertEqual(state.models['home', name], expected.models['home', name])
        root = Path(__file__).parent
        tree = ast.parse((root / 'urls.py').read_text(encoding='utf-8-sig'))
        routes = {node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'path' and node.args
                  and isinstance(node.args[0], ast.Constant) and str(node.args[0].value).startswith('vtt/')}
        self.assertEqual(routes, {'vtt/laboratorio/', 'vtt/laboratorio/api/sessoes/',
                                 'vtt/laboratorio/api/sessoes/<uuid:session_id>/',
                                 'vtt/laboratorio/api/sessoes/<uuid:session_id>/medir/',
                                 'vtt/laboratorio/api/sessoes/<uuid:session_id>/caminho/',
                                 'vtt/laboratorio/api/sessoes/<uuid:session_id>/comandos/'})

    def test_flag_default_is_false_and_model_registration_is_last_import(self):
        root = Path(__file__).parent
        tree = ast.parse((root.parent / 'bonfire/settings.py').read_text(encoding='utf-8-sig'))
        flag = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'VTT_LAB_ENABLED'
                            for target in node.targets))
        self.assertEqual(ast.literal_eval(flag.args[1]), False)
        models = ast.parse((root / 'models.py').read_text(encoding='utf-8-sig'))
        self.assertIsInstance(models.body[-1], ast.ImportFrom)
        self.assertEqual(models.body[-1].module, 'vtt_lab_models')

    def test_fixture_bootstrap_rejects_disk_and_non_memory_uri_before_schema_access(self):
        for name in ('fixture.sqlite', 'file:fixture.sqlite?xmode=memory',
                     'file:fixture?mode=memory&mode=ro'):
            with self.subTest(name=name), patch.dict(connection.settings_dict, {'NAME': name}), patch.object(
                    connection, 'schema_editor', side_effect=AssertionError('Must not touch this database')):
                with self.assertRaises(RuntimeError):
                    bootstrap_isolated_schema()


def bootstrap_isolated_schema():
    """Create selected tables for a fresh in-memory fixture after settings.configure/setup.

    Never migrate a configured project database. A threaded HTTP fixture should use
    SQLite's named shared-memory URI and keep its initial connection open.
    """
    database = connection.settings_dict
    name = str(database.get('NAME', ''))
    memory_uri = (name.startswith('file:') and parse_qs(urlsplit(name).query).get('mode') == ['memory'])
    if (database.get('ENGINE') != 'django.db.backends.sqlite3'
            or not (name == ':memory:' or memory_uri)):
        raise RuntimeError('The fixture bootstrap only accepts in-memory SQLite')
    with connection.schema_editor() as editor:
        for model in (ContentType, Permission, Group, get_user_model(), UserProfile,
                      TbRaca, TbLinhagem, TbEssencia, TbAntecedente, TbPersonagem):
            editor.create_model(model)
        state = ProjectState.from_apps(apps)
        for name in ('vttlabreceipt', 'vttlabsession'):
            state.remove_model('home', name)
        migration = importlib.import_module('home.migrations.0167_vtt_lab').Migration('0167_vtt_lab', 'home')
        for operation in migration.operations:
            before = state.clone()
            operation.state_forwards('home', state)
            operation.database_forwards('home', editor, before, state)


if __name__ == '__main__' and '--isolated' in sys.argv:
    bootstrap_isolated_schema()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
