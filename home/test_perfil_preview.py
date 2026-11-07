# -*- coding: utf-8 -*-
"""PRÉVIA VIVA DO PERFIL — regressão do endpoint POST /perfil/previa/.

Contrato (padrão de preview do projeto, igual `criar_personagem_preview_view`):
a prévia passa pelo MESMO code path do render real, então NÃO existe drift entre
o que o usuário vê antes de salvar e o que a página pública mostra depois.

O que este arquivo prova:
  1. o preview devolve o HERO do perfil com as VARS do tema CANDIDATO (o tema
     ainda não salvo já aparece, via `_theme_vars_style` + data-fx-*);
  2. candidato BLOQUEADO (cosmético que o usuário não possui) é RECUSADO
     exatamente como no salvamento — cai no default e volta marcado em
     `recusados`, sem 500 e sem contrabandear o cosmético;
  3. NADA persiste: depois de N prévias a aparência salva continua idêntica;
  4. anônimo toma 302 (login_required) e GET não é aceito;
  5. o perfil PÚBLICO continua renderizando — pelo partial unificado, o mesmo
     que a prévia usa (render único, sem duplicação de markup).

Roda contra o CATÁLOGO REAL (TbCosmetico vem das migrações de seed/backfill):
'abissal' é um tema-dado basal (accent #38E1FF, partícula flutuar/lenta) e as
chaves do catálogo são o slug SEM o prefixo do tipo ('tema-abissal' → 'abissal').
Os cosméticos BLOQUEADOS são criados aqui porque o seed é todo origem='livre'.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from home.models import TbCosmetico, TbUsuarioCosmetico, UserProfile

_PARTIAL = 'home/partials/_perfil_publico_hero.html'

# Tema basal 'abissal' (migração de backfill) — cores fora do tema salvo ('bonfire'),
# o que permite provar que as vars emitidas são as do CANDIDATO.
_ABISSAL_ACCENT = '#38E1FF'
_ABISSAL_SURFACE = '#071722'
_ABISSAL_GRADIENTE = 'linear-gradient(120deg, #38E1FF, #2563EB)'


class PreviewCatalogoParcialTests(TestCase):
    def test_perfil_e_previa_renderizam_default_sem_seed_basal(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = get_user_model().objects.create_user(
            'catalogo-parcial', 'parcial@example.com', 'senha-forte-1')
        profile = UserProfile.objects.get_or_create(user=user)[0]
        profile.profile_theme = 'bonfire'
        profile.save(update_fields=['profile_theme'])
        TbCosmetico.objects.create(
            slug='tema-relicario-parcial', tipo='tema', nome='Relicário',
            origem='loja_mm', escopo='ambos')
        TbCosmetico.objects.create(
            slug='moldura-relicario-parcial', tipo='moldura', nome='Aro',
            origem='loja_mm', escopo='ambos')
        TbCosmetico.objects.create(
            slug='efeito-relicario-parcial', tipo='efeito', nome='Brilho',
            origem='loja_mm', escopo='ambos')
        cache.clear()
        catalogo_parcial = {
            kind: {'relicario-parcial': {'label': 'Relicário', 'class': css_class}}
            for kind, css_class in (
                ('theme', 'theme-relicario'), ('frame', 'frame-relicario'),
                ('effect', 'effect-relicario'))
        }
        with patch('home.views._appearance_catalog',
                   side_effect=lambda kind: catalogo_parcial[kind]):
            publico = self.client.get(reverse('public_profile', args=[user.username]))
            self.assertEqual(publico.status_code, 200)
            self.assertContains(publico, 'theme-bonfire')

            self.client.force_login(user)
            previa = self.client.post(reverse('perfil_preview'), data={
                'profile_theme': 'relicario-parcial',
                'avatar_frame': 'relicario-parcial',
                'profile_effect': 'relicario-parcial',
            })
        self.assertEqual(previa.status_code, 200)
        corpo = previa.json()
        self.assertEqual(corpo['theme_key'], 'bonfire')
        self.assertEqual(corpo['frame_key'], 'none')
        self.assertEqual(corpo['effect_key'], 'none')
        self.assertEqual(
            sorted(corpo['recusados']),
            ['avatar_frame', 'profile_effect', 'profile_theme'])
        self.assertIn('theme-bonfire', corpo['html'])


class PerfilPreviewBase(TestCase):
    """Usuário dono do perfil + cosméticos BLOQUEADOS (o seed só tem 'livre')."""

    def setUp(self):
        super().setUp()
        # get_catalog é cacheado por TTL curto — sem limpar, um teste vê o
        # catálogo montado por outro.
        cache.clear()
        self.addCleanup(cache.clear)

        # A reused test database may predate the data seeds. These are the
        # baseline entries exercised below; keep the fixture self-contained.
        for slug, tipo, nome, css_class in (
            ('tema-bonfire', 'tema', 'Bonfire', 'theme-bonfire'),
            ('tema-custom', 'tema', 'Personalizado', 'theme-custom'),
            ('moldura-none', 'moldura', 'Sem moldura', ''),
            ('moldura-gold-trim', 'moldura', 'Friso Dourado', 'frame-gold-trim'),
            ('efeito-none', 'efeito', 'Sem efeito', ''),
            ('efeito-aurora', 'efeito', 'Aurora', 'effect-aurora'),
        ):
            TbCosmetico.objects.get_or_create(
                slug=slug,
                defaults={'tipo': tipo, 'nome': nome, 'css_class': css_class,
                          'origem': 'livre', 'escopo': 'ambos'},
            )
        TbCosmetico.objects.get_or_create(
            slug='tema-abissal',
            defaults={
                'tipo': 'tema', 'nome': 'Abissal', 'origem': 'livre',
                'escopo': 'ambos',
                'definicao_json': {
                    'accent': '#38E1FF', 'accent2': '#2563EB',
                    'surface': '#071722', 'deep': '#030B12',
                    'gradiente': True, 'particula': 'flutuar',
                    'vel': 'lenta', 'glow': True,
                },
            },
        )
        cache.clear()

        User = get_user_model()
        self.user = User.objects.create_user('gaz', 'gaz@example.com', 'senha-forte-1')
        self.profile = UserProfile.objects.get_or_create(user=self.user)[0]
        self.profile.profile_theme = 'bonfire'
        self.profile.avatar_frame = None
        self.profile.profile_effect = None
        self.profile.titulo_equipado = ''
        self.profile.badges_destaque = []
        self.profile.save()

        # Cosméticos NÃO-LIVRES: só entram na aparência de quem os tem no inventário.
        self.tema_premium = TbCosmetico.objects.create(
            slug='tema-relicario', tipo='tema', nome='Relicário', css_class='',
            origem='loja_mm', preco=500, escopo='ambos', ordem=90,
            definicao_json={'accent': '#FF00AA', 'accent2': '#00FFAA',
                            'surface': '#120018', 'deep': '#08000C',
                            'gradiente': False, 'particula': 'cair', 'vel': 'rapida'})
        self.moldura_premium = TbCosmetico.objects.create(
            slug='moldura-relicario', tipo='moldura', nome='Aro do Relicário',
            css_class='frame-relicario', origem='loja_mm', preco=300,
            escopo='ambos', ordem=90)
        self.titulo_premium = TbCosmetico.objects.create(
            slug='titulo-guardiao-da-chama', tipo='titulo', nome='Guardião da Chama',
            origem='conquista', raridade='epico', escopo='perfil', ordem=0)

        self.client.force_login(self.user)

    def _preview(self, **campos):
        """POST do estado candidato do formulário de aparência."""
        dados = {'profile_theme': 'bonfire', 'avatar_frame': 'none',
                 'profile_effect': 'none'}
        dados.update(campos)
        return self.client.post(reverse('perfil_preview'), data=dados)

    def _aparencia_salva(self):
        p = UserProfile.objects.get(user=self.user)
        return (p.profile_theme, p.avatar_frame, p.profile_effect,
                p.titulo_equipado, list(p.badges_destaque or []),
                dict(p.theme_custom or {}), p.avatar_url, p.banner_url,
                p.background_url, p.bio)


class PreviewRenderizaCandidatoTests(PerfilPreviewBase):
    def test_hero_volta_com_as_vars_do_tema_candidato(self):
        resp = self._preview(profile_theme='abissal')
        self.assertEqual(resp.status_code, 200, resp.content)
        corpo = resp.json()
        self.assertTrue(corpo['ok'])
        html = corpo['html']
        # É o hero do perfil público (partial unificado), não um card decorativo.
        self.assertIn('public-profile-page', html)
        self.assertIn('public-profile-card', html)
        # Vars do tema CANDIDATO (ainda NÃO salvo), emitidas por _theme_vars_style.
        self.assertIn('--profile-accent-solid:%s' % _ABISSAL_ACCENT, html)
        self.assertIn('--profile-surface:%s' % _ABISSAL_SURFACE, html)
        self.assertIn('--sheet-accent-solid:%s' % _ABISSAL_ACCENT, html)
        # gradiente=True → accent vira linear-gradient (mesmo builder do custom).
        self.assertIn(_ABISSAL_GRADIENTE, html)
        # Partículas por atributo (contrato do perfil-fx.css).
        self.assertIn('data-fx-particula="flutuar"', html)
        self.assertIn('data-fx-vel="lenta"', html)
        self.assertEqual(corpo['theme_key'], 'abissal')
        self.assertEqual(corpo['recusados'], [])
        # E o tema SALVO continua sendo o antigo.
        self.assertEqual(UserProfile.objects.get(user=self.user).profile_theme, 'bonfire')

    def test_moldura_e_efeito_candidatos_entram_nas_classes(self):
        corpo = self._preview(avatar_frame='gold-trim', profile_effect='aurora').json()
        self.assertEqual(corpo['recusados'], [])
        self.assertIn('frame-gold-trim', corpo['html'])
        self.assertIn('effect-aurora', corpo['html'])

    def test_tema_custom_do_formulario_entra_na_previa(self):
        corpo = self._preview(profile_theme='custom', custom_accent='#123456',
                              custom_accent2='#654321', custom_surface='#0a0a0a',
                              custom_deep='#050505').json()
        self.assertTrue(corpo['is_custom'])
        self.assertIn('--profile-accent:#123456', corpo['html'])
        self.assertIn('--profile-deep:#050505', corpo['html'])

    def test_cor_invalida_e_sanitizada_e_nao_vaza_pro_style(self):
        html = self._preview(
            profile_theme='custom',
            custom_accent='red;}</style><script>alert(1)</script>').json()['html']
        self.assertNotIn('<script>', html)
        self.assertNotIn('alert(1)', html)
        # Cai no default do tema Personalizado (hex-only).
        self.assertIn('--profile-accent:#f59e0b', html)

    def test_previa_reflete_banner_avatar_e_bio_candidatos(self):
        html = self._preview(avatar_url='https://cdn.exemplo/av.gif',
                             banner_url='https://cdn.exemplo/bn.gif',
                             bio='Contador de histórias na fogueira.').json()['html']
        self.assertIn('https://cdn.exemplo/av.gif', html)
        self.assertIn('https://cdn.exemplo/bn.gif', html)
        self.assertIn('Contador de histórias na fogueira.', html)
        # E nada disso encostou no banco.
        p = UserProfile.objects.get(user=self.user)
        self.assertIn(p.avatar_url, (None, ''))
        self.assertIn(p.bio, (None, ''))

    def test_titulo_e_badge_possuidos_aparecem_na_previa(self):
        TbUsuarioCosmetico.objects.create(user=self.user, cosmetico=self.titulo_premium,
                                          origem='conquista:teste')
        badge = TbCosmetico.objects.create(slug='badge-primeira-fogueira', tipo='badge',
                                           nome='Primeira Fogueira', asset_url='🔥',
                                           origem='conquista', ordem=0)
        TbUsuarioCosmetico.objects.create(user=self.user, cosmetico=badge, origem='staff')
        cache.clear()
        corpo = self._preview(titulo_equipado='titulo-guardiao-da-chama',
                              badges_destaque=['badge-primeira-fogueira']).json()
        self.assertEqual(corpo['recusados'], [])
        self.assertIn('Guardião da Chama', corpo['html'])
        self.assertIn('Primeira Fogueira', corpo['html'])
        self.assertEqual(corpo['badges_destaque'], ['badge-primeira-fogueira'])


class PreviewRecusaCandidatoBloqueadoTests(PerfilPreviewBase):
    """Recusa IDÊNTICA à do salvamento — a prévia não é uma porta dos fundos."""

    def _salva(self, **campos):
        dados = {'action': 'update_profile', 'username': self.user.username,
                 'email': self.user.email, 'profile_theme': 'bonfire',
                 'avatar_frame': 'none', 'profile_effect': 'none'}
        dados.update(campos)
        return self.client.post(reverse('profile'), data=dados)

    def test_tema_nao_possuido_cai_no_default_igual_ao_salvar(self):
        corpo = self._preview(profile_theme='relicario').json()
        # Prévia: recusado → volta pro default do tipo.
        self.assertEqual(corpo['theme_key'], 'bonfire')
        self.assertIn('profile_theme', corpo['recusados'])
        self.assertNotIn('#FF00AA', corpo['html'])

        # Salvar o MESMO candidato produz a MESMA recusa.
        self._salva(profile_theme='relicario')
        self.assertEqual(UserProfile.objects.get(user=self.user).profile_theme, 'bonfire')

    def test_moldura_nao_possuida_cai_no_default_igual_ao_salvar(self):
        corpo = self._preview(avatar_frame='relicario').json()
        self.assertEqual(corpo['frame_key'], 'none')
        self.assertIn('avatar_frame', corpo['recusados'])
        self.assertNotIn('frame-relicario', corpo['html'])

        self._salva(avatar_frame='relicario')
        self.assertIn(UserProfile.objects.get(user=self.user).avatar_frame, (None, ''))

    def test_titulo_nao_possuido_e_recusado_igual_ao_salvar(self):
        corpo = self._preview(titulo_equipado='titulo-guardiao-da-chama').json()
        self.assertEqual(corpo['titulo_equipado'], '')
        self.assertIn('titulo_equipado', corpo['recusados'])
        self.assertNotIn('Guardião da Chama', corpo['html'])

        self._salva(titulo_equipado='titulo-guardiao-da-chama')
        self.assertEqual(UserProfile.objects.get(user=self.user).titulo_equipado, '')

    def test_badge_nao_possuida_e_recusada_igual_ao_salvar(self):
        TbCosmetico.objects.create(slug='badge-matador-dragoes', tipo='badge',
                                   nome='Matador de Dragões', asset_url='🐉',
                                   origem='conquista', ordem=0)
        cache.clear()
        corpo = self._preview(badges_destaque=['badge-matador-dragoes']).json()
        self.assertEqual(corpo['badges_destaque'], [])
        self.assertIn('badges_destaque', corpo['recusados'])
        self.assertNotIn('Matador de Dragões', corpo['html'])

        self._salva(badges_destaque=['badge-matador-dragoes'])
        self.assertEqual(list(UserProfile.objects.get(user=self.user).badges_destaque), [])

    def test_tema_premium_POSSUIDO_passa_na_previa(self):
        """A recusa é por POSSE, não por origem: com o item no inventário, passa."""
        TbUsuarioCosmetico.objects.create(user=self.user, cosmetico=self.tema_premium,
                                          origem='compra_mm')
        cache.clear()
        corpo = self._preview(profile_theme='relicario').json()
        self.assertEqual(corpo['theme_key'], 'relicario')
        self.assertEqual(corpo['recusados'], [])
        self.assertIn('--profile-accent-solid:#FF00AA', corpo['html'])
        self.assertIn('data-fx-particula="cair"', corpo['html'])

    def test_cosmetico_inexistente_nao_quebra_a_previa(self):
        corpo = self._preview(profile_theme='tema-que-nao-existe',
                              avatar_frame='inventado').json()
        self.assertEqual(corpo['theme_key'], 'bonfire')
        self.assertEqual(corpo['frame_key'], 'none')
        self.assertEqual(sorted(corpo['recusados']), ['avatar_frame', 'profile_theme'])


class PreviewNaoPersisteNadaTests(PerfilPreviewBase):
    def test_n_previas_deixam_a_aparencia_salva_intacta(self):
        self.profile.profile_theme = 'abissal'
        self.profile.bio = 'bio original'
        self.profile.avatar_url = 'https://cdn.exemplo/original.png'
        self.profile.save()
        antes = self._aparencia_salva()

        for i in range(5):
            resp = self._preview(profile_theme='bonfire', avatar_frame='gold-trim',
                                 profile_effect='aurora', bio='rascunho %d' % i,
                                 avatar_url='https://cdn.exemplo/rascunho%d.png' % i,
                                 background_url='https://cdn.exemplo/fundo.gif',
                                 custom_accent='#abcdef', clear_banner='on',
                                 titulo_equipado='titulo-guardiao-da-chama')
            self.assertEqual(resp.status_code, 200, resp.content)

        self.assertEqual(self._aparencia_salva(), antes)

    def test_previa_nao_cria_linhas_de_inventario_nem_perfis(self):
        antes = (UserProfile.objects.count(), TbUsuarioCosmetico.objects.count())
        self._preview(profile_theme='relicario',
                      titulo_equipado='titulo-guardiao-da-chama')
        self.assertEqual((UserProfile.objects.count(), TbUsuarioCosmetico.objects.count()),
                         antes)


class PreviewAcessoTests(PerfilPreviewBase):
    def test_anonimo_toma_302(self):
        self.client.logout()
        resp = self.client.post(reverse('perfil_preview'), data={'profile_theme': 'bonfire'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_get_nao_e_aceito(self):
        self.assertEqual(self.client.get(reverse('perfil_preview')).status_code, 405)

    def test_previa_e_sempre_do_dono_logado(self):
        """O endpoint não aceita alvo: o perfil previsto é sempre o de quem pediu."""
        get_user_model().objects.create_user('vizinho', 'v@example.com', 'senha-forte-2')
        html = self._preview(username='vizinho').json()['html']
        self.assertIn('@gaz', html)
        self.assertNotIn('@vizinho', html)


class PartialUnificadoTests(PerfilPreviewBase):
    """Render ÚNICO: prévia e perfil público saem do MESMO template."""

    def test_perfil_publico_renderiza_com_o_partial(self):
        resp = self.client.get(reverse('public_profile', args=[self.user.username]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'home/pages/perfil_publico.html')
        self.assertTemplateUsed(resp, _PARTIAL)
        corpo = resp.content.decode('utf-8')
        self.assertIn('public-profile-page', corpo)
        self.assertIn('Personagens', corpo)
        # Na página real o link de volta existe; na prévia, não.
        self.assertIn('public-profile-back', corpo)

    def test_editor_ja_nasce_com_a_previa_do_estado_salvo(self):
        self.profile.profile_theme = 'abissal'
        self.profile.save()
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, _PARTIAL)
        corpo = resp.content.decode('utf-8')
        self.assertIn('perfil-preview-stage', corpo)
        # Estado inicial = aparência ATUAL SALVA (abissal), já renderizada.
        self.assertIn('--profile-surface:%s' % _ABISSAL_SURFACE, corpo)
        self.assertIn('data-fx-particula="flutuar"', corpo)

    def test_previa_nao_traz_o_link_de_voltar_da_pagina_publica(self):
        html = self._preview().json()['html']
        self.assertNotIn('public-profile-back', html)
        self.assertIn('is-preview', html)
        # Gancho do fundo escopado (o cliente sobrepõe o arquivo local aqui).
        self.assertIn('perfil-preview-bg', html)

    def test_previa_e_pagina_publica_batem_no_mesmo_estado(self):
        """Zero drift: com o MESMO estado, o hero da prévia é o hero da página."""
        self.profile.profile_theme = 'abissal'
        self.profile.bio = 'Mesma bio nos dois lados.'
        self.profile.save()
        publico = self.client.get(
            reverse('public_profile', args=[self.user.username])).content.decode('utf-8')
        previa = self._preview(profile_theme='abissal', avatar_frame='none',
                               profile_effect='none',
                               bio='Mesma bio nos dois lados.').json()['html']
        for marca in ('--profile-surface:%s' % _ABISSAL_SURFACE,
                      'data-fx-particula="flutuar"',
                      'data-fx-vel="lenta"',
                      'Mesma bio nos dois lados.'):
            self.assertIn(marca, publico, 'faltou no perfil público: %s' % marca)
            self.assertIn(marca, previa, 'faltou na prévia: %s' % marca)
        self.assertIn('<h1>gaz</h1>', publico)
        self.assertIn('<h2 class="public-profile-preview-name">gaz</h2>', previa)
