from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.conquista_admin_form import ConquistaAdminForm
from home.models import TbClasse, TbConquista


class ConquistaAdminFormTests(TestCase):
    def base_data(self, slug):
        return {'slug': slug, 'nome': 'Conquista assistida',
                'criterio': 'automatico', 'criterio_json': '{}',
                'ativo': 'on', 'ordem': '0'}

    def test_staff_creates_class_rule_without_editing_json(self):
        classe = TbClasse.objects.create(nome='Classe QA', slug='classe-qa')
        admin = get_user_model().objects.create_superuser(
            'conquista-form-admin', 'conquista-form@example.invalid', 'x')
        self.client.force_login(admin)
        url = reverse('admin:home_tbconquista_add')
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'metrica_assistida')
        data = {**self.base_data('classe-assistida'),
                'metrica_assistida': 'class_started',
                'classe_inicial': str(classe.pk)}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.content[:500])
        rule = TbConquista.objects.get(slug='classe-assistida')
        self.assertEqual(rule.criterio_json, {
            'schema_version': 1, 'metric': 'class_started', 'scope': 'account',
            'filters': {'class_slug': classe.slug}, 'operator': 'gte', 'target': 1})

    def test_units_form_builds_multiple_safe_identities_and_rejects_duplicates(self):
        data = {**self.base_data('unidades-assistidas'),
                'metrica_assistida': 'items_purchased_units',
                'itens_comprados': 'mundano:12\nmagico:34',
                'operador_unidades': 'gt', 'alvo_unidades': '10'}
        form = ConquistaAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save()
        self.assertEqual(rule.criterio_json, {
            'schema_version': 1, 'metric': 'items_purchased_units',
            'scope': 'account', 'aggregate': 'sum',
            'filters': {'items': [{'catalog': 'mundano', 'id': 12},
                                  {'catalog': 'magico', 'id': 34}]},
            'operator': 'gt', 'target': 10})
        duplicate = ConquistaAdminForm(data={**data, 'slug': 'unidades-duplicadas',
            'itens_comprados': 'mundano:12\nmundano:12'})
        self.assertFalse(duplicate.is_valid())
        self.assertIn('itens_comprados', duplicate.errors)

    def test_simple_metrics_generate_supported_rules(self):
        for metric in ('characters_created', 'stories_published', 'items_purchased'):
            with self.subTest(metric=metric):
                form = ConquistaAdminForm(data={
                    **self.base_data(f'assistida-{metric}'),
                    'metrica_assistida': metric,
                })
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.save().criterio_json, {
                    'schema_version': 1, 'metric': metric, 'scope': 'account',
                    'operator': 'gte', 'target': 1,
                })

    def test_legacy_rule_cannot_be_activated_without_supported_definition(self):
        legacy = TbConquista.objects.create(
            slug='legada-inativa', nome='Legada', criterio='automatico',
            criterio_json={'metric': 'unsupported'}, ativo=False)
        data = {**self.base_data(legacy.slug), 'nome': 'Legada editada',
                'criterio_json': '{"metric":"unsupported"}'}
        inactive = ConquistaAdminForm(data={key: value for key, value in data.items()
                                           if key != 'ativo'}, instance=legacy)
        self.assertTrue(inactive.is_valid(), inactive.errors)
        active = ConquistaAdminForm(data=data, instance=legacy)
        self.assertFalse(active.is_valid())
        self.assertIn('criterio_json', active.errors)
