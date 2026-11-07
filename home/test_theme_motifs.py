from pathlib import Path

from django.contrib.auth import get_user_model
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase, TestCase

from .cosmetics import THEME_MOTIFS, invalidate_cosmetic_cache, sanitize_definicao_tema
from .models import TbCosmetico, TbUsuarioCosmetico
from .views import _appearance_context


ROOT = Path(__file__).resolve().parent


def browser_fixture():
    """Real swatch partial and CSS in a disposable, account-free browser fixture."""
    from .views import _theme_vars_style
    definition = sanitize_definicao_tema({'accent': '#34d399', 'accent2': '#059669',
        'surface': '#141418', 'deep': '#09090c', 'particula': 'nenhuma', 'motif': 'leaves'})
    cards = ''.join(render_to_string('home/includes/tema_swatch_card.html', {
        'key': motif, 'item': {'label': motif.title(), 'class': 'theme-data'},
        'd': dict(definition, motif=motif), 'input_name': 'theme', 'input_id': f'motif-{motif}',
    }) for motif in THEME_MOTIFS)
    styles = ''.join(f'<link rel="stylesheet" href="{(ROOT / "static" / path).as_uri()}">'
        for path in ('css/pages/perfil.css', 'css/components/tema_swatch.css',
                     'css/pages/profile-redesign.css', 'css/components/profile-theme-motifs.css'))
    portrait = (ROOT / 'static/cosmetics/rank-obsidiana-v3.png').as_uri()
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{styles}
    <style>body{{--bft-header-height:0px;--stroke:#45454c;--bg0:#09090c;--bg1:#141418;--text:#f3f3f5;margin:0;background:#09090c;color:#f3f3f5;font-family:Arial}}
    main{{max-width:1080px;padding:20px;margin:auto}}*{{box-sizing:border-box}}img{{max-width:100%}}
    .fixture-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:14px;margin-top:22px}}
    .fixture-grid>section,.fixture-grid>article{{min-width:0;margin:0;padding:0}}
    .fixture-grid :is(.public-profile-banner,.ficha-header){{min-height:156px;border:1px solid #45454c;border-radius:3px;background-color:#141418;padding:18px}}
    .fixture-grid h2{{font-size:19px;line-height:1.4;overflow-wrap:anywhere}}
    .profile-save-bar{{margin-top:12px!important}}.tema-swatch-grid{{margin-top:24px}}
    @media(max-width:600px){{main{{padding:12px}}.profile-header.profile-hero{{padding:18px!important;gap:14px!important}}.profile-username{{font-size:25px!important}}}}
    </style></head><body class="bft-profile"><main>
    <div class="profile-page theme-data" id="profile-root" data-theme-motif="leaves" style="{_theme_vars_style(definition)}">
      <header class="profile-header profile-hero"><img src="{portrait}" alt="Retrato de teste" width="76" height="76"><div class="profile-hero-copy"><h1 class="profile-username">Perfil de teste</h1><p class="profile-bio-preview">Tema independente de patente.</p></div></header>
      <nav class="profile-nav"><a href="#themes">Identidade</a><a href="#themes">Aparencia</a></nav>
      <div class="profile-save-bar"><span>Alteracoes do perfil</span><button class="profile-btn">Salvar alteracoes</button></div>
    </div>
    <div class="fixture-grid"><section class="public-profile-page theme-data" data-theme-motif="leaves" style="{_theme_vars_style(definition)}"><header class="public-profile-banner"><h2>Perfil publico</h2></header></section>
    <section class="ficha theme-data" data-theme-motif="leaves" style="{_theme_vars_style(definition)}"><header class="ficha-header"><h2>Ficha privada</h2></header></section>
    <article class="ficha theme-data" data-theme-motif="leaves" style="{_theme_vars_style(definition)}"><header class="ficha-header"><h2>Ficha publica</h2></header></article></div>
    <div class="tema-swatch-grid" id="themes" role="radiogroup" aria-label="Motivos">{cards}</div>
    </main><script src="{(ROOT / 'static/js/tema_swatch.js').as_uri()}"></script>
    <script>document.querySelector('#themes').addEventListener('change',event=>{{const theme=TemaSwatch.leCartao(event.target);document.querySelectorAll('[data-theme-motif]').forEach(target=>TemaSwatch.aplica(target,theme));}});</script></body></html>'''


class ThemeMotifSanitizerTests(SimpleTestCase):
    def test_allowlisted_motifs_are_data_not_rank_branches(self):
        for motif in THEME_MOTIFS:
            self.assertEqual(sanitize_definicao_tema({'motif': motif})['motif'], motif)

    def test_invalid_or_missing_motif_is_none_and_empty_definition_stays_empty(self):
        for invalid in (None, [], {}, 1, True, 'unknown', 'SUN', 'moon" onmouseover="x', 'url(x)'):
            self.assertEqual(sanitize_definicao_tema({'motif': invalid})['motif'], 'none')
        self.assertEqual(sanitize_definicao_tema({'accent': '#112233'})['motif'], 'none')
        self.assertEqual(sanitize_definicao_tema({}), {})
        self.assertEqual(sanitize_definicao_tema(None), {})

    def test_swatch_uses_sanitized_motif(self):
        html = render_to_string('home/includes/tema_swatch_card.html', {
            'key': 'arbitrary-theme', 'item': {'label': 'Theme', 'class': 'theme-data'},
            'd': sanitize_definicao_tema({'motif': 'leaves'}), 'input_name': 'profile_theme',
            'input_id': 'test-theme',
        })
        self.assertIn('data-motif="leaves"', html)

    def test_roots_and_single_css_include_are_wired(self):
        for path in ('pages/perfil.html', 'partials/_perfil_publico_hero.html',
                     'pages/ficha_detail.html', 'pages/ficha_publica.html'):
            source = (ROOT / 'templates/home' / path).read_text(encoding='utf-8')
            self.assertIn('data-theme-motif="{{ appearance.theme_motif', source)
            get_template('home/' + path)
        base = (ROOT / 'templates/home/base.html').read_text(encoding='utf-8')
        self.assertEqual(base.count('profile-theme-motifs.css'), 1)
        self.assertLess(base.index('profile-effects.css'), base.index('profile-theme-motifs.css'))


class ThemeMotifContextTests(TestCase):
    def setUp(self):
        invalidate_cosmetic_cache()
        self.addCleanup(invalidate_cosmetic_cache)
        self.owner = get_user_model().objects.create_user('theme-motif-owner')
        TbCosmetico.objects.update_or_create(slug='tema-bonfire', defaults={
            'tipo': 'tema', 'nome': 'Basal', 'origem': 'livre', 'css_class': 'theme-bonfire',
            'definicao_json': {}, 'ativo': True})
        self.theme = TbCosmetico.objects.create(
            slug='tema-independent-motif', nome='Independent motif', tipo='tema',
            origem='conquista', escopo='ambos', css_class='theme-data',
            definicao_json={'accent': '#34d399', 'motif': 'leaves'})

    def test_owned_theme_exports_motif_and_unowned_theme_does_not(self):
        denied = _appearance_context('independent-motif', user=self.owner)
        self.assertEqual(denied['theme_key'], 'bonfire')
        self.assertEqual(denied['theme_motif'], 'none')
        TbUsuarioCosmetico.objects.create(user=self.owner, cosmetico=self.theme, origem='staff')
        for motif in THEME_MOTIFS:
            self.theme.definicao_json['motif'] = motif
            self.theme.save()
            for scope in ('perfil', 'ficha'):
                appearance = _appearance_context('independent-motif', user=self.owner, escopo=scope)
                self.assertEqual(appearance['theme_motif'], motif)
                self.assertIn('--profile-accent-solid:#34d399;', appearance['custom_style'])

    def test_suspended_theme_has_no_motif_and_legacy_is_unchanged(self):
        from django.utils import timezone
        TbUsuarioCosmetico.objects.create(user=self.owner, cosmetico=self.theme,
                                        origem='staff', suspenso_em=timezone.now())
        self.assertEqual(_appearance_context('independent-motif', user=self.owner)['theme_motif'], 'none')
        legacy = _appearance_context('bonfire', user=self.owner)
        self.assertEqual(legacy['theme_motif'], 'none')
        self.assertEqual(legacy['custom_style'], '')
