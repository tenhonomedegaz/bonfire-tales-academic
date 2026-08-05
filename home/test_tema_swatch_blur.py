# -*- coding: utf-8 -*-
"""SELETOR DE TEMA POR PRÉVIA VISUAL + DESFOQUE DO PAINEL CENTRAL.

Dois pedidos do PO cobertos aqui:

1. "o ideal é não ter o NOME do tema pra escolher e sim uma PRÉVIA do tema, e ao
   escolher muda em tempo real" — o seletor (perfil E ficha) é uma grade de
   CARTÕES-PRÉVIA, um por tema do catálogo, pintados com a definicao_json de cada
   tema (data-* + CSS vars no style). O nome vira legenda. As semânticas de radio
   ficam INTACTAS: mesmo name/value, então o POST do formulário não muda nada.

2. "nos perfis e na ficha, a div principal precisa de um blur desfocando a imagem
   de fundo" — o container central ganha backdrop-filter + fundo translúcido
   derivado do tema, mas SÓ quando há imagem de fundo (classe condicional no
   template) e com fallback @supports para quem não tem backdrop-filter.

Roda contra o CATÁLOGO REAL (TbCosmetico vem das migrações de seed/backfill).
"""
import os
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from home.models import TbPersonagem, UserProfile
from home.test_levelup import LevelUpLoteBase
from home.views import _appearance_catalog

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
_CSS_SWATCH = os.path.join(_STATIC, 'css', 'components', 'tema_swatch.css')
_CSS_PERFIL = os.path.join(_STATIC, 'css', 'pages', 'perfil.css')
_CSS_FICHA = os.path.join(_STATIC, 'css', 'pages', 'ficha.css')
_JS_SWATCH = os.path.join(_STATIC, 'js', 'tema_swatch.js')

# Tema-dado basal 'abissal' (migração 0057 de backfill): cores fora do default.
_ABISSAL = 'abissal'


def _arquivo(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _grade(html, grid_id):
    """Recorta o HTML da grade de temas (do id da grade até o fim do formulário),
    para contar cartões sem pegar nada de fora do seletor."""
    inicio = html.index('id="%s"' % grid_id)
    fim = html.index('</div>', html.index('</label>', inicio))
    return html[inicio:fim]


class SwatchBase(TestCase):
    def setUp(self):
        super().setUp()
        # get_catalog é cacheado por TTL curto — sem limpar, um teste vê o
        # catálogo montado por outro.
        cache.clear()
        self.addCleanup(cache.clear)
        self.temas = _appearance_catalog('theme')


class CartoesDeTemaNoPerfilTests(SwatchBase):
    """A grade do editor de perfil (/perfil/)."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user('swatcher', 'sw@example.com', 'senha-forte-1')
        self.profile = UserProfile.objects.get_or_create(user=self.user)[0]
        self.profile.profile_theme = 'bonfire'
        self.profile.save()
        self.client.force_login(self.user)

    def _html(self):
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')

    def test_um_cartao_por_tema_do_catalogo(self):
        grade = _grade(self._html(), 'id_profile_theme_group')
        cartoes = re.findall(r'data-tema-card="([^"]*)"', grade)
        self.assertEqual(sorted(cartoes), sorted(self.temas.keys()),
                         'a grade tem que ter exatamente 1 cartão por tema do catálogo')
        # Um radio por cartão — nenhum cartão decorativo sem input.
        self.assertEqual(len(re.findall(r'name="profile_theme"', grade)), len(cartoes))

    def test_cartao_carrega_as_cores_da_definicao_em_data_e_style(self):
        d = self.temas[_ABISSAL]['definicao']
        self.assertTrue(d, 'o backfill de temas basais precisa ter rodado')
        html = self._html()
        self.assertIn('data-accent="%s"' % d['accent'], html)
        self.assertIn('data-accent2="%s"' % d['accent2'], html)
        self.assertIn('data-surface="%s"' % d['surface'], html)
        self.assertIn('data-deep="%s"' % d['deep'], html)
        self.assertIn('data-particula="%s"' % d['particula'], html)
        # E as MESMAS cores como CSS vars, que é o que pinta a miniatura.
        self.assertIn('--tsw-accent:%s;--tsw-accent2:%s;--tsw-surface:%s;--tsw-deep:%s;'
                      % (d['accent'], d['accent2'], d['surface'], d['deep']), html)

    def test_cartao_custom_mostra_as_cores_atuais_do_usuario(self):
        self.profile.profile_theme = 'custom'
        self.profile.theme_custom = {'accent': '#123456', 'accent2': '#654321',
                                     'surface': '#0a0a0a', 'deep': '#050505'}
        self.profile.save()
        html = self._html()
        cartao = html[html.index('data-tema-card="custom"'):]
        cartao = cartao[:cartao.index('</label>')]
        self.assertIn('data-accent="#123456"', cartao)
        self.assertIn('data-deep="#050505"', cartao)
        self.assertIn('--tsw-surface:#0a0a0a', cartao)

    def test_semantica_de_radio_preservada(self):
        grade = _grade(self._html(), 'id_profile_theme_group')
        # value = a chave crua do catálogo (o que o backend valida/salva).
        for chave in self.temas:
            self.assertIn('value="%s"' % chave, grade)
        # Exatamente UM marcado, e é o tema salvo.
        marcados = re.findall(r'type="radio"[^>]*value="([^"]+)"[^>]*checked', grade)
        self.assertEqual(marcados, ['bonfire'])
        # E o <select> antigo sumiu — o nome do tema não é mais o elemento de escolha.
        self.assertNotIn('<select', grade)

    def test_o_nome_do_tema_e_so_legenda(self):
        grade = _grade(self._html(), 'id_profile_theme_group')
        self.assertIn('tema-swatch-name', grade)   # legenda pequena
        self.assertIn('tema-swatch-preview', grade)  # a miniatura é o elemento principal

    def test_post_do_formulario_continua_salvando_pelo_mesmo_campo(self):
        """Zero mudança de backend: o radio posta o que o <select> postava."""
        resp = self.client.post(reverse('profile'), data={
            'action': 'update_profile', 'username': self.user.username,
            'email': self.user.email, 'profile_theme': _ABISSAL,
            'avatar_frame': 'none', 'profile_effect': 'none'})
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(UserProfile.objects.get(user=self.user).profile_theme, _ABISSAL)

    def test_pagina_carrega_o_css_e_o_js_do_seletor(self):
        html = self._html()
        self.assertIn('css/components/tema_swatch.css', html)
        self.assertIn('js/tema_swatch.js', html)


def _classes_de(html, ancora):
    """Classes do elemento cuja tag de abertura contém `ancora`. Olhar só o
    atributo class evita falso positivo com o mesmo nome citado dentro do JS
    da página (o script da prévia menciona 'profile-has-bg' de propósito)."""
    fim = html.index(ancora)
    inicio = html.rindex('<', 0, fim)
    tag = html[inicio:html.index('>', fim) + 1]
    m = re.search(r'class="([^"]*)"', tag)
    return (m.group(1) if m else '').split()


class DesfoqueDoPainelDoPerfilTests(CartoesDeTemaNoPerfilTests):
    """Blur SÓ com imagem de fundo — a classe é condicional no template."""

    def test_sem_imagem_de_fundo_nao_ha_classe_de_desfoque(self):
        self.profile.background_url = ''
        self.profile.save()
        html = self._html()
        self.assertNotIn('profile-has-bg', _classes_de(html, 'id="profile-root"'))

    def test_com_imagem_de_fundo_a_classe_entra(self):
        self.profile.background_url = 'https://cdn.exemplo/fundo.jpg'
        self.profile.save()
        html = self._html()
        self.assertIn('profile-has-bg', _classes_de(html, 'id="profile-root"'))

    def test_perfil_publico_tambem_ganha_a_classe(self):
        self.profile.background_url = 'https://cdn.exemplo/fundo.jpg'
        self.profile.save()
        html = self.client.get(
            reverse('public_profile', args=[self.user.username])).content.decode('utf-8')
        classes = _classes_de(html, 'public-profile-page')
        self.assertIn('public-profile-page', classes)
        self.assertIn('profile-has-bg', classes)

    def test_perfil_publico_sem_fundo_fica_solido(self):
        self.profile.background_url = ''
        self.profile.save()
        html = self.client.get(
            reverse('public_profile', args=[self.user.username])).content.decode('utf-8')
        self.assertNotIn('profile-has-bg', _classes_de(html, 'public-profile-page'))


class CartoesDeTemaNaFichaTests(LevelUpLoteBase):
    """A grade do editor de aparência da ficha — antes o seletor da ficha nem
    carregava o CSS dos cartões (perfil.css não é linkado lá)."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.p = self._guerreiro_no_nivel(1, apelido='swatch-ficha')
        self.client.force_login(self.p.dono)
        self.temas = _appearance_catalog('theme')

    def _html(self):
        resp = self.client.get(reverse('ficha_detail', args=[self.p.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')

    def test_um_cartao_por_tema_com_as_cores_da_definicao(self):
        html = self._html()
        grade = _grade(html, 'ficha-theme-group')
        cartoes = re.findall(r'data-tema-card="([^"]*)"', grade)
        self.assertEqual(sorted(cartoes), sorted(self.temas.keys()))
        self.assertEqual(len(re.findall(r'name="ficha_theme"', grade)), len(cartoes))
        d = self.temas[_ABISSAL]['definicao']
        self.assertIn('data-accent="%s"' % d['accent'], grade)
        self.assertIn('--tsw-deep:%s' % d['deep'], grade)

    def test_ficha_carrega_o_css_e_o_js_do_seletor(self):
        html = self._html()
        self.assertIn('css/components/tema_swatch.css', html)
        self.assertIn('js/tema_swatch.js', html)

    def test_sem_imagem_de_fundo_a_folha_nao_ganha_desfoque(self):
        html = self._html()
        self.assertNotIn('ficha-has-bg', _classes_de(html, 'ficha animate-fade-in'))
        self.assertNotIn('ficha-bg-media', html)

    def test_com_imagem_de_fundo_a_folha_ganha_a_classe_de_desfoque(self):
        TbPersonagem.objects.filter(pk=self.p.pk).update(
            ficha_background_url='https://cdn.exemplo/fundo-ficha.jpg')
        html = self._html()
        self.assertIn('ficha-has-bg', _classes_de(html, 'ficha animate-fade-in'))
        self.assertIn('ficha-bg-media', html)

    def test_tema_salvo_pela_ficha_continua_pelo_mesmo_campo(self):
        resp = self.client.post(reverse('personagem_info_salvar', args=[self.p.pk]),
                                data={'ficha_theme': _ABISSAL, 'foto_frame': 'none',
                                      'ficha_effect': 'none'},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn(resp.status_code, (200, 302))
        self.p.refresh_from_db()
        self.assertEqual(self.p.ficha_theme, _ABISSAL)


class CssDoDesfoqueTests(SwatchBase):
    """O CSS do blur: presente, condicionado à classe, e com fallback."""

    def test_perfil_declara_backdrop_filter_no_container_central(self):
        css = _arquivo(_CSS_PERFIL)
        bloco = css[css.index('.profile-page.profile-has-bg,'):]
        bloco = bloco[:bloco.index('}')]
        self.assertIn('backdrop-filter: blur(12px)', bloco)
        self.assertIn('color-mix(in srgb, var(--profile-deep)', bloco)
        # superfície translúcida derivada do tema (~86%), como pediu o PO
        self.assertIn('color-mix(in srgb, var(--profile-surface) 86%, transparent)', css)

    def test_ficha_declara_backdrop_filter_na_folha(self):
        css = _arquivo(_CSS_FICHA)
        bloco = css[css.index('.ficha.ficha-has-bg {'):]
        bloco = bloco[:bloco.index('}')]
        self.assertIn('backdrop-filter: blur(12px)', bloco)
        self.assertIn('color-mix(in srgb, var(--sheet-surface) 86%, transparent)', css)

    def test_fallback_supports_presente_nos_dois_arquivos(self):
        for path in (_CSS_PERFIL, _CSS_FICHA):
            css = _arquivo(path)
            self.assertIn('@supports not ((backdrop-filter: blur(2px))', css,
                          'faltou o fallback @supports em %s' % os.path.basename(path))

    def test_desfoque_e_condicionado_a_classe_de_imagem_de_fundo(self):
        """Nada de painel lavado à toa: nenhum blur é incondicional. Ou vem da
        classe de imagem de fundo (o pedido do PO), ou do cosmético 'Vidro'
        (.effect-glass), que já existia e é escolha explícita do usuário."""
        for path, classe in ((_CSS_PERFIL, 'has-bg'), (_CSS_FICHA, 'ficha-has-bg')):
            css = _arquivo(path)
            achou_gate = False
            for m in re.finditer(r'([^{}]+)\{([^{}]*backdrop-filter[^{}]*)\}', css):
                seletor, corpo = m.group(1), m.group(2)
                if 'none' in corpo:
                    continue  # reset de impressão
                self.assertTrue(classe in seletor or 'effect-glass' in seletor,
                                '%s: blur incondicional → %s'
                                % (os.path.basename(path), seletor.strip()))
                achou_gate = achou_gate or classe in seletor
            self.assertTrue(achou_gate,
                            '%s: nenhuma regra de blur presa a .%s'
                            % (os.path.basename(path), classe))

    def test_componente_do_seletor_e_compartilhado_e_data_driven(self):
        css = _arquivo(_CSS_SWATCH)
        self.assertIn('.ficha .tema-swatch-grid', css)   # serve perfil E ficha
        self.assertIn('var(--tsw-accent', css)
        self.assertIn('var(--tsw-surface', css)
        self.assertIn(':has(input:focus-visible)', css)  # navegável por teclado
        self.assertIn(':has(input:checked)', css)        # anel de selecionado
        # o CSS antigo saiu de perfil.css (não pode ficar duplicado nos dois)
        self.assertNotIn('.tema-swatch-preview', _arquivo(_CSS_PERFIL))

    def test_js_espelha_o_builder_de_vars_do_backend(self):
        js = _arquivo(_JS_SWATCH)
        for var in ('--profile-accent-solid', '--sheet-accent-solid',
                    '--profile-surface', '--sheet-surface'):
            self.assertIn(var, js)
        self.assertIn('linear-gradient(120deg, ', js)   # mesmo formato do _theme_vars_style
        self.assertIn('data-fx-particula', js)          # contrato das partículas
