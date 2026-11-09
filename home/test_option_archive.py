import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from home import test_db_access as api_fixtures, test_versioned_options as option_fixtures
from home.content_versions import create_revision, seal_ruleset
from home.picks import _opcao_universe
from home.views import SiteDataUnavailable
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_options import VersionedOptions


class OptionArchiveTests(TestCase):
    def setUp(self):
        self.seal = option_fixtures.VersionedOptionsTests.seal.__get__(self)
        self.ctx = option_fixtures.VersionedOptionsTests.ctx.__get__(self)
        option_fixtures.VersionedOptionsTests.setUp(self)

    def test_retirement_hides_new_choices_but_preserves_old_selections(self):
        before = _opcao_universe(self.ctx(ruleset=self.ruleset))
        self.option.arquivado = True
        self.option.save()
        self.assertEqual(_opcao_universe(self.ctx()), [])
        self.assertEqual(_opcao_universe(self.ctx(
            constraints={'listed_slugs': [self.option.slug]})), [])
        self.assertEqual(_opcao_universe(self.ctx(ruleset=self.ruleset)), before)
        retired = self.seal()
        source = SimpleNamespace(descricao='::options=Style')
        self.assertEqual(_opcao_universe(self.ctx(ruleset=retired, source=source)), [])
        choice = SimpleNamespace(id_opcao_id=self.option.pk, valor=self.option.slug)
        self.assertEqual(VersionedOptions(retired).selected_features([choice])[0][2].tags_json,
                         ['ca:+1'])
        with patch('home.views._site_docs', return_value=[{
                'Id_Opcao': str(self.option.pk), 'Nome': self.option.nome, 'Tipo': 'Style'}]):
            self.assertEqual(self.client.get(reverse('api_opcoes')).json()['opcoes'], [])
            response = self.client.get(reverse('jogador_opcoes'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['json_opcoes'], [])
        with patch('home.views._site_docs', side_effect=SiteDataUnavailable):
            result = self.client.get(reverse('api_opcoes') + '?tipo=Style')
            self.assertEqual(result.json()['opcoes'], [])

    def test_snapshot_without_archive_field_keeps_its_original_options(self):
        payload = deepcopy(VersionedOptions(self.ruleset).data)
        for row in payload['options']:
            row.pop('arquivado')
        old = seal_ruleset([create_revision('option-catalog', payload)],
                          evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.assertEqual(_opcao_universe(self.ctx(ruleset=old)),
                         _opcao_universe(self.ctx(ruleset=self.ruleset)))

    def test_api_archives_with_version_scope_and_replay_guards(self):
        fixture = api_fixtures.StructuredDbApiTests
        _, secret = fixture.make_key(self)
        headers = fixture.request_headers(self, secret)
        url = reverse('db_access_object', args=['opcao_jogo', self.option.pk])
        version = self.client.get(url, **headers).json()['version']
        command = dict(data=json.dumps({'arquivado': True}), content_type='application/json',
                       **dict(headers, HTTP_IDEMPOTENCY_KEY='archive-one', HTTP_IF_MATCH=version))
        self.assertEqual(self.client.patch(url, **command).status_code, 200)
        self.assertEqual(self.client.patch(url, **command).status_code, 200)
        self.option.refresh_from_db()
        self.assertTrue(self.option.arquivado)
        self.assertEqual(self.option.tags_json, ['ca:+1'])
        stale = dict(command, HTTP_IDEMPOTENCY_KEY='archive-stale')
        self.assertEqual(self.client.patch(url, **stale).status_code, 412)
        _, read_secret = fixture.make_key(self, scopes=('read',))
        read_headers = fixture.request_headers(self, read_secret,
            HTTP_IDEMPOTENCY_KEY='archive-no-write', HTTP_IF_MATCH=version)
        denied = self.client.patch(url, data=json.dumps({'arquivado': False}),
                                  content_type='application/json', **read_headers)
        self.assertEqual(denied.status_code, 403)
