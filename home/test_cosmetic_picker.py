"""Read-only picker contracts. Run with isolated settings and no project database."""

import ast
import json
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import path, resolve, reverse
from django.utils import timezone

from home import cosmetic_picker as picker
from home import cosmetics
from home.templatetags.cosmetic_packages import cosmetic_catalog


def placeholder(request):
    return HttpResponse()


urlpatterns = [
    path('perfil/cosmeticos/previa/', picker.cosmetic_picker_preview, name='cosmetic_picker_preview'),
    *[path(name + '/', placeholder, name=name) for name in (
        'profile', 'personagens', 'colaborador', 'theme_studio',
        'cosmetic_checkout', 'event_cosmetic_shop')],
]


def catalog_item(key='sample', tipo='tema', origin='staff', scope='ambos', **extra):
    return dict({'key': key, 'tipo': tipo, 'slug': tipo + '-' + key,
                 'label': 'Sample', 'class': 'theme-sample', 'origem': origin,
                 'escopo': scope, 'descricao': 'Public preview', 'definicao': {}}, **extra)


def snapshot(*items):
    return {'catalog': {item['slug']: item for item in items}, 'inventory': {},
            'permanent': set(), 'rules': {}, 'cash': [], 'events': [], 'tier': None}


@override_settings(ROOT_URLCONF=__name__, STATIC_URL='/static/', LOGIN_URL='/login/',
                   ALLOWED_HOSTS=['testserver'])
class PickerTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(pk=11, is_authenticated=True)
        self.snapshot = snapshot(catalog_item())
        self.original_snapshot = picker.cosmetic_discovery._read_snapshot
        self.read = self.enterContext(patch.object(
            picker.cosmetic_discovery, '_read_snapshot', return_value=self.snapshot))
        self.load = self.enterContext(patch.object(picker, 'load_package', return_value={'avatar': []}))
        self.registry = self.enterContext(patch.object(picker, '_presentation_metadata', return_value={}))
        self.sync = self.enterContext(patch.object(
            cosmetics, '_sync_rank_once', side_effect=AssertionError('Preview cannot sync grants')))

    def preview(self, **params):
        query = dict(tipo='tema', key='sample', escopo='perfil')
        query.update(params)
        request = self.factory.get(reverse('cosmetic_picker_preview'), query)
        request.user = self.user
        return picker.cosmetic_picker_preview(request)

    def data(self, **params):
        response = self.preview(**params)
        self.assertEqual(response.status_code, 200)
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        return json.loads(response.content)

    def test_route_uses_new_module_without_editing_profile_views(self):
        self.assertEqual(resolve('/perfil/cosmeticos/previa/').func, picker.cosmetic_picker_preview)
        tree = ast.parse((Path(__file__).parent / 'urls.py').read_text(encoding='utf-8-sig'))
        route = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'path'
                     and node.args and isinstance(node.args[0], ast.Constant)
                     and node.args[0].value == 'perfil/cosmeticos/previa/')
        self.assertEqual(ast.unparse(route.args[1]), 'cosmetic_picker.cosmetic_picker_preview')

    def test_login_get_only_and_private_errors(self):
        self.user.is_authenticated = False
        self.assertEqual(self.preview().status_code, 302)
        self.user.is_authenticated = True
        request = self.factory.post('/perfil/cosmeticos/previa/')
        request.user = self.user
        response = picker.cosmetic_picker_preview(request)
        self.assertEqual(response.status_code, 405)
        self.assertIn('no-store', response['Cache-Control'])
        self.read.assert_not_called()
        self.load.assert_not_called()

    def test_invalid_parameters_never_read_catalog_or_files(self):
        invalid = [{'tipo': kind} for kind in ('', 'badge', 'theme', '../tema')]
        invalid += [{'escopo': scope} for scope in ('', 'ambos', '../perfil')]
        invalid += [{'key': key} for key in ('', '../sample', '/tmp/sample', 'a/b', 'a\\b',
                     'a.json', 'x?y', 'x#y', ' x', 'x\n', '%2e%2e', 'A', 'a' * 101)]
        invalid += [{'key': ['sample', 'other']}, {'tipo': ['tema', 'efeito']},
                    {'escopo': ['perfil', 'ficha']}]
        for params in invalid:
            with self.subTest(params=params):
                response = self.preview(**params)
                self.assertEqual(response.status_code, 400)
                self.assertIn('private', response['Cache-Control'])
                self.assertIn('no-store', response['Cache-Control'])
        self.read.assert_not_called()
        self.load.assert_not_called()
        self.registry.assert_not_called()

    def test_active_catalog_kind_and_scope_are_required(self):
        for catalog in (snapshot(), snapshot(catalog_item(scope='ficha')),
                        snapshot(catalog_item(tipo='moldura'))):
            with self.subTest(catalog=catalog):
                self.read.return_value = catalog
                response = self.preview()
                self.assertEqual(response.status_code, 404)
                self.assertIn('no-store', response['Cache-Control'])
        self.load.assert_not_called()
        self.registry.assert_not_called()

    def test_locked_art_is_public_but_never_a_grant_and_loads_only_requested_package(self):
        self.snapshot['catalog']['tema-unrelated'] = catalog_item('unrelated')
        before = deepcopy(self.snapshot)
        data = self.data()
        self.assertTrue(data['locked'])
        self.assertEqual(data['package'], {'avatar': []})
        self.assertEqual(data['acquisition'], {'label': '', 'url': ''})
        self.assertEqual(data['description'], 'Public preview')
        self.assertEqual(data['css_class'], 'theme-sample')
        self.assertEqual(data['theme_category'], 'classico')
        self.assertIn('Cookie', self.preview()['Vary'])
        self.assertEqual(self.snapshot, before)
        self.assertEqual(self.load.call_count, 2)
        self.load.assert_called_with('tema', 'sample', 'perfil')
        self.sync.assert_not_called()

    def test_each_supported_kind_and_scope_loads_exactly_once(self):
        for tipo in ('tema', 'moldura', 'efeito'):
            for escopo in ('perfil', 'ficha'):
                with self.subTest(tipo=tipo, escopo=escopo):
                    self.read.return_value = snapshot(catalog_item(tipo=tipo))
                    self.load.reset_mock()
                    data = self.data(tipo=tipo, escopo=escopo)
                    self.load.assert_called_once_with(tipo, 'sample', escopo)
                    self.assertEqual(data['tipo'], tipo)

    def test_classification_never_revokes_free_presets_or_unlocks_specials(self):
        for origin in ('livre', 'conquista', 'evento_manual', 'loja_braseiro', 'loja_mm', 'colaborador'):
            for category in ('classico', 'especial'):
                with self.subTest(origin=origin, category=category):
                    self.read.return_value = snapshot(catalog_item(origin=origin, categoria=category))
                    data = self.data()
                    self.assertEqual(data['locked'], origin != 'livre')
                    self.assertEqual(data['theme_category'], category)

    def test_existing_inventory_and_permanent_rights_preserve_access(self):
        for source in ('staff', 'conquista:rank', 'compra_mm'):
            self.snapshot['inventory'] = {'tema-sample': {'origem': source, 'suspenso_em': None}}
            self.assertFalse(self.data()['locked'])
        self.snapshot['inventory']['tema-sample']['suspenso_em'] = timezone.now()
        self.assertTrue(self.data()['locked'])
        self.snapshot['permanent'].add('tema-sample')
        self.assertFalse(self.data()['locked'])

    def test_colab_requires_real_tier_not_temporary_inventory(self):
        for minimum, tier, expected in [('conde', None, True), ('conde', 'conde', False),
                                        ('duque', 'conde', True), ('marques', 'duque', False),
                                        ('', 'duque', True)]:
            with self.subTest(minimum=minimum, tier=tier):
                self.read.return_value = snapshot(catalog_item(origin='colaborador', requer_plano=minimum))
                self.read.return_value['tier'] = tier
                self.read.return_value['inventory'] = {
                    'tema-sample': {'origem': 'colaborador:duque', 'suspenso_em': None}}
                self.assertEqual(self.data()['locked'], expected)

    def test_snapshot_is_for_current_user_on_every_request(self):
        def read(user):
            result = snapshot(catalog_item())
            if user.pk == 11:
                result['permanent'].add('tema-sample')
            return result
        self.read.side_effect = read
        self.assertFalse(self.data()['locked'])
        self.user = SimpleNamespace(pk=12, is_authenticated=True)
        self.assertTrue(self.data()['locked'])

    def test_real_snapshot_uses_batched_read_only_queries_and_colab_tier(self):
        from home import models
        from home import cosmetic_entitlements, permissions
        entry = catalog_item(origin='colaborador', requer_plano='conde')
        with patch.object(picker.cosmetic_discovery, 'get_catalog', side_effect=lambda kind:
                          {'sample': entry} if kind == 'tema' else {}), patch.object(
                cosmetic_entitlements, 'permanent_cosmetic_slugs', return_value=set()) as permanent, patch.object(
                permissions, 'colab_tier', return_value='conde') as tier, patch.object(
                models.TbUsuarioCosmetico, 'objects') as inventory, patch.object(
                models.TbConquista, 'objects') as rules, patch.object(
                models.TbCosmetico, 'objects') as catalog, patch.object(
                models.CosmeticCheckoutOffer, 'objects') as cash, patch.object(
                models.EventCosmeticOffer, 'objects') as events:
            inventory.filter.return_value.values.return_value = []
            rules.filter.return_value.values.return_value = []
            catalog.filter.return_value.values_list.return_value = []
            cash.filter.return_value.values.return_value = []
            events.filter.return_value.values.return_value = []
            # Reach the original function despite the endpoint fixture's patch.
            result = self.original_snapshot(self.user)
        self.assertEqual(result['tier'], 'conde')
        tier.assert_called_once_with(self.user)
        permanent.assert_called_once_with(self.user)
        inventory.filter.assert_called_once_with(user=self.user, cosmetico__slug__in={'tema-sample'})
        for manager in (inventory, rules, catalog, cash, events):
            manager.create.assert_not_called()
            manager.update.assert_not_called()
            manager.get_or_create.assert_not_called()
        self.sync.assert_not_called()

    def test_only_published_acquisition_links_are_exposed(self):
        entry = self.snapshot['catalog']['tema-sample']
        entry['origem'] = 'evento_manual'
        offer = dict(pk=7, cosmetico__slug=entry['slug'], active=True,
                     starts_at=None, ends_at=None, cost_braseiros=10)
        self.snapshot['events'] = [offer]
        data = self.data()
        self.assertTrue(data['locked'])
        self.assertEqual(data['acquisition']['url'], '/event_cosmetic_shop/#event-offer-7')
        offer['starts_at'] = timezone.now() + timedelta(days=1)
        self.assertEqual(self.data()['acquisition']['url'], '')
        offer.update(starts_at=None, ends_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.data()['acquisition']['url'], '')
        self.snapshot['rules'][entry['slug']] = [dict(
            nome='Rank', descricao='Published condition', criterio='automatico')]
        data = self.data()
        self.assertTrue(data['locked'])
        self.assertIn('Published condition', data['unlock_hint'])
        self.assertEqual(data['acquisition']['url'], '/profile/#conquistas')

    def test_shop_offers_must_be_active_and_not_demonstration(self):
        offer = dict(cosmetico__slug='tema-sample', active=False,
                     demonstration=False, amount=Decimal('12.00'))
        self.snapshot['cash'] = [offer]
        self.assertEqual(self.data()['acquisition']['url'], '')
        offer.update(active=True, demonstration=True)
        self.assertEqual(self.data()['acquisition']['url'], '')
        offer['demonstration'] = False
        data = self.data()
        self.assertTrue(data['locked'])
        self.assertEqual(data['acquisition']['url'], '/cosmetic_checkout/#cosmetic-offer-tema-sample')

    def test_theme_preview_separates_category_from_css_definition(self):
        self.snapshot['catalog']['tema-sample'].update(
            categoria='especial', css_url='/media/themes/sample.css',
            definicao={'accent': '#123456', 'categoria': 'especial', 'desbloqueio': {'secret': 'value'}})
        data = self.data()
        self.assertEqual(data['theme_category'], 'especial')
        self.assertEqual(data['theme_css_url'], '/media/themes/sample.css')
        self.assertEqual(data['theme_definition']['accent'], '#123456')
        self.assertNotIn('categoria', data['theme_definition'])
        self.assertNotIn('desbloqueio', data['theme_definition'])

    def test_inclusion_is_metadata_only_preserving_options_and_locks(self):
        options = [dict(key='none', label='None', **{'class': ''}, estado='livre'),
                   dict(key='sample', label='Sample', **{'class': 'effect-sample'}, estado='bloqueado',
                        posse_origem='Existing origin', unlock_hint='Existing condition', extra='kept'),
                   dict(key='locked', label='Locked', **{'class': ''}, locked=True)]
        before = deepcopy(options)
        with patch('home.templatetags.cosmetic_packages.load_package', side_effect=AssertionError):
            context = cosmetic_catalog(options, 'efeito', 'effect-id', 'effect-name',
                                       'sample', 'ficha', 'Effects', 'input-class')
        self.assertEqual(options, before)
        self.assertEqual([item['locked'] for item in context['items']], [False, True, True])
        self.assertEqual([item['selected'] for item in context['items']], [False, True, False])
        item = context['items'][1]
        self.assertEqual(item['extra'], 'kept')
        self.assertEqual(item['posse_origem'], 'Existing origin')
        self.assertEqual(item['unlock_hint'], 'Existing condition')
        self.assertEqual(item['preview_url'], '/perfil/cosmeticos/previa/?tipo=efeito&key=sample&escopo=ficha')
        self.assertTrue(all('package' not in item for item in context['items']))
        self.assertEqual(context['select_id'], 'effect-id')
        self.assertEqual(context['select_name'], 'effect-name')
        self.assertEqual(context['select_class'], 'input-class')
        self.registry.assert_called_once()
        self.read.assert_not_called()
        self.load.assert_not_called()

    def test_inclusion_root_preview_context_for_both_scopes_even_without_items(self):
        for escopo in ('perfil', 'ficha'):
            with self.subTest(escopo=escopo):
                context = cosmetic_catalog([], 'tema', 'theme-id', 'theme-name', escopo=escopo)
                self.assertEqual(context['preview_url'], reverse('cosmetic_picker_preview'))
                self.assertEqual(context['escopo'], escopo)
                self.assertEqual(context['items'], [])
        self.read.assert_not_called()
        self.load.assert_not_called()

    def test_thumbnail_paths_and_category_registry_are_validated(self):
        option = dict(key='sample', label='Sample', **{'class': ''})
        self.registry.return_value = {'moldura-sample': {
            'thumbnail': 'cosmetics/thumbs/sample.webp', 'category': 'especial'}}
        item = picker.picker_items([option], 'moldura', 'perfil')[0]
        self.assertEqual(item['thumbnail_url'], '/static/cosmetics/thumbs/sample.webp')
        self.assertEqual(item['category'], 'especial')
        for value in ('../sample.png', '/cosmetics/sample.png', 'cosmetics/../sample.png',
                      'cosmetics/%2e%2e/sample.png', 'https://host/sample.png', '//host/sample.png',
                      'cosmetics/sample.png?q=1', 'cosmetics/sample.webp#x',
                      'cosmetics/a\\b.png', 'cosmetics/sample.svg', 'cosmetics/sample.png\n'):
            with self.subTest(value=value):
                self.registry.return_value['moldura-sample'] = {'thumbnail': value, 'category': 'bad'}
                item = picker.picker_items([option], 'moldura', 'perfil')[0]
                self.assertEqual(item['thumbnail_url'], '')
                self.assertEqual(item['category'], 'classico')
        self.registry.return_value = {'moldura-sample': []}
        for asset, expected in [('/media/cosmetics/sample.png', '/media/cosmetics/sample.png'),
                                ('cosmetics/thumbs/sample.webp', '/static/cosmetics/thumbs/sample.webp'),
                                ('/media/../sample.png', ''), ('javascript:bad', ''),
                                ('https://host/sample.png', '')]:
            self.assertEqual(picker.picker_items([dict(option, asset_url=asset)], 'moldura', 'perfil')[0]
                             ['thumbnail_url'], expected)
        self.load.assert_not_called()
        self.read.assert_not_called()


class ThemeCategoryTests(SimpleTestCase):
    def test_catalog_sanitizer_preserves_only_supported_category(self):
        for category in ('classico', 'especial'):
            raw = {'accent': '#123456', 'categoria': category}
            self.assertEqual(cosmetics.sanitize_catalog_theme_definition(raw)['categoria'], category)
            self.assertNotIn('categoria', cosmetics.sanitize_definicao_tema(raw))
        for category in ('unknown', 'ESPECIAL', '', None, [], {}):
            with self.subTest(category=category), self.assertRaises(ValidationError):
                cosmetics.sanitize_catalog_theme_definition({'categoria': category})

    def test_classification_is_data_driven_without_slug_rules(self):
        self.assertEqual(cosmetics.theme_category({'class': 'theme-data skin-illustrated'}), 'especial')
        self.assertEqual(cosmetics.theme_category({'css_url': '/media/sample.css'}), 'especial')
        self.assertEqual(cosmetics.theme_category({'class': 'theme-bonfire'}), 'classico')
        self.assertEqual(cosmetics.theme_category({'categoria': 'classico', 'css_url': '/media/a.css'}), 'classico')
        self.assertEqual(cosmetics.theme_category({'definicao': {'categoria': 'especial'}}), 'especial')

    def test_load_and_options_keep_category_but_not_in_css(self):
        from home.models import TbCosmetico
        row = SimpleNamespace(slug='tema-sample', tipo='tema', nome='Sample', css_class='theme-data',
                              raridade='comum', animado=False, asset_efetivo='', origem='livre', preco=0,
                              requer_plano='', escopo='ambos', descricao='', css_file=None,
                              definicao_json={'categoria': 'especial', 'accent': '#123456'})
        with patch.object(cosmetics.cache, 'get', return_value=None), patch.object(cosmetics.cache, 'set'), patch.object(
                TbCosmetico, 'objects') as manager:
            manager.filter.return_value.order_by.return_value = [row]
            catalog = cosmetics._load_catalog('tema')
        self.assertEqual(catalog['sample']['categoria'], 'especial')
        self.assertNotIn('categoria', catalog['sample']['definicao'])
        with patch.object(cosmetics, 'get_catalog', return_value=catalog), patch.object(
                cosmetics, '_catalog_ownership', return_value=(set(), {})):
            options = cosmetics.catalog_options(None, 'tema', escopo='perfil', selected='sample')
        self.assertEqual(options[0]['categoria'], 'especial')
        self.assertEqual(options[0]['estado'], 'livre')
        self.assertTrue(options[0]['selected'])

    @override_settings(ROOT_URLCONF=__name__, STATIC_URL='/static/')
    def test_registry_special_is_not_masked_by_classic_fallback(self):
        from home.models import TbCosmetico
        row = SimpleNamespace(slug='tema-rank-obsidiana', tipo='tema', nome='Rank Obsidiana',
                              css_class='theme-data', raridade='comum', animado=False,
                              asset_efetivo='', origem='conquista', preco=None, requer_plano='',
                              escopo='ambos', descricao='', css_file=None,
                              definicao_json={'accent': '#123456', 'motif': 'facets'})
        for explicit, expected in [(None, 'especial'), ('classico', 'classico'), ('especial', 'especial')]:
            with self.subTest(explicit=explicit):
                row.definicao_json.pop('categoria', None)
                if explicit:
                    row.definicao_json['categoria'] = explicit
                with patch.object(cosmetics.cache, 'get', return_value=None), patch.object(
                        cosmetics.cache, 'set'), patch.object(TbCosmetico, 'objects') as manager:
                    manager.filter.return_value.order_by.return_value = [row]
                    catalog = cosmetics._load_catalog('tema')
                with patch.object(cosmetics, 'get_catalog', return_value=catalog), patch.object(
                        cosmetics, '_catalog_ownership', return_value=(set(), {})):
                    options = cosmetics.catalog_options(None, 'tema', escopo='perfil')
                with patch.object(picker, '_presentation_metadata', return_value={
                        row.slug: {'category': 'especial'}}):
                    listed = picker.picker_items(options, 'tema', 'perfil')[0]
                    preview = picker.picker_items([dict(catalog['rank-obsidiana'], key='rank-obsidiana')],
                                                  'tema', 'perfil')[0]
                self.assertEqual(listed['category'], expected)
                self.assertEqual(preview['category'], expected)
                self.assertEqual(options[0]['estado'], 'bloqueado')
                self.assertTrue(listed['locked'])

    def test_registry_is_single_bounded_read_and_optional(self):
        payload = json.dumps({'version': 1, 'items': {'tema-sample': {'category': 'especial'}}}).encode()
        source = mock_open(read_data=payload)
        with patch.object(picker, 'PRESENTATION_PATH', Mock(open=source)):
            self.assertEqual(picker._presentation_metadata()['tema-sample']['category'], 'especial')
        source().read.assert_called_once_with(picker._REGISTRY_LIMIT + 1)
        for invalid in (b'[]', b'null', b'{', b'{"version":true,"items":{}}',
                        b'{"version":2,"items":{}}', b'{"version":1,"items":[]}',
                        b'x' * (picker._REGISTRY_LIMIT + 1)):
            with self.subTest(invalid=invalid[:40]), patch.object(
                    picker, 'PRESENTATION_PATH', Mock(open=mock_open(read_data=invalid))):
                self.assertEqual(picker._presentation_metadata(), {})
        with patch.object(picker, 'PRESENTATION_PATH', Mock(open=Mock(side_effect=FileNotFoundError))):
            self.assertEqual(picker._presentation_metadata(), {})
