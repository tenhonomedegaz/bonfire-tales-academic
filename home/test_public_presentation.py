from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TbConteudoEstatico, TbCronica, TbJornal, TbMapLayer, TbPersonagem, TbRegiao, TbTerritorio


class PublicPresentationTests(TestCase):
    def test_home_shows_only_published_community_stories(self):
        author = get_user_model().objects.create_user(username='story-author')
        published = TbCronica.objects.create(
            titulo='História pública', slug='historia-publica',
            conteudo_markdown='Um relato completo.', autor=author,
            status='aprovada', data_publicacao=timezone.now(),
        )
        TbCronica.objects.create(
            titulo='Rascunho privado', slug='rascunho-privado',
            conteudo_markdown='Ainda em revisão.', autor=author, status='pendente',
        )
        TbJornal.objects.create(titulo='Artigo do jornal', slug='artigo-do-jornal')

        response = self.client.get(reverse('home'))

        self.assertContains(response, published.titulo)
        self.assertContains(response, reverse('cronica_detail', kwargs={'slug': published.slug}))
        self.assertNotContains(response, 'Rascunho privado')
        self.assertNotContains(response, 'Artigo do jornal')
        self.assertNotContains(response, 'Volte para a aventura')

    def test_home_personal_shortcuts_are_owned_and_active_only(self):
        owner = get_user_model().objects.create_user(username='home-owner')
        other = get_user_model().objects.create_user(username='other-owner')
        active = TbPersonagem.objects.create(dono=owner, nome='Minha heroína')
        TbPersonagem.objects.create(dono=owner, nome='No cofre', arquivado=True)
        TbPersonagem.objects.create(dono=other, nome='Personagem alheio')
        self.client.force_login(owner)

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Volte para a aventura')
        self.assertContains(response, reverse('ficha_detail', kwargs={'pk': active.pk}))
        self.assertContains(response, 'Minha heroína')
        self.assertNotContains(response, 'No cofre')
        self.assertNotContains(response, 'Personagem alheio')
        self.assertContains(response, 'feed=seguindo')

    def test_home_onboarding_links_follow_account_progress(self):
        visitor = self.client.get(reverse('home'))
        self.assertContains(visitor, 'href="#como-jogar"')
        self.assertContains(visitor, 'id="como-jogar"')
        self.assertContains(visitor, 'id="home-primary-action" href="%s"' % reverse('register'))
        self.assertContains(visitor, 'id="home-next-step" href="%s"' % reverse('register'))

        journey = TbConteudoEstatico.objects.get(chave='home-jornada')
        journey.cta_texto = 'Ler o guia'
        journey.cta_url = reverse('sobre')
        journey.save(update_fields=['cta_texto', 'cta_url'])
        visitor_with_editorial_link = self.client.get(reverse('home'))
        self.assertContains(visitor_with_editorial_link, 'id="home-next-step" href="%s"' % reverse('sobre'))

        player = get_user_model().objects.create_user(username='new-player')
        self.client.force_login(player)
        TbPersonagem.objects.create(dono=player, nome='Ficha arquivada', arquivado=True)
        before_character = self.client.get(reverse('home'))
        self.assertContains(before_character, 'id="home-primary-action" href="%s"' % reverse('criacao_ficha'))
        self.assertContains(before_character, 'id="home-next-step" href="%s"' % reverse('criacao_ficha'))
        self.assertNotContains(before_character, 'id="home-next-step" href="%s"' % reverse('register'))

        TbPersonagem.objects.create(dono=player, nome='Primeira ficha')
        ready_to_play = self.client.get(reverse('home'))
        self.assertContains(ready_to_play, 'id="home-next-step" href="%s"' % reverse('sistemas_missoes'))

    def test_home_uses_managed_content_without_fake_ads(self):
        bloco = TbConteudoEstatico.objects.get(chave='home-hero')
        bloco.titulo = 'Título editado no admin'
        bloco.imagem_url = 'https://example.com/banner-editado.webp'
        bloco.save(update_fields=['titulo', 'imagem_url'])

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Título editado no admin')
        self.assertContains(response, 'https://example.com/banner-editado.webp')
        self.assertNotContains(response, 'Advertisement')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'rel="canonical"')

    @override_settings(
        ADSENSE_ENABLED=True,
        ADSENSE_SIDEBAR_SLOT='1234567890',
        ADSENSE_HORIZONTAL_SLOT='0987654321',
    )
    def test_ads_are_opt_in_and_never_render_on_login(self):
        home = self.client.get(reverse('home'))
        login = self.client.get(reverse('login'))

        self.assertContains(home, 'data-ad-slot="1234567890"')
        self.assertContains(home, 'data-ad-slot="0987654321"')
        self.assertNotContains(login, 'adsbygoogle')
        self.assertContains(login, 'noindex, nofollow')

    def test_institutional_pages_have_real_content(self):
        for name in ('sobre', 'contato', 'privacidade', 'termos'):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'Esta página está em construção')
                self.assertNotContains(response, 'Advertisement')

    def test_sitemap_ads_txt_and_robots(self):
        sitemap = self.client.get(reverse('sitemap_xml'))
        robots = self.client.get(reverse('robots_txt'))
        ads = self.client.get(reverse('ads_txt'))

        self.assertEqual(sitemap.status_code, 200)
        self.assertEqual(sitemap['Content-Type'], 'application/xml; charset=utf-8')
        self.assertContains(sitemap, '/privacidade/')
        self.assertNotContains(sitemap, '/login/')
        self.assertNotContains(sitemap, '/mapa/')
        self.assertContains(robots, 'Disallow: /admin/')
        self.assertContains(robots, 'Sitemap: http://testserver/sitemap.xml')
        self.assertContains(ads, 'google.com, ca-pub-1634793837919535, DIRECT')

    def test_sitemap_only_promotes_world_pages_with_lore(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0,
            defaults={'nome': 'Cinéria', 'ordem': 0, 'publica': True},
        )
        TbRegiao.objects.create(nome='Com Lore', slug='com-lore', camada=0, lore_markdown='Lore própria e completa.')
        TbRegiao.objects.create(nome='Sem Lore', slug='sem-lore', camada=0, lore_markdown='')
        TbTerritorio.objects.create(nome='Território Com Lore', slug='territorio-com-lore', camada=0, lore_markdown='Lore própria.')
        TbTerritorio.objects.create(nome='Território Sem Lore', slug='territorio-sem-lore', camada=0, lore_markdown='')

        sitemap = self.client.get(reverse('sitemap_xml'))

        self.assertContains(sitemap, '/mundo/regioes/com-lore/')
        self.assertNotContains(sitemap, '/mundo/regioes/sem-lore/')
        self.assertContains(sitemap, '/mundo/territorios/territorio-com-lore/')
        self.assertNotContains(sitemap, '/mundo/territorios/territorio-sem-lore/')

    def test_map_is_public_but_not_indexed(self):
        response = self.client.get(reverse('mapa'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'noindex, nofollow')

    def test_old_placeholder_urls_redirect_to_real_content(self):
        cases = {
            'magias_congregacao': reverse('magias_listas'),
            'mundo_cosmo': reverse('mundo_regioes'),
            'mundo_linha_tempo': reverse('mundo_cronicas'),
            'mundo_faccoes': reverse('mundo_organizacoes'),
            'catarse': reverse('colaborador'),
        }
        for route_name, target in cases.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.url, target)
