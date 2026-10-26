"""Read-only export, lossless long text and permission regressions."""
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from . import catalog_export as exports
from .catalog_export_admin import catalog_export_view
from .models import TbTalento, TbConteudoEstatico, TbItemMundano


@override_settings(TIME_ZONE='America/Sao_Paulo', TEMPLATES=[{
    'BACKEND':'django.template.backends.django.DjangoTemplates', 'APP_DIRS':True,
    'DIRS':[str(Path(__file__).resolve().parent / 'templates')],
    'OPTIONS':{'libraries':{'humanize':'django.contrib.humanize.templatetags.humanize'},
               'context_processors':['django.template.context_processors.request',
                                     'django.contrib.auth.context_processors.auth']},
}], MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware'])
class CatalogExportTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser('export-owner', password='isolated-test')
        self.talent = TbTalento.objects.create(nome='Teste epico', slug='teste-epico',
            tipo='epico', descricao='**Descricao** com paragrafos.\n\nOutro paragrafo.',
            tags_json=['attr:talent_attr_score+2', 'attr_max:talent_attr_score=30'])
        self.other = TbTalento.objects.create(nome='Outro', slug='outro', tipo='geral', descricao='Outro')

    def spec(self, **updates):
        table = {'model':'talento', 'fields':['nome', 'descricao', 'tags_json'], 'filters':[]}
        table.update(updates)
        return {'tables':[table]}

    def request(self, data=None, user=None):
        factory = RequestFactory()
        request = factory.post('/admin/catalog-export/', data) if data is not None else factory.get('/admin/catalog-export/')
        request.user = user or self.owner
        return catalog_export_view(request)

    def ticket(self, spec=None):
        response = self.request({'action':'preview', 'spec':json.dumps(spec or self.spec())})
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def test_filtered_multiple_tables_include_pk_and_json(self):
        item = TbItemMundano.objects.create(nome='Item', slug='item', preco='123.45')
        spec = self.spec(filters=[{'field':'tipo','op':'exact','value':'epico'}])
        spec['tables'].append({'model':'item_mundano', 'fields':['nome','preco']})
        prepared = exports.prepare(spec)
        stream = exports.build_workbook(prepared, self.owner.pk)
        try:
            book = load_workbook(stream)
            self.assertEqual(book['talento'].max_row, 2)
            self.assertEqual(book['talento']['A2'].value, self.talent.pk)
            self.assertEqual(json.loads(book['talento']['D2'].value), self.talent.tags_json)
            self.assertEqual(book['item_mundano']['C2'].value, '123.45')
            self.assertEqual(TbTalento.objects.count(), 2)
            self.assertEqual(TbItemMundano.objects.get(pk=item.pk).nome, 'Item')
        finally:
            stream.close()

    def test_formula_like_values_are_text_and_large_text_is_preserved(self):
        original = 'á😀' * 20000
        self.talent.nome, self.talent.descricao = '=HYPERLINK("bad")', original
        self.talent.save(update_fields=['nome','descricao'])
        stream = exports.build_workbook(exports.prepare(self.spec()), self.owner.pk)
        try:
            book = load_workbook(stream)
            self.assertEqual(book['talento']['B2'].data_type, 's')
            self.assertEqual(book['talento']['B2'].value, '=HYPERLINK("bad")')
            self.assertTrue(book['talento']['C2'].value.startswith('@texto:'))
            restored = ''.join(row[6] for row in book['_textos_longos'].iter_rows(min_row=2, values_only=True))
            self.assertEqual(restored, original)
            self.assertTrue(all(cell.data_type != 'f' for sheet in book for row in sheet for cell in row))
        finally:
            stream.close()

    def test_inclusive_period_and_invalid_period_on_catalog_without_date(self):
        row = TbConteudoEstatico.objects.create(chave='periodo', pagina='home')
        at = timezone.make_aware(datetime(2026,10,25,23,59))
        TbConteudoEstatico.objects.filter(pk=row.pk).update(atualizado_em=at)
        spec = {'tables':[{'model':'tbconteudoestatico', 'fields':['chave','atualizado_em'],
                         'date_field':'atualizado_em', 'from':'2026-10-25', 'to':'2026-10-25'}]}
        self.assertEqual(exports.prepare(spec)[0]['count'], 1)
        spec['tables'][0]['from'] = '2026-10-26'
        with self.assertRaises(exports.ExportError):
            exports.prepare(spec)
        with self.assertRaises(exports.ExportError):
            exports.prepare(self.spec(date_field='nome', **{'from':'2026-01-01'}))
        with self.assertRaises(exports.ExportError):
            exports.prepare(self.spec(**{'from':'2026-01-01'}))

    def test_rejects_private_tables_fields_and_orm_traversal(self):
        for spec in [self.spec(model='auth_user'), self.spec(fields=['password']),
                     self.spec(filters=[{'field':'nome__regex','op':'exact','value':'.*'}]),
                     self.spec(filters=[{'field':'nome','op':'regex','value':'.*'}]),
                     self.spec(fields=['nome','nome'])]:
            with self.subTest(spec=spec), self.assertRaises(exports.ExportError):
                exports.prepare(spec)

    def test_limits_before_generation_and_during_text_generation(self):
        with patch.object(exports, 'MAX_ROWS_PER_TABLE', 1), self.assertRaises(exports.ExportError):
            exports.prepare(self.spec())
        prepared = exports.prepare(self.spec())
        with patch.object(exports, 'MAX_TEXT_BYTES', 5), self.assertRaises(exports.ExportError):
            exports.build_workbook(prepared, self.owner.pk)

    def test_superuser_preview_download_and_audit(self):
        preview = self.ticket()
        response = self.request({'action':'download', 'ticket':preview['ticket']})
        self.assertEqual(response.status_code, 200)
        try:
            book = load_workbook(BytesIO(b''.join(response.streaming_content)))
            self.assertIn('talento', book.sheetnames)
        finally:
            response.close()
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(LogEntry.objects.filter(user=self.owner).count(), 1)

    def test_preview_is_bound_to_owner_and_changes_require_new_preview(self):
        ticket = self.ticket()['ticket']
        other = get_user_model().objects.create_superuser('other-export', password='isolated-test')
        self.assertEqual(self.request({'action':'download','ticket':ticket}, other).status_code, 403)
        self.other.delete()
        self.assertEqual(self.request({'action':'download','ticket':ticket}).status_code, 400)
        self.assertEqual(self.request({'action':'download','ticket':'fake'}).status_code, 400)
        self.assertFalse(LogEntry.objects.exists())

    def test_staff_without_superuser_is_denied(self):
        staff = get_user_model().objects.create_user('export-staff', is_staff=True)
        self.assertEqual(self.request(user=staff).status_code, 403)
        self.assertEqual(self.request({'action':'preview','spec':json.dumps(self.spec())}, staff).status_code, 403)

    def test_admin_page_and_csrf(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'export-schema')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(reverse('admin:catalog_export'), {'action':'preview','spec':json.dumps(self.spec())})
        self.assertEqual(response.status_code, 403)
        client.get(reverse('admin:catalog_export'))
        response = client.post(reverse('admin:catalog_export'),
            {'action':'preview','spec':json.dumps(self.spec())},
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.content)

    def test_xml_unsafe_text_has_reversible_encoding(self):
        from .catalog_export import _scalar
        self.assertEqual(_scalar(12345678901234567890), '12345678901234567890')
        # Update bypasses normal form validation to simulate legacy dirty data.
        TbTalento.objects.filter(pk=self.talent.pk).update(descricao='before\x00after')
        stream = exports.build_workbook(exports.prepare(self.spec()), self.owner.pk)
        try:
            value = load_workbook(stream)['talento']['C2'].value
            self.assertEqual(json.loads(value.removeprefix('JSON_TEXT:')), 'before\x00after')
        finally:
            stream.close()
