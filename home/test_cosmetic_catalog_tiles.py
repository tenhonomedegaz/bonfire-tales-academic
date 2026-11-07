"""On-demand catalog presentation with bounded settings and no database."""
import json
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase, override_settings


def component(items, kind='moldura', select_id='id_avatar_frame', name='avatar_frame', scope='perfil'):
    return get_template('home/includes/cosmetic_catalog.html').render({
        'items': items, 'tipo': kind, 'select_id': select_id, 'select_name': name,
        'escopo': scope, 'label': {'tema': 'Tema', 'moldura': 'Moldura', 'efeito': 'Efeito'}[kind],
        'select_class': 'profile-input', 'preview_url': '/catalog-preview/',
    })

def fixture_items():
    return [
        {'key': 'none', 'label': 'Sem moldura', 'class': '', 'locked': False, 'selected': True,
         'category': 'classico', 'thumbnail_url': '/static/brand/icon.png'},
        {'key': 'ember-ring', 'label': 'Anel de brasas', 'class': 'frame-ember-ring',
         'locked': False, 'category': 'classico', 'thumbnail_url': '/static/cosmetics/ember-ring.svg'},
        {'key': 'elo-diamante-fechada', 'label': 'Elmo de Diamante', 'class': '',
         'locked': True, 'category': 'especial', 'unlock_hint': 'Alcance a patente Diamante',
         'thumbnail_url': '/static/cosmetics/arcane-ring.svg'},
    ]

def browser_fixture():
    from home.cosmetic_packages import load_package
    frames = fixture_items()
    frames.append(dict(frames[1], key='gold-trim', label='Moldura dourada'))
    effects = [dict(item, key=key, label=label, **{'class': 'effect-' + key})
               for item, key, label in zip(frames, ['none', 'glass', 'starfall'],
                                          ['Sem efeito', 'Vidro', 'Chuva de estrelas'])]
    themes = [dict(frames[0], key='ember', label='Brasas', **{'class': 'theme-ember'}),
              dict(frames[1], key='custom', label='Personalizado', **{'class': 'theme-custom'}),
              dict(frames[2], key='exclusive', label='Aurora especial', **{'class': 'theme-arcane'}),
              dict(frames[1], key='rank-but-classic', label='Bosque', **{'class': 'theme-verdant'})]
    themes.append(dict(frames[1], key='owned-special', label='Especial adquirido',
                       category='especial', **{'class': 'theme-arcane skin-owned-fixture'}))
    html = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    for file in ['css/pages/perfil.css', 'css/pages/perfil-fx.css',
                 'css/components/cosmetic-presentation.css', 'css/components/cosmetic-catalog.css']:
        html += '<link rel="stylesheet" href="/static/' + file + '">'
    html += '<style>body{margin:0;padding:24px;background:#17181d;color:#eee;font:14px Arial,sans-serif;--text:#eee;--stroke:#494b55;--bg1:#25262d}main{max-width:980px;margin:auto}h1{font-size:22px}h2{font-size:16px;margin-top:32px}button{font:inherit}form{margin:24px 0}.fixture-fields{display:none}.profile-appearance-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}@media(max-width:600px){body{padding:16px}.profile-appearance-grid{grid-template-columns:1fr}}</style></head><body><main><h1>Aparência do perfil</h1><form id="perfil-form"><div class="fixture-fields"><input name="username" value="Aventureira"><input name="avatar_url" value="/static/brand/icon.png"><input name="banner_url" value="/static/cosmetics/arcane-banner.svg"><input name="custom_accent" value="#ee7766"><input name="custom_accent2" value="#44ccaa"><input name="custom_surface" value="#282831"><input name="custom_deep" value="#17181d"></div><div class="profile-cosmetic-launchers">'
    html += component(themes, 'tema', 'id_profile_theme', 'profile_theme')
    html += component(frames)
    html += component(effects, 'efeito', 'id_profile_effect', 'profile_effect')
    html += '</div><button type="submit" id="save-profile">Salvar Perfil</button><button type="reset">Restaurar</button></form><h2>Ficha</h2><form><div class="profile-appearance-grid">'
    html += component(frames, 'moldura', 'ficha-frame-select', 'foto_frame', 'ficha')
    html += component(effects, 'efeito', 'ficha-effect-select', 'ficha_effect', 'ficha')
    html += '</div></form></main><script src="/static/cosmetics/renderer.js" defer></script><script src="/static/js/tema_swatch.js" defer></script><script src="/static/js/cosmetic-catalog.js" defer></script></body></html>'
    html = html.replace('<main>', '<div id="profile-root" class="profile-page theme-ember skin-current-fixture" data-theme-category="especial" hidden></div><main>', 1)
    previews = {}
    for kind, items in [('tema', themes), ('moldura', frames), ('efeito', effects)]:
        for item in items:
            previews[kind + ':' + item['key']] = {
                'key': item['key'], 'tipo': kind, 'label': item['label'],
                'description': 'Uma presença para sua jornada.', 'locked': item.get('locked', False),
                'unlock_hint': item.get('unlock_hint', ''),
                'acquisition': {'label': 'Conhecer benefícios', 'url': '/colaborador/'},
                'package': load_package(kind, item['key']), 'css_class': item['class'],
                'theme_definition': {'accent': '#a76859', 'accent2': '#5ea99c', 'surface': '#2a2427', 'deep': '#17181d'},
                'theme_css_url': '', 'theme_category': item.get('category', 'classico'),
                'thumbnail_url': item['thumbnail_url'],
            }
    return {'html': html, 'previews': previews}

class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.elements = []; self.feed(html)
    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

@override_settings(STATIC_URL='/static/', ROOT_URLCONF='home.test_cosmetic_picker')
class CosmeticCatalogTileTests(SimpleTestCase):
    def test_real_tag_uses_item_preview_url_without_loading_any_packages(self):
        from home.templatetags.cosmetic_packages import cosmetic_catalog
        with patch('home.cosmetic_picker.reverse', return_value='/catalog-preview/'), patch(
                'home.templatetags.cosmetic_packages.load_package', side_effect=AssertionError('eager package')):
            context = cosmetic_catalog(fixture_items(), 'moldura', 'ficha-frame-select',
                                       'foto_frame', 'none', 'ficha', 'Moldura')
        html = get_template('home/includes/cosmetic_catalog.html').render(context)
        root = next(attrs for tag, attrs in Elements(html).elements if 'data-cosmetic-catalog' in attrs)
        self.assertEqual(root['data-catalog-url'], context['preview_url'])
        self.assertEqual(root['data-catalog-scope'], context['escopo'])
        self.assertEqual(context['escopo'], 'ficha')
        self.assertNotIn('data-cosmetic-layers', html)

    def test_native_ids_names_selection_and_disabled_options_are_preserved(self):
        for select_id, name, scope in [('id_avatar_frame', 'avatar_frame', 'perfil'),
                                       ('id_profile_theme', 'profile_theme', 'perfil'),
                                       ('ficha-frame-select', 'foto_frame', 'ficha')]:
            html = component(fixture_items(), select_id=select_id, name=name, scope=scope)
            elements = Elements(html).elements
            select = next(attrs for tag, attrs in elements if tag == 'select')
            self.assertEqual((select['id'], select['name']), (select_id, name))
            self.assertNotIn('hidden', select)
            options = [attrs for tag, attrs in elements if tag == 'option']
            self.assertIn('selected', options[0]); self.assertIn('disabled', options[2])
            root = next(attrs for tag, attrs in elements if 'data-cosmetic-catalog' in attrs)
            self.assertEqual(root['data-catalog-scope'], scope)

    def test_closed_catalog_is_static_and_locked_tiles_are_previewable(self):
        items = fixture_items(); before = deepcopy(items)
        html = component(items)
        self.assertEqual(items, before)
        self.assertNotIn('data-cosmetic-layers', html)
        self.assertNotIn('_cosmetic_preview', html)
        self.assertNotIn('type="radio"', html)
        tiles = [attrs for tag, attrs in Elements(html).elements if 'data-catalog-tile' in attrs]
        self.assertEqual(len(tiles), 3)
        self.assertTrue(all('disabled' not in tile for tile in tiles))
        self.assertEqual(tiles[2]['aria-label'], 'Elmo de Diamante · Bloqueado')
        self.assertIn('data-catalog-preview></div>', html)
        self.assertIn('data-catalog-apply disabled', html)

    def test_dialog_labels_and_launcher_are_accessible(self):
        elements = Elements(component(fixture_items())).elements
        dialog = next(attrs for tag, attrs in elements if tag == 'dialog')
        self.assertNotIn('open', dialog)
        self.assertEqual(dialog['aria-labelledby'], 'id_avatar_frame-dialog-title')
        launcher = next(attrs for tag, attrs in elements if 'data-catalog-open' in attrs)
        self.assertEqual(launcher['aria-haspopup'], 'dialog')
        self.assertEqual(launcher['aria-controls'], dialog['id'])
        self.assertEqual(launcher['type'], 'button')

    def test_theme_category_is_data_not_key_based(self):
        items = [dict(fixture_items()[0], key='rank-but-classic', category='classico'),
                 dict(fixture_items()[1], key='ordinary-name', category='especial')]
        html = component(items, 'tema')
        tiles = [attrs for tag, attrs in Elements(html).elements if 'data-catalog-tile' in attrs]
        self.assertEqual([tile['data-catalog-item-category'] for tile in tiles], ['classico', 'especial'])
        self.assertIn('Clássicos', html); self.assertIn('Especiais', html)

    def test_untrusted_labels_are_escaped(self):
        items = [dict(fixture_items()[0], label='<script>alert(1)</script>" onfocus="x')]
        html = component(items)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('onfocus', next(attrs for tag, attrs in Elements(html).elements if 'data-catalog-tile' in attrs))

    def test_profile_has_exactly_three_catalogs_without_eager_side_preview(self):
        source = (Path(__file__).parent / 'templates/home/pages/perfil.html').read_text(encoding='utf-8')
        self.assertEqual(source.count('{% cosmetic_catalog '), 3)
        self.assertIn("'id_profile_theme' 'profile_theme'", source)
        self.assertIn('data-theme-category="{{ appearance.theme_category|default:', source)
        self.assertNotIn('id_profile_theme_group', source)
        self.assertNotIn('perfil-preview-pane', source)
        self.assertNotIn('atualizaPrevia', source)
        for name in ['avatar_file', 'banner_file', 'custom_accent', 'clear_locked_avatar_frame']:
            self.assertIn('name="' + name + '"', source)
        get_template('home/pages/perfil.html')
