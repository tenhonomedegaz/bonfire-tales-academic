import json
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .bestiary_catalog import TYPE_LABELS, cr_components, creature_type_icons
from .models import TbBestiario, TbOrganizacao
from .organization_presentation import organization_presentation
from .views import _organization_catalog_payload


def browser_fixture(kind):
    """Render real page templates offline, without accounts, database or remote art."""
    from django.contrib.auth.models import AnonymousUser
    from django.template.loader import render_to_string
    from django.test import RequestFactory, override_settings
    from .views import _statblock_display_full
    request = RequestFactory().get('/' + kind + '/')
    request.user = AnonymousUser()
    base = '''{% load static %}<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>:root{--stroke:#42434a;--bg0:#0a0a0c;--bg1:#16161a;--text:#ececf0;--muted:#b4b6c0;--ember:#f69d65;--spark:#e0b787;--bft-header-height:57px}*{box-sizing:border-box}body{margin:0;background:var(--bg0);color:var(--text);font-family:Arial,sans-serif}main{width:100%;max-width:1320px;margin:auto;padding:24px}button,input,select{font:inherit}button{cursor:pointer}a{color:inherit;text-decoration:none}img{max-width:100%}svg{max-width:100%}.be-type-icon{max-width:18px}.h-6{width:24px;height:24px}.hidden{display:none!important}[hidden]{display:none!important}header.fixture-top{height:57px;padding:16px 24px;border-bottom:1px solid var(--stroke)}@media(max-width:600px){main{padding:14px}}</style>
    <script src="/static/js/markdown.js"></script>{% block extra_head %}{% endblock %}</head><body class="{% block body_class %}{% endblock %}"><header class="fixture-top">Bonfire Tales RPG</header><main>{% block content %}{% endblock %}</main></body></html>'''
    templates = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': False,
        'OPTIONS': {'loaders': [('django.template.loaders.locmem.Loader', {'home/base.html': base}),
                               'django.template.loaders.app_directories.Loader'],
                    'libraries': {'editorial_images': 'home.templatetags.editorial_images'}}}]
    context = {'request': request}
    if kind == 'organizations':
        text = '![Emblema](/static/img/bestiary/aboleth-art.png)\n\n## Historia e tradicoes\n\n**Uma sociedade independente** com registros preservados.\n\n- Vigiar os caminhos\n- Manter os arquivos\n\n'
        text += '\n\n'.join('Os membros compartilham relatos de expedicoes e discutem novas rotas. ' * 4 for _ in range(12))
        items = [_organization_catalog_payload({'Nome': f'Companhia dos Caminhos {index:02}',
            'Slug': f'companhia-{index:02}', 'Tipo': 'Guilda', 'Sede': 'Porto Norte',
            'Regioes': ['Cineria'], 'Lideranca': 'Conselho dos cartografos',
            'Descricao': text if index == 0 else '## Outra companhia\n\n**Registro independente**.'})
            for index in range(20)]
        context.update(kind='organizacoes', title='Organizacoes', subtitle='Guildas e sociedades de Cineria.',
                       items=items, can_edit_wiki=False)
        template = 'home/pages/catalogo.html'
    else:
        rows = []
        for index, (name, creature_type, raw) in enumerate((
            ('Cartografo arcano', 'Humanoid (wizard)', '4 (XP 1.100; PB +2)'),
            ('Guardiao dos arquivos', 'Undead', 'None (XP 0; PB equals your bonus)'),
        ), 1):
            block = {'name': name, 'size': ['M'], 'type': creature_type, 'cr': raw,
                     'hp': {'average': 38, 'formula': '7d8+7'}, 'ac': [14],
                     'speed': {'walk': 30}, 'str': 12, 'dex': 14, 'con': 12,
                     'int': 16, 'wis': 12, 'cha': 10}
            challenge = cr_components(raw, block)
            sheet = _statblock_display_full(block)
            sheet.update(cr=challenge['nd'], xp=challenge['xp'], pb=challenge['pb'])
            rows.append({'id': index, 'nome': name, 'slug': f'creature-{index}',
                         'tipo': creature_type, 'type_icons': creature_type_icons(creature_type),
                         'tamanho': 'Medio', 'nd': challenge['nd'], 'xp': challenge['xp'],
                         'pb': challenge['pb'], 'nd_source': raw, 'sb': sheet,
                         'imagem': '/static/img/bestiary/aboleth-art.png', 'art': {}, 'usages': []})
        context.update(criaturas=rows, active_creature_id=1, total_criaturas=2,
                       page_count=1, request=request, ordem='az')
        template = 'home/pages/bestiario.html'
    with override_settings(TEMPLATES=templates):
        return render_to_string(template, context, request=request)


class CatalogPresentationTests(SimpleTestCase):
    def test_feature_decoration_receives_source_for_normalized_and_legacy_sections(self):
        from .views import _statblock_display_full
        source = {'name': 'Spell ability', 'entries': ['Text'], 'tags': ['spell'],
                  'spell_refs': [{'slug': 'feather-fall'}]}
        def decorate(feature, original):
            self.assertIs(original, source)
            return dict(feature, spell_text_html='Decorated')
        with patch('home.bestiary_spell_text.decorate_spell_text', side_effect=decorate):
            for key in ('reaction', 'reactions', 'trait', 'traits', 'action', 'actions'):
                result = _statblock_display_full({key: [source]})
                target = 'reactions' if key.startswith('reaction') else 'traits' if key.startswith('trait') else 'actions'
                self.assertEqual(result[target][0]['spell_text_html'], 'Decorated')

    def test_cr_fields_preserve_source_and_explicit_values_without_inference(self):
        for raw, nd, xp, pb in (
            ('4 (XP 1.100; PB +2)', '4', '1.100', '+2'),
            ('1/4 (XP 50; PB +2)', '1/4', '50', '+2'),
            ('2 (450 XP; PB +2)', '2', '450', '+2'),
            ('None (XP 0; PB equals your bonus)', 'Sem ND fixo', '0', 'equals your bonus'),
            ('0 (XP 10)', '0', '10', ''),
            ('17', '17', '', ''),
            ('Varies with summoner', 'Varies with summoner', '', ''),
            (None, 'pendente', '', ''),
        ):
            with self.subTest(raw=raw):
                parsed = cr_components(raw)
                self.assertEqual((parsed['nd'], parsed['xp'], parsed['pb']), (nd, xp, pb))
                self.assertEqual(parsed['source'], raw or '')
        parsed = cr_components('4 (aquatic; XP 1,100; PB +2)')
        self.assertEqual(parsed['notes'], 'aquatic')
        self.assertEqual(cr_components('1', {'cr': {'cr': '1', 'xp': 200}, 'pb': '+2'})['xp'], '200')

    def test_creature_type_icons_cover_all_types_aliases_and_unknown(self):
        for kind, label in TYPE_LABELS.items():
            self.assertEqual(creature_type_icons(kind)[0]['label'], label)
            self.assertTrue(creature_type_icons(kind)[0]['paths'])
        self.assertEqual(creature_type_icons('undead')[0]['key'], 'morto-vivo')
        self.assertEqual(creature_type_icons('Humanoid (wizard)')[0]['key'], 'humanoide')
        self.assertEqual(creature_type_icons('unknown')[0]['key'], 'pending')
        self.assertEqual(len(creature_type_icons('planta ou besta')), 2)

    def test_organization_markdown_image_and_encoded_text_are_projected_not_rewritten(self):
        text = '![Selo](/static/img/bestiary/aboleth-art.png)\n\n## Historia\n\n**Texto** com lista:\n\n- Um\n- Dois'
        result = organization_presentation(json.dumps(text))
        self.assertEqual(result['descricao'], text)
        self.assertEqual(result['imagem'], '/static/img/bestiary/aboleth-art.png')
        self.assertEqual(result['imagem_alt'], 'Selo')
        self.assertNotIn('![Selo]', result['descricao_leitura'])
        self.assertIn('**Texto**', result['descricao_leitura'])
        self.assertEqual(organization_presentation(text, 'javascript:alert(1)')['imagem'], result['imagem'])
        self.assertEqual(organization_presentation('![](javascript:alert(1))')['imagem'], '')
        explicit = _organization_catalog_payload({'Nome': 'Guilda', 'ImagemUrl': '/media/org.png', 'Descricao': 'Historia'})
        self.assertEqual(explicit['imagem'], '/media/org.png')
        self.assertEqual(explicit['descricao_leitura'], 'Historia')


class CatalogReadabilityViewTests(TestCase):
    def test_creature_cards_and_sheet_separate_cr_xp_pb_without_writing(self):
        raw = '4 (XP 1.100; PB +2)'
        creature = TbBestiario.objects.create(nome='Generic creature', slug='generic-creature',
            tipo='Humanoid (wizard)', nd=raw, statblock_json={'cr': raw, 'hp': {'average': 20}})
        response = self.client.get(reverse('bestiario'))
        self.assertEqual(response.status_code, 200)
        data = response.context['criaturas'][0]
        self.assertEqual((data['nd'], data['xp'], data['pb']), ('4', '1.100', '+2'))
        self.assertEqual(data['sb']['cr'], '4')
        self.assertContains(response, '<b aria-hidden="true">4</b>', html=True)
        self.assertContains(response, 'data-creature-type="humanoide"')
        self.assertContains(response, '<dt>XP</dt><dd>1.100</dd>', html=True)
        self.assertNotContains(response, 'class="be-challenge-meta"')
        self.assertContains(response, '<dt>Bônus de Proficiência (PB)</dt><dd>+2</dd>', html=True)
        creature.refresh_from_db()
        self.assertEqual(creature.nd, raw)
        self.assertEqual(creature.statblock_json['cr'], raw)

    def test_organization_reader_uses_existing_markdown_art_and_scoped_layout(self):
        description = '![Org](/static/img/bestiary/aboleth-art.png)\n\n## Historia\n\n**Texto**'
        organization = TbOrganizacao.objects.create(nome='Guilda da Leitura', slug='guilda-da-leitura',
                                                   descricao=description)
        response = self.client.get(reverse('mundo_organizacoes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'catalog-shell--organizations')
        self.assertContains(response, 'css/pages/organizations.css')
        item = response.context['items'][0]
        self.assertEqual(item['imagem'], '/static/img/bestiary/aboleth-art.png')
        self.assertIn('## Historia', item['descricao_leitura'])
        self.assertContains(response, 'data-markdown-source')
        organization.refresh_from_db()
        self.assertEqual(organization.descricao, description)
