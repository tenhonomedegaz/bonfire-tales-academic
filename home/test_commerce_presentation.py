from types import SimpleNamespace
from unittest.mock import patch

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings

from home.templatetags.commerce_presentation import shop_type, shop_visual


class CommercePresentationTests(SimpleTestCase):
    def test_type_labels_and_template_tag_are_presentation_only(self):
        self.assertEqual(shop_type('moldura'), 'Moldura')
        self.assertEqual(shop_type('unknown'), 'Cosmético')
        rendered = Template(
            '{% load commerce_presentation %}{% shop_visual cosmetic as visual %}'
            '{{ visual.kind }}|{{ visual.exact }}'
        ).render(Context({'cosmetic': SimpleNamespace(tipo='titulo')}))
        self.assertEqual(rendered, 'titulo|False')

    @override_settings(STATIC_URL='/static/')
    def test_manifest_art_is_static_and_does_not_check_entitlement(self):
        cosmetic = SimpleNamespace(tipo='moldura', slug='moldura-ember-ring')
        with patch('home.cosmetic_packages.cosmetic_allowed',
                   side_effect=AssertionError('ownership lookup')):
            visual = shop_visual(cosmetic)
        self.assertEqual(visual, {
            'kind': 'moldura',
            'image': '/static/cosmetics/ember-ring.svg',
            'glyph': '',
            'exact': True,
        })

    def test_badges_accept_safe_media_or_short_glyphs_only(self):
        self.assertEqual(shop_visual(SimpleNamespace(
            tipo='badge', asset_efetivo='/media/badges/ember.png')), {
            'kind': 'badge', 'image': '/media/badges/ember.png',
            'glyph': '', 'exact': True,
        })
        self.assertEqual(shop_visual(SimpleNamespace(
            tipo='badge', asset_efetivo='✦')), {
            'kind': 'badge', 'image': '', 'glyph': '✦', 'exact': True,
        })
        for value in ('javascript:alert(1)', 'data:image/svg+xml,x',
                      '//evil.example/badge.svg', '<script>'):
            visual = shop_visual(SimpleNamespace(tipo='badge', asset_efetivo=value))
            self.assertEqual(visual['image'], '')
            self.assertEqual(visual['glyph'], '')
            self.assertFalse(visual['exact'])
