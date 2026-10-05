"""A vitrine pública só lê campos expressamente liberados pelo personagem."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import TbClasse, TbPersonagem, TbPersonagemClasse, TbRaca


class PublicCharacterSheetTests(TestCase):
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
        self.client.logout()
        profile = self.client.get(reverse('public_profile', args=[self.owner.username]))
        self.assertContains(profile, public)

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
