import json
import shutil
import subprocess
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .cosmetics import invalidate_cosmetic_cache
from .models import TbCosmetico, TbPersonagem, TbUsuarioCosmetico, UserProfile
from .views import _appearance_context, _appearance_options, _data_theme_class


class ThemeSkinTokenTests(SimpleTestCase):
    def test_illustrated_catalogs_have_reusable_skin_tokens_and_separate_slots(self):
        from .cosmetics import sanitize_definicao_tema
        from .cosmetic_packages import load_package
        docs = Path(__file__).resolve().parent.parent / 'docs/cosmetics'
        for filename in ('lunar-themes-catalog.json', 'halloween-catalog.json'):
            catalog = json.loads((docs / filename).read_text(encoding='utf-8'))
            self.assertFalse(catalog['activate_in_production'])
            for item in catalog['cosmetics']:
                with self.subTest(slug=item['slug']):
                    self.assertEqual(item['tipo'], 'tema')
                    self.assertFalse(item['ativo'])
                    self.assertEqual(item['origem'], 'staff')
                    self.assertIn('skin-illustrated', _data_theme_class({'class': item['css_class']}))
                    colors = sanitize_definicao_tema(item['definicao_json'])
                    self.assertEqual(colors['particula'], 'nenhuma')
                    self.assertEqual(colors['motif'], 'none')
        for scope in ('perfil', 'ficha'):
            frame = load_package('moldura', 'vigilia-das-lanternas', scope)
            effect = load_package('efeito', 'vigilia-das-lanternas', scope)
            self.assertIsNotNone(frame)
            self.assertIsNotNone(effect)
            self.assertEqual(frame['avatar'][0]['aperture'], {'cx': 50, 'cy': 50, 'diameter': 70})
            self.assertEqual(frame['avatar'][0]['motion'], 'none')
            self.assertTrue(effect['overlay'])
            self.assertEqual(len(effect['banner']), 3)
            self.assertEqual(effect['ornament'], [])
            for layer in effect['banner']:
                self.assertIn('placement', layer)
                self.assertIn('mobile', layer)

    def test_restricted_tokens_deduplicate_and_reject_whole_invalid_value(self):
        self.assertEqual(_data_theme_class({'class': ' skin-any  variant_2 skin-any theme-data '}),
                         'theme-data skin-any variant_2')
        for value in (None, [], 'skin-ok bad:name', 'skin-ok; color:red',
                      'skin-ok" onclick="x', 'url(x)', '9skin', 'skin-\u00e1'):
            with self.subTest(value=value):
                self.assertEqual(_data_theme_class({'class': value}), 'theme-data')

    def test_all_pilot_compositions_remain_available(self):
        for key in ('forja-de-brasas', 'aurora-glacial', 'circulo-arcano'):
            for identifier in ({'slug': 'tema-' + key}, {'key': key}):
                self.assertEqual(_data_theme_class(dict(identifier, **{'class': 'theme-data'})),
                                 'theme-data collection-' + key)

    def test_real_swatch_script_transitions_and_authorized_sync(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for preview regression coverage')
        script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const catalog = ['skin-lua-vermelha', 'skin-lua-negra', 'skin-lua-cristal', 'generic-edge variant_2'];
const context = {window: {}, document: {querySelectorAll: () => catalog.map(temaClasse => ({dataset: {temaClasse}}))}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const swatch = context.window.TemaSwatch;
function target(className) {
  const vars = new Map(), attrs = new Map();
  const el = {className, children: [],
    style: {setProperty: (k,v) => vars.set(k,v), removeProperty: k => vars.delete(k), getPropertyValue: k => vars.get(k) || ''},
    setAttribute: (k,v) => attrs.set(k,v), removeAttribute: k => attrs.delete(k),
    hasAttribute: k => attrs.has(k), getAttribute: k => attrs.get(k), querySelector: () => null};
  el.classList = { [Symbol.iterator]: function* () {yield* el.className.split(/\s+/).filter(Boolean);},
    add: name => {if (!el.className.split(' ').includes(name)) el.className += ' ' + name;},
    remove: name => {el.className = el.className.split(' ').filter(c => c !== name).join(' ');}};
  return el;
}
const sheet = target('ficha theme-data skin-lua-vermelha effect-spark ficha-has-bg');
const theme = {chave: 'arbitrary', classe: '', accent: '#112233', accent2: '#445566', surface: '#121212', deep: '#090909', particula: 'nenhuma', vel: 'lenta'};
for (const classe of catalog) {
  swatch.aplica(sheet, {...theme, classe});
  for (const name of classe.split(' ')) assert(sheet.className.split(' ').includes(name));
  for (const name of catalog.flatMap(c => c.split(' ')).filter(c => !classe.split(' ').includes(c)))
    assert(!sheet.className.split(' ').includes(name), name);
  assert(sheet.className.includes('effect-spark ficha-has-bg'));
  assert.equal(sheet.style.getPropertyValue('--sheet-accent-solid'), '#112233');
  assert.equal(sheet.style.getPropertyValue('--profile-accent-solid'), '#112233');
}
swatch.aplica(sheet, {...theme, classe: 'skin-ok bad:token'});
assert(!sheet.className.includes('skin-ok'));
assert(sheet.className.includes('theme-data'));
for (const chave of ['forja-de-brasas', 'aurora-glacial', 'circulo-arcano']) {
  swatch.aplica(sheet, {...theme, chave, classe: 'theme-data'});
  assert(sheet.className.includes('collection-' + chave));
}
swatch.aplica(sheet, {...theme, chave: 'custom', classe: 'theme-custom'});
assert(!/skin-|collection-|generic-edge|variant_2/.test(sheet.className));
swatch.aplica(sheet, {chave: 'bonfire', classe: 'theme-bonfire'});
assert(!sheet.className.includes('theme-data'));
assert.equal(sheet.style.getPropertyValue('--sheet-accent'), '');
// Server-rendered initial classes must be replaceable before any aplica call.
const privateRoot = target('profile-page theme-data skin-lua-vermelha effect-old profile-has-bg');
const source = target('public-profile-page theme-data skin-lua-cristal effect-spark');
source.style.setProperty('--profile-accent-solid', '#abcdef');
swatch.syncAuthorizedPreview(source, privateRoot);
assert(privateRoot.className.includes('skin-lua-cristal'));
assert(!privateRoot.className.includes('skin-lua-vermelha'));
assert(!privateRoot.className.includes('effect-old'));
assert(privateRoot.className.includes('profile-has-bg'));
assert.equal(privateRoot.style.getPropertyValue('--profile-accent-solid'), '#abcdef');
swatch.syncAuthorizedPreview(target('public-profile-page theme-bonfire'), privateRoot);
assert(!privateRoot.className.includes('skin-lua-cristal'));
assert.equal(privateRoot.style.getPropertyValue('--profile-accent-solid'), '');
'''
        result = subprocess.run([node, '-e', script, str(Path(__file__).parent / 'static/js/tema_swatch.js')],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ThemeSkinCatalogTests(TestCase):
    def setUp(self):
        invalidate_cosmetic_cache()
        self.addCleanup(invalidate_cosmetic_cache)
        self.owner = get_user_model().objects.create_user('skin-owner')
        for key, css in (('bonfire', 'theme-bonfire'), ('custom', 'theme-custom')):
            TbCosmetico.objects.update_or_create(slug='tema-' + key, defaults={
                'nome': key, 'tipo': 'tema', 'origem': 'livre', 'ativo': True,
                'css_class': css, 'definicao_json': {}})
        self.themes = []
        for key in ('lua-vermelha', 'lua-negra', 'lua-cristal', 'arbitrary-edge'):
            self.themes.append(TbCosmetico.objects.create(
                slug='tema-' + key, nome=key, tipo='tema', origem='conquista',
                escopo='ambos', ativo=True, css_class='skin-' + key,
                definicao_json={'accent': '#112233', 'accent2': '#445566',
                                'surface': '#121212', 'deep': '#090909', 'particula': 'nenhuma'}))

    def grant(self, theme):
        TbUsuarioCosmetico.objects.create(user=self.owner, cosmetico=theme, origem='staff')

    def test_catalog_classes_in_both_scopes_and_options_without_effect_coupling(self):
        for theme in self.themes:
            self.grant(theme)
            key = theme.slug.removeprefix('tema-')
            for scope in ('perfil', 'ficha'):
                appearance = _appearance_context(key, user=self.owner, escopo=scope)
                self.assertEqual(appearance['theme_class'], 'theme-data ' + theme.css_class)
                self.assertEqual(appearance['effect_key'], 'none')
                self.assertIn('--sheet-accent-solid:#112233;', appearance['custom_style'])
                option = next(item for item in _appearance_options(self.owner, 'theme', scope)
                              if item['key'] == key)
                self.assertEqual(option['class'], appearance['theme_class'])
                with_effect = _appearance_context(key, effect='spark', user=self.owner, escopo=scope)
                self.assertEqual(with_effect['theme_class'], appearance['theme_class'])
                self.assertEqual(with_effect['custom_style'], appearance['custom_style'])

    def test_denied_suspended_and_wrong_scope_do_not_leak_skin(self):
        from django.utils import timezone
        theme = self.themes[0]
        self.assertEqual(_appearance_context('lua-vermelha', user=self.owner)['theme_class'], 'theme-bonfire')
        self.grant(theme)
        theme.escopo = 'perfil'
        theme.save()
        self.assertEqual(_appearance_context('lua-vermelha', user=self.owner, escopo='ficha')['theme_class'], 'theme-bonfire')
        TbUsuarioCosmetico.objects.filter(user=self.owner).update(suspenso_em=timezone.now())
        self.assertEqual(_appearance_context('lua-vermelha', user=self.owner)['theme_class'], 'theme-bonfire')

    def test_legacy_custom_and_invalid_data_class(self):
        self.assertEqual(_appearance_context('bonfire')['theme_class'], 'theme-bonfire')
        custom = _appearance_context('custom', theme_custom={'accent': '#abcdef'})
        self.assertEqual(custom['theme_class'], 'theme-custom')
        self.assertIn('#abcdef', custom['custom_style'])
        theme = self.themes[0]
        theme.css_class = 'skin-valid bad:token'
        theme.save()
        self.grant(theme)
        self.assertEqual(_appearance_context('lua-vermelha', user=self.owner)['theme_class'], 'theme-data')
        option = next(item for item in _appearance_options(self.owner, 'theme') if item['key'] == 'lua-vermelha')
        self.assertEqual(option['class'], 'theme-data')

    def test_profile_private_preview_and_character_render_use_catalog_skin(self):
        theme = self.themes[0]
        self.grant(theme)
        profile, _ = UserProfile.objects.get_or_create(user=self.owner)
        profile.profile_theme = 'lua-vermelha'
        profile.save()
        character = TbPersonagem.objects.create(dono=self.owner, nome='Skin test', ficha_theme='lua-vermelha')
        self.client.force_login(self.owner)
        for route, args in (('profile', []), ('ficha_detail', [character.pk])):
            response = self.client.get(reverse(route, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['appearance']['theme_class'], 'theme-data skin-lua-vermelha')
            self.assertContains(response, 'data-tema-classe="theme-data skin-lua-vermelha"')
        for theme in self.themes[:3]:
            if theme != self.themes[0]:
                self.grant(theme)
            response = self.client.post(reverse('perfil_preview'), {'profile_theme': theme.slug[5:]})
            self.assertEqual(response.status_code, 200)
            self.assertIn('theme-data ' + theme.css_class, response.json()['html'])
            self.assertEqual(response.json()['recusados'], [])
        profile.refresh_from_db()
        character.refresh_from_db()
        self.assertEqual(profile.profile_theme, 'lua-vermelha')
        self.assertEqual(character.ficha_theme, 'lua-vermelha')
