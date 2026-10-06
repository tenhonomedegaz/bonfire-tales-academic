import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from home.conquista_admin_form import ConquistaAdminForm
from home.models import (TbAnuncioItemMagico, TbClasse, TbConquista, TbItemMagico,
                         TbItemMundano, TbMagia, TbPersonagem)


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
        mundane = TbItemMundano.objects.create(nome='Item QA', slug='item-qa')
        magic = TbItemMagico.objects.create(nome='Item mágico QA', slug='item-magico-qa')
        data = {**self.base_data('unidades-assistidas'),
                'metrica_assistida': 'items_purchased_units',
                'itens_comprados': f'mundano:{mundane.pk}\nmagico:{magic.pk}',
                'operador_unidades': 'gt', 'alvo_unidades': '10'}
        form = ConquistaAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save()
        self.assertEqual(rule.criterio_json, {
            'schema_version': 1, 'metric': 'items_purchased_units',
            'scope': 'account', 'aggregate': 'sum',
            'filters': {'items': [{'catalog': 'mundano', 'id': mundane.pk},
                                  {'catalog': 'magico', 'id': magic.pk}]},
            'operator': 'gt', 'target': 10})
        duplicate = ConquistaAdminForm(data={**data, 'slug': 'unidades-duplicadas',
            'itens_comprados': f'mundano:{mundane.pk}\nmundano:{mundane.pk}'})
        self.assertFalse(duplicate.is_valid())
        self.assertIn('itens_comprados', duplicate.errors)
        missing = ConquistaAdminForm(data={**data, 'slug': 'unidades-ausentes',
            'itens_comprados': f'mundano:{mundane.pk + 100000}\nmagico:{magic.pk + 100000}'})
        self.assertFalse(missing.is_valid())
        self.assertIn(f'mundano:{mundane.pk + 100000}', str(missing.errors['itens_comprados']))
        self.assertIn(f'magico:{magic.pk + 100000}', str(missing.errors['itens_comprados']))

    def test_units_form_checks_workshop_spell_and_community_announcement_ids(self):
        spell = TbMagia.objects.create(nome='Magia QA', slug='magia-qa')
        seller = get_user_model().objects.create_user('seller-form-qa')
        character = TbPersonagem.objects.create(dono=seller, nome='Vendedor QA')
        announcement = TbAnuncioItemMagico.objects.create(
            vendedor=character, nome='Anúncio QA', status='vendido')
        data = {**self.base_data('oficina-comunidade'),
                'metrica_assistida': 'items_purchased_units',
                'itens_comprados': f'oficina:{spell.pk}\ncomunidade:{announcement.pk}',
                'operador_unidades': 'gte', 'alvo_unidades': '1'}
        form = ConquistaAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        missing = ConquistaAdminForm(data={**data,
            'itens_comprados': f'oficina:{spell.pk + 100000}\ncomunidade:{announcement.pk + 100000}'})
        self.assertFalse(missing.is_valid())
        self.assertIn(f'oficina:{spell.pk + 100000}', str(missing.errors['itens_comprados']))
        self.assertIn(f'comunidade:{announcement.pk + 100000}', str(missing.errors['itens_comprados']))

    def test_raw_json_checks_new_identity_but_preserves_unchanged_historical_rule(self):
        definition = {
            'schema_version': 1, 'metric': 'items_purchased_units',
            'scope': 'account', 'aggregate': 'sum',
            'filters': {'items': [{'catalog': 'mundano', 'id': 99999999}]},
            'operator': 'gte', 'target': 1,
        }
        data = {**self.base_data('raw-invalid-identity'),
                'criterio_json': json.dumps(definition)}
        self.assertIn('criterio_json', ConquistaAdminForm(data=data).errors)
        historical = TbConquista.objects.create(
            slug='historical-identity', nome='Histórica', criterio='automatico',
            criterio_json=definition)
        edited = ConquistaAdminForm(data={**data, 'slug': historical.slug,
                                          'nome': 'Histórica editada'}, instance=historical)
        self.assertTrue(edited.is_valid(), edited.errors)
        changed = ConquistaAdminForm(data={**data, 'slug': historical.slug,
            'criterio_json': json.dumps({**definition, 'filters': {
                'items': [{'catalog': 'mundano', 'id': 99999998}]}})}, instance=historical)
        self.assertIn('criterio_json', changed.errors)
        historical.ativo = False
        historical.save(update_fields=['ativo'])
        reactivated = ConquistaAdminForm(data={**data, 'slug': historical.slug},
                                         instance=historical)
        self.assertIn('criterio_json', reactivated.errors)
        historical.ativo = True
        with self.assertRaises(ValidationError):
            historical.full_clean()

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

    def test_level_form_requires_real_class_and_configured_threshold(self):
        classe = TbClasse.objects.create(nome='Classe nível QA', slug='classe-nivel-qa')
        admin = get_user_model().objects.create_superuser(
            'level-form-admin', 'level-form-admin@example.invalid', 'x')
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse('admin:home_tbconquista_add')),
                            'classe_unica')
        data = {**self.base_data('nivel-assistido'),
                'metrica_assistida': 'character_level',
                'classe_nivel': str(classe.pk), 'alvo_nivel': '3'}
        form = ConquistaAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().criterio_json, {
            'schema_version': 1, 'metric': 'character_level',
            'scope': 'account', 'filters': {'class_slug': classe.slug},
            'operator': 'gte', 'target': 3})
        invalid = ConquistaAdminForm(data={**data, 'slug': 'nivel-invalido',
                                           'alvo_nivel': '21'})
        self.assertIn('alvo_nivel', invalid.errors)

        pure = ConquistaAdminForm(data={**data, 'slug': 'nivel-puro',
                                       'alvo_nivel': '20', 'classe_unica': 'on'})
        self.assertTrue(pure.is_valid(), pure.errors)
        self.assertEqual(pure.save().criterio_json['filters'],
                         {'class_slug': classe.slug, 'single_class': True})
        self.assertTrue(ConquistaAdminForm(instance=pure.instance).fields[
            'classe_unica'].initial)
        early = ConquistaAdminForm(data={**data, 'slug': 'nivel-puro-precoce',
                                        'classe_unica': 'on'})
        self.assertIn('classe_unica', early.errors)

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
