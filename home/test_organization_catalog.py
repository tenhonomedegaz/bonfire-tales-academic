import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .admin import OrganizacaoAdminForm
from .models import TbOrganizacao


class OrganizationCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_user(
            username='organization-editor', password='test-password', is_staff=True
        )

    def test_admin_normalizes_legacy_json_string_and_rejects_object(self):
        fields = {
            'nome': 'Liga do Norte', 'slug': 'liga-do-norte', 'tipo': 'Guilda',
            'regioes': '"[]"', 'territorios': '[]', 'aliados': '["Casa da Luz"]',
            'inimigos': '[]', 'tags': '[]',
        }
        form = OrganizacaoAdminForm(data=fields)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['regioes'], [])
        self.assertEqual(form.cleaned_data['aliados'], ['Casa da Luz'])

        fields['aliados'] = '{"nome":"Casa da Luz"}'
        form = OrganizacaoAdminForm(data=fields)
        self.assertFalse(form.is_valid())
        self.assertIn('aliados', form.errors)

        owner = get_user_model().objects.create_superuser(
            username='organization-owner', password='test-password', email='owner@example.invalid'
        )
        self.client.force_login(owner)
        response = self.client.post(reverse('admin:home_tborganizacao_add'), data={
            **fields, 'aliados': '["Casa da Luz"]', '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 302)
        saved = TbOrganizacao.objects.get(slug='liga-do-norte')
        self.assertEqual(saved.regioes, [])
        self.assertEqual(saved.aliados, ['Casa da Luz'])

    def test_staff_post_persists_lists_and_catalog_exposes_typed_relationships(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({
                'nome': 'Liga do Norte', 'regioes': '[]',
                'aliados': ['Casa da Luz'], 'inimigos': '["Bando"]',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        organization = TbOrganizacao.objects.get(slug='liga-do-norte')
        self.assertEqual(organization.regioes, [])
        self.assertEqual(organization.aliados, ['Casa da Luz'])
        self.assertEqual(organization.inimigos, ['Bando'])

        # Existing rows may contain a JSON string instead of a JSON array.
        TbOrganizacao.objects.create(
            nome='Guarda Antiga', slug='guarda-antiga', aliados='[]', regioes='[]'
        )
        TbOrganizacao.objects.create(
            nome='Arquivo Malformado', slug='arquivo-malformado', aliados={'nome': 'Casa'},
        )
        catalog = self.client.get(reverse('mundo_organizacoes'))
        self.assertEqual(catalog.status_code, 200)
        by_slug = {item['slug']: item for item in catalog.context['items']}
        self.assertEqual(by_slug['liga-do-norte']['meta']['Aliados'], ['Casa da Luz'])
        self.assertEqual(by_slug['liga-do-norte']['meta']['Inimigos'], ['Bando'])
        self.assertEqual(by_slug['guarda-antiga']['meta']['Aliados'], [])
        self.assertEqual(by_slug['arquivo-malformado']['meta']['Aliados'], [])
        self.assertNotIn('[]', by_slug['guarda-antiga']['tags'])

        repeated = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({'nome': 'Liga do Norte', 'aliados': ['Casa Renovada']}),
            content_type='application/json',
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(TbOrganizacao.objects.filter(slug='liga-do-norte').count(), 1)
        organization.refresh_from_db()
        self.assertEqual(organization.aliados, ['Casa Renovada'])

    def test_invalid_post_does_not_write_any_organization(self):
        anonymous = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({'nome': 'Sem Autorização'}),
            content_type='application/json',
        )
        self.assertEqual(anonymous.status_code, 404)
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({'nome': 'Lote Inválido', 'aliados': '[invalid'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TbOrganizacao.objects.exists())
