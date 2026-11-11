"""Visual selector contracts without database access or entitlement changes."""

from copy import deepcopy
from html.parser import HTMLParser
from unittest.mock import patch

from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase, override_settings

from home.templatetags.cosmetic_packages import cosmetic_catalog


def browser_fixture():
    """Render the real component and public art for the database-free browser test."""
    static = 'https://catalog.invalid/static/'
    frames = [
        {'key': 'none', 'label': 'Sem moldura', 'class': ''},
        {'key': 'ember-ring', 'label': 'Anel de brasas', 'class': 'frame-ember-ring'},
        {'key': 'arcane-pulse', 'label': 'Pulso arcano', 'class': 'frame-arcane-pulse',
         'posse_origem': 'Resgate de evento'},
        {'key': 'elo-diamante-fechada', 'label': 'Elmo de Diamante', 'class': '',
         'locked': True, 'unlock_hint': 'Alcance a patente Diamante'},
        {'key': 'gold-trim', 'label': 'Moldura dourada comemorativa de exploracao',
         'class': 'frame-gold-trim'},
    ]
    effects = [{'key': key, 'label': label, 'class': 'effect-' + key,
                'locked': key == 'starfall',
                'unlock_hint': 'Evento Estelar' if key == 'starfall' else ''}
               for key, label in [('none', 'Sem efeito'), ('soft-glow', 'Brilho suave'),
                                  ('glass', 'Vidro'), ('embers', 'Brasas'),
                                  ('aurora', 'Aurora'), ('starfall', 'Chuva de estrelas')]]
    template = Template("""{% load static cosmetic_packages %}
<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{% for file in styles %}<link rel="stylesheet" href="{% static file %}">{% endfor %}
<style>body{margin:0;padding:16px;background:#141517;color:#eee;font:14px Arial,sans-serif;--bg0:#141517;--bg1:#202226;--text:#eee;--muted:#bbbfc6;--stroke:#555b62;--accent:#ed8171}main{max-width:1000px;margin:auto}h1{font-size:22px}h2{font-size:18px}form{margin-bottom:24px}button{padding:8px;margin:12px 0}.profile-appearance-grid,.info-grid.appearance-controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}@media(max-width:600px){.profile-appearance-grid,.info-grid.appearance-controls{grid-template-columns:1fr}}</style>
<main><h1>Aparencia</h1><h2>Perfil</h2><form><div class="profile-appearance-grid">
<div class="profile-field">{% cosmetic_catalog frames 'moldura' 'id_avatar_frame' 'avatar_frame' 'none' 'perfil' 'Borda do Avatar' 'profile-input' %}</div>
<div class="profile-field">{% cosmetic_catalog effects 'efeito' 'id_profile_effect' 'profile_effect' 'none' 'perfil' 'Efeito do Perfil' 'profile-input' %}</div>
</div><button type="reset">Restaurar perfil</button></form>
<h2>Ficha</h2><form><div class="info-grid appearance-controls">
<div class="info-field">{% cosmetic_catalog frames 'moldura' 'ficha-frame-select' 'foto_frame' 'none' 'ficha' 'Moldura' %}</div>
<div class="info-field">{% cosmetic_catalog effects 'efeito' 'ficha-effect-select' 'ficha_effect' 'none' 'ficha' 'Efeito' %}</div>
</div><button type="reset">Restaurar ficha</button></form></main>
<script src="{% static 'cosmetics/renderer.js' %}" defer></script>
<script src="{% static 'js/cosmetic-catalog.js' %}" defer></script>
<script src="{% static 'js/profile-effects.js' %}" defer></script>
</html>""")
    with override_settings(STATIC_URL=static):
        return template.render(Context({'frames': frames, 'effects': effects, 'styles': [
            'css/pages/perfil.css', 'css/pages/perfil-fx.css', 'css/pages/ficha.css',
            'css/components/cosmetic-presentation.css', 'css/components/cosmetic-catalog.css',
            'css/components/profile-effects.css', 'css/components/profile-theme-motifs.css',
        ]}))


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class CosmeticCatalogTileTests(SimpleTestCase):
    def setUp(self):
        self.options = [
            {'key': 'none', 'label': 'Sem efeito', 'class': '', 'estado': 'livre'},
            {'key': 'aurora', 'label': 'Aurora', 'class': 'effect-aurora',
             'estado': 'possui', 'posse_origem': 'Resgate de evento'},
            {'key': 'glass', 'label': 'Vidro', 'class': 'effect-glass',
             'estado': 'bloqueado', 'unlock_hint': 'Patente Diamante'},
            {'key': 'embers', 'label': 'Brasas', 'class': 'effect-embers', 'locked': True},
        ]

    def test_public_previews_include_locked_art_without_mutating_options(self):
        before = deepcopy(self.options)
        with patch('home.templatetags.cosmetic_packages.load_package', return_value=None) as load:
            context = cosmetic_catalog(self.options, 'efeito', 'id_profile_effect',
                                       'profile_effect', 'aurora', 'perfil', 'Efeito')
        self.assertEqual(load.call_count, 4)
        load.assert_any_call('efeito', 'glass', 'perfil')
        self.assertEqual([item['locked'] for item in context['items']], [False, False, True, True])
        self.assertEqual([item['selected'] for item in context['items']], [False, True, False, False])
        self.assertEqual(self.options, before)

    def test_original_ids_names_values_and_locked_fallback_are_preserved(self):
        for select_id, name, scope in [
            ('id_avatar_frame', 'avatar_frame', 'perfil'),
            ('id_profile_effect', 'profile_effect', 'perfil'),
            ('ficha-frame-select', 'foto_frame', 'ficha'),
            ('ficha-effect-select', 'ficha_effect', 'ficha'),
        ]:
            with self.subTest(select_id=select_id), patch(
                'home.templatetags.cosmetic_packages.load_package', return_value=None
            ):
                kind = 'moldura' if 'frame' in select_id else 'efeito'
                context = cosmetic_catalog(self.options, kind, select_id, name, 'aurora', scope, 'Catalogo')
                html = get_template('home/includes/cosmetic_catalog.html').render(context)
                elements = Elements(html).elements
                select = next(attrs for tag, attrs in elements if tag == 'select')
                self.assertEqual((select['id'], select['name']), (select_id, name))
                self.assertNotIn('hidden', select)
                options = [attrs for tag, attrs in elements if tag == 'option']
                self.assertEqual([item['value'] for item in options], [item['key'] for item in self.options])
                self.assertIn('selected', options[1])
                self.assertIn('disabled', options[2])
                self.assertIn('disabled', options[3])
                controls = next(attrs for tag, attrs in elements if 'data-catalog-controls' in attrs)
                self.assertIn('hidden', controls)
                radios = [attrs for tag, attrs in elements if attrs.get('type') == 'radio']
                self.assertTrue(all(item['name'] == 'catalog_' + select_id for item in radios))
                self.assertIn('disabled', radios[2])
                self.assertIn('Bloqueado · Patente Diamante', html)
                self.assertIn('Resgate de evento', html)

    def test_inclusion_tag_renders_helmet_sprite_in_locked_frame(self):
        options = [{'key': 'helmet', 'label': 'Elmo', 'locked': True, 'class': 'frame-helmet'}]
        package = {'avatar': [{'motion': 'helmet', 'url': '/static/helmet.webp',
                              'fallback': '/static/helmet.png',
                              'aperture': {'cx': 50, 'cy': 45, 'diameter': 40}}]}
        with patch('home.templatetags.cosmetic_packages.load_package', return_value=package):
            html = Template("{% load cosmetic_packages %}{% cosmetic_catalog options 'moldura' 'frames' 'foto_frame' 'none' 'ficha' 'Moldura' %}").render(Context({'options': options}))
        self.assertIn('data-cosmetic-helmet', html)
        self.assertIn('cosmetic-helmet-open', html)
        self.assertIn('is-packaged', html)
        self.assertIn('disabled', html)
        self.assertIn('data-aperture-x="50.000"', html)
        self.assertIn('data-aperture-y="45.000"', html)
        self.assertIn('data-aperture-size="40.000"', html)

    def test_page_templates_compile(self):
        for path in ('home/base.html', 'home/pages/perfil.html', 'home/pages/ficha_detail.html'):
            get_template(path)
