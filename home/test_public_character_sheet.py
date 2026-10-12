"""A vitrine pública só lê campos expressamente liberados pelo personagem."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .cosmetics import invalidate_cosmetic_cache
from .models import (TbClasse, TbCosmetico, TbPersonagem,
                     TbPersonagemClasse, TbRaca, TbUsuarioCosmetico)


class PublicCharacterSheetTests(TestCase):
    def tearDown(self):
        invalidate_cosmetic_cache()

    def test_anonymous_legacy_link_opens_only_published_projection(self):
        operational = reverse('ficha_detail', args=[self.character.pk])
        public = reverse('ficha_publica', args=[self.character.pk])
        login = '/login/?next=' + operational.replace('/', '%2F')

        self.assertRedirects(self.client.get(operational), login,
                             fetch_redirect_response=False)
        TbPersonagem.objects.filter(pk=self.character.pk).update(publico=True)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(operational, follow=True)
            head = self.client.head(operational)
            post = self.client.post(operational, {'action': 'unpublish'})
        self.assertRedirects(response, public)
        self.assertEqual(head.status_code, 302)
        self.assertEqual(head['Location'], public)
        self.assertRedirects(post, login, fetch_redirect_response=False)
        for secret in (self.character.anotacoes, self.character.notas_jogador,
                       self.character.historia, '987654', '12345'):
            self.assertNotIn(secret, response.content.decode())
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
            ('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertEqual(writes, [])

        TbPersonagem.objects.filter(pk=self.character.pk).update(arquivado=True)
        self.assertRedirects(self.client.get(operational), login,
                             fetch_redirect_response=False)
        TbPersonagem.objects.filter(pk=self.character.pk).update(arquivado=False, publico=False)
        self.assertRedirects(self.client.get(operational), login,
                             fetch_redirect_response=False)

    def test_operational_link_redirects_visitor_to_public_projection(self):
        TbPersonagem.objects.filter(pk=self.character.pk).update(publico=True)
        operational = reverse('ficha_detail', args=[self.character.pk])
        public = reverse('ficha_publica', args=[self.character.pk])
        self.client.force_login(self.other)
        response = self.client.get(operational)
        self.assertRedirects(response, public)
        html = self.client.get(public).content.decode()
        for secret in ('NOTA PRIVADA Q8', 'MESA PRIVADA Q8',
                       'HISTÓRIA PRIVADA Q8', '987654', '12345'):
            self.assertNotIn(secret, html)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(operational).status_code, 200)
        TbPersonagem.objects.filter(pk=self.character.pk).update(publico=False)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(operational).status_code, 404)
        self.assertEqual(self.client.get(public).status_code, 404)

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('public-sheet-owner')
        cls.other = User.objects.create_user('public-sheet-other')
        cls.staff = User.objects.create_user('public-sheet-staff', is_staff=True)
        race = TbRaca.objects.create(nome='Raça pública', slug='raca-publica')
        klass = TbClasse.objects.create(nome='Classe pública', slug='classe-publica')
        cls.character = TbPersonagem.objects.create(
            dono=cls.owner, nome='Heroína pública', id_raca=race,
            anotacoes='NOTA PRIVADA Q8', notas_jogador='MESA PRIVADA Q8',
            historia='HISTÓRIA PRIVADA Q8', carteira_pc=987654, braseiros=12345,
        )
        TbPersonagemClasse.objects.create(
            id_personagem=cls.character, id_classe=klass, nivel=1, principal=True)

    def test_owner_can_preview_publish_and_revoke_without_public_cache(self):
        public = reverse('ficha_publica', args=[self.character.pk])
        action = reverse('personagem_publicacao', args=[self.character.pk])
        self.assertEqual(self.client.get(public).status_code, 404)
        self.client.force_login(self.owner)
        preview = self.client.get(public + '?preview=1')
        self.assertContains(preview, 'Prévia como visitante')
        self.assertContains(preview, 'Heroína pública')
        self.assertContains(preview, 'noindex, nofollow')
        self.assertEqual(self.client.post(action, {'action': 'publish'}).status_code, 302)
        self.client.logout()
        with CaptureQueriesContext(connection) as queries:
            first = self.client.get(public)
            second = self.client.get(public)
        self.assertContains(first, 'Heroína pública')
        self.assertContains(second, 'Classe pública')
        self.assertIn('no-store', first['Cache-Control'])
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
            ('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertEqual(writes, [])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(action, {'action': 'unpublish'}).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(public).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(public + '?preview=1'), 'Heroína pública')

    def test_public_page_excludes_private_data_for_every_viewer(self):
        TbPersonagem.objects.filter(pk=self.character.pk).update(publico=True)
        public = reverse('ficha_publica', args=[self.character.pk])
        for user in (None, self.owner, self.other, self.staff):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            response = self.client.get(public)
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            for secret in ('NOTA PRIVADA Q8', 'MESA PRIVADA Q8',
                           'HISTÓRIA PRIVADA Q8', '987654', '12345'):
                self.assertNotIn(secret, html)
            direct_payload = self.client.get(public + '?format=json',
                                             HTTP_ACCEPT='application/json')
            self.assertEqual(direct_payload.status_code, 200)
            self.assertTrue(direct_payload['Content-Type'].startswith('text/html'))
            for secret in ('NOTA PRIVADA Q8', 'MESA PRIVADA Q8',
                           'HISTÓRIA PRIVADA Q8', '987654', '12345'):
                self.assertNotIn(secret, direct_payload.content.decode())
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('personagem_publicacao',
                                                args=[self.character.pk]),
                                          {'action': 'unpublish'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('personagem_publicacao',
                                                args=[self.character.pk]),
                                          {'action': 'preferences',
                                           'description': 'TENTATIVA ALHEIA',
                                           'show_attributes': 'on'}).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('personagem_publicacao',
                                                args=[self.character.pk]),
                                          {'action': 'unpublish'}).status_code, 404)
        self.character.refresh_from_db()
        self.assertEqual(self.character.descricao_publica, '')
        self.assertFalse(self.character.mostrar_atributos_publicos)

    def test_public_route_is_read_only_for_all_viewers_and_methods(self):
        TbPersonagem.objects.filter(pk=self.character.pk).update(
            publico=True, mostrar_atributos_publicos=True)
        public = reverse('ficha_publica', args=[self.character.pk])
        baseline = TbPersonagem.objects.get(pk=self.character.pk)
        for user in (None, self.owner, self.other, self.staff):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            with CaptureQueriesContext(connection) as queries:
                first = self.client.get(public)
                second = self.client.get(public)
                head = self.client.head(public)
                post = self.client.post(public, {'action': 'unpublish'})
                put = self.client.put(public, data='{"publico":false}',
                                      content_type='application/json')
            self.assertEqual([first.status_code, second.status_code, head.status_code],
                             [200, 200, 200])
            self.assertEqual([post.status_code, put.status_code], [405, 405])
            self.assertEqual([q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
                ('INSERT ', 'UPDATE ', 'DELETE '))], [])
            current = TbPersonagem.objects.get(pk=self.character.pk)
            self.assertEqual(current.atualizado_em, baseline.atualizado_em)
            self.assertEqual(current.publico, baseline.publico)
            self.assertEqual(current.mostrar_atributos_publicos,
                             baseline.mostrar_atributos_publicos)

    def test_public_appearance_respects_owner_entitlements_and_image_safety(self):
        theme = TbCosmetico.objects.create(
            slug='tema-ember', tipo='tema', nome='Brasas',
            css_class='theme-ember', origem='loja_mm', escopo='ficha')
        frame = TbCosmetico.objects.create(
            slug='moldura-gold-trim', tipo='moldura', nome='Dourada',
            css_class='frame-gold-trim', origem='loja_mm', escopo='ficha')
        effect = TbCosmetico.objects.create(
            slug='efeito-soft-glow', tipo='efeito', nome='Brilho',
            css_class='effect-soft-glow', origem='loja_mm', escopo='ficha')
        invalidate_cosmetic_cache()
        TbPersonagem.objects.filter(pk=self.character.pk).update(
            publico=True, ficha_theme='ember', foto_frame='gold-trim',
            ficha_effect='soft-glow', foto_url='https://example.com/hero.png',
            ficha_background_url='javascript:alert(1)')
        public = reverse('ficha_publica', args=[self.character.pk])
        anonymous = self.client.get(public)
        self.assertEqual(anonymous.status_code, 200)
        self.assertNotContains(anonymous, 'theme-ember')
        self.assertNotContains(anonymous, 'frame-gold-trim')
        self.assertNotContains(anonymous, 'effect-soft-glow')
        self.assertNotContains(anonymous, 'javascript:')
        for item in (theme, frame, effect):
            TbUsuarioCosmetico.objects.create(
                user=self.owner, cosmetico=item, origem='compra_mm')
        entitled = self.client.get(public)
        self.assertContains(entitled, 'theme-ember')
        self.assertContains(entitled, 'frame-gold-trim')
        self.assertContains(entitled, 'effect-soft-glow')
        self.assertContains(entitled, 'https://example.com/hero.png')
        self.assertNotContains(entitled, 'javascript:')
        TbUsuarioCosmetico.objects.filter(user=self.owner, cosmetico=frame).update(
            suspenso_em=timezone.now())
        revoked = self.client.get(public)
        self.assertNotContains(revoked, 'frame-gold-trim')
        self.assertContains(revoked, 'theme-ember')
        TbPersonagem.objects.filter(pk=self.character.pk).update(
            ficha_background_url='https://example.com/background.webp')
        self.assertContains(self.client.get(public),
                            'https://example.com/background.webp')
        theme.escopo = 'perfil'
        theme.save(update_fields=['escopo'])
        invalidate_cosmetic_cache()
        self.assertNotContains(self.client.get(public), 'theme-ember')

    def test_private_preview_is_owner_only_and_archive_cannot_publish(self):
        public = reverse('ficha_publica', args=[self.character.pk])
        action = reverse('personagem_publicacao', args=[self.character.pk])
        for user in (None, self.other, self.staff):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            self.assertEqual(self.client.get(public + '?preview=1').status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(action, {'action': 'unknown'}).status_code, 400)
        TbPersonagem.objects.filter(pk=self.character.pk).update(arquivado=True)
        self.assertEqual(self.client.post(action, {'action': 'publish'}).status_code, 400)
        self.assertEqual(self.client.get(public).status_code, 404)

    def test_profile_and_owner_list_link_to_public_projection(self):
        public = reverse('ficha_publica', args=[self.character.pk])
        self.client.force_login(self.owner)
        owner_list = self.client.get(reverse('personagens'))
        self.assertContains(owner_list, public + '?preview=1')
        self.assertContains(owner_list, 'Publicar ficha')
        self.client.post(reverse('personagem_publicacao', args=[self.character.pk]),
                         {'action': 'publish'})
        owner_list = self.client.get(reverse('personagens'))
        self.assertContains(owner_list, 'Retirar publicação')
        self.assertContains(owner_list, public)
        self.assertContains(owner_list, public + '?preview=1')
        published_preview = self.client.get(public + '?preview=1')
        self.assertContains(published_preview, 'Prévia como visitante')
        self.assertContains(published_preview, 'noindex, nofollow')
        self.client.logout()
        profile = self.client.get(reverse('public_profile', args=[self.owner.username]))
        self.assertContains(profile, public)

    def test_social_image_only_uses_valid_published_portrait(self):
        public = reverse('ficha_publica', args=[self.character.pk])
        TbPersonagem.objects.filter(pk=self.character.pk).update(
            foto_url='/media/portraits/hero.png')
        self.client.force_login(self.owner)
        private_preview = self.client.get(public + '?preview=1')
        self.assertNotIn('property="og:image"', private_preview.content.decode())
        self.client.post(reverse('personagem_publicacao', args=[self.character.pk]),
                         {'action': 'publish'})
        self.client.logout()
        published = self.client.get(public)
        self.assertContains(published,
                            f'property="og:image" content="{published.context["site_origin"]}/media/portraits/hero.png"')
        TbPersonagem.objects.filter(pk=self.character.pk).update(
            foto_url='https://example.com/portrait.png')
        self.assertContains(self.client.get(public),
                            'property="og:image" content="https://example.com/portrait.png"')
        TbPersonagem.objects.filter(pk=self.character.pk).update(
            foto_url='javascript:alert(1)')
        self.assertNotIn('property="og:image"', self.client.get(public).content.decode())
        self.client.force_login(self.owner)
        self.client.post(reverse('personagem_publicacao', args=[self.character.pk]),
                         {'action': 'unpublish'})
        self.client.logout()
        self.assertEqual(self.client.get(public).status_code, 404)

    def test_archiving_unpublishes_and_blocks_operational_public_access(self):
        public = reverse('ficha_publica', args=[self.character.pk])
        operational = reverse('ficha_detail', args=[self.character.pk])
        TbPersonagem.objects.filter(pk=self.character.pk).update(publico=True)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('personagem_arquivar',
                                                  args=[self.character.pk])).status_code, 302)
        self.character.refresh_from_db()
        self.assertTrue(self.character.arquivado)
        self.assertFalse(self.character.publico)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(public).status_code, 404)
        self.assertEqual(self.client.get(operational).status_code, 404)
        # Dados antigos com Publico=True não podem contornar o bloqueio.
        TbPersonagem.objects.filter(pk=self.character.pk).update(publico=True)
        self.assertEqual(self.client.get(public).status_code, 404)
        self.assertEqual(self.client.get(operational).status_code, 404)

    def test_owner_preferences_are_separate_from_publication_and_private_lore(self):
        public = reverse('ficha_publica', args=[self.character.pk])
        action = reverse('personagem_publicacao', args=[self.character.pk])
        self.client.force_login(self.owner)
        description = 'Conto para visitantes <script>alert(1)</script>'
        self.assertEqual(self.client.post(action, {
            'action': 'preferences', 'description': description,
            'show_attributes': 'on', 'show_skills': 'on', 'show_summary': 'on',
        }).status_code, 302)
        self.character.refresh_from_db()
        self.assertFalse(self.character.publico)
        self.assertEqual(self.character.historia, 'HISTÓRIA PRIVADA Q8')
        self.assertEqual(self.character.descricao_publica, description)
        self.assertEqual(self.client.post(action, {
            'action': 'preferences', 'description': 'x' * 2001,
        }).status_code, 400)
        self.assertEqual(self.client.post(action, {'action': 'publish'}).status_code, 302)
        self.client.logout()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(public)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Conto para visitantes', html)
        self.assertIn('content="Conto para visitantes &lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('HISTÓRIA PRIVADA Q8', html)
        self.assertIn('Atributos públicos', html)
        self.assertIn('Perícias públicas', html)
        self.assertIn('Resumo mecânico público', html)
        mechanics = response.context['mechanics']
        self.assertEqual(len(mechanics['atributos']), 6)
        self.assertTrue(any(row['nome'] == 'Força' and row['valor'] == 10
                            for row in mechanics['atributos']))
        self.assertTrue(mechanics['pericias'])
        self.assertEqual(mechanics['resumo']['ca'], 10)
        self.assertIsNone(mechanics['resumo']['pv_maximo'])
        self.assertEqual([q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
            ('INSERT ', 'UPDATE ', 'DELETE '))], [])

    def test_mechanics_default_private_and_independent_visibility(self):
        action = reverse('personagem_publicacao', args=[self.character.pk])
        public = reverse('ficha_publica', args=[self.character.pk])
        self.client.force_login(self.owner)
        self.client.post(action, {'action': 'publish'})
        self.client.logout()
        baseline = self.client.get(public)
        self.assertNotContains(baseline, 'Atributos públicos')
        self.assertNotContains(baseline, 'Perícias públicas')
        self.assertNotContains(baseline, 'Resumo mecânico público')
        self.client.force_login(self.owner)
        self.client.post(action, {'action': 'preferences', 'show_skills': 'on'})
        self.client.logout()
        skills = self.client.get(public)
        self.assertContains(skills, 'Perícias públicas')
        self.assertNotContains(skills, 'Atributos públicos')
        self.assertNotContains(skills, 'Resumo mecânico público')
        self.client.force_login(self.owner)
        self.client.post(action, {'action': 'preferences'})
        self.client.logout()
        hidden = self.client.get(public)
        self.assertNotContains(hidden, 'Perícias públicas')
