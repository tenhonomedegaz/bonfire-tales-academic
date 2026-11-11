"""Focused contract checks for the authorized site participation flow."""

from django.contrib.auth import get_user_model
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from .models import TbPerfilMestre


class MasterParticipationFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.player = user_model.objects.create_user('player_participation', password='test-pass')
        self.other = user_model.objects.create_user('other_participation', password='test-pass')
        self.staff = user_model.objects.create_superuser('staff_participation', 'staff@example.test', 'test-pass')

    def test_request_review_edit_and_directory_are_distinct_from_discord(self):
        self.client.force_login(self.player)
        response = self.client.post(reverse('master_request'))
        self.assertEqual(response.status_code, 302)
        profile = TbPerfilMestre.objects.get(user=self.player)
        self.assertEqual(profile.status_mestre, 'pendente')
        self.assertEqual(profile.versao, 1)
        self.client.post(reverse('master_request'))
        profile.refresh_from_db()
        self.assertEqual(profile.versao, 1)
        self.assertEqual(self.client.get(reverse('participation_edit')).status_code, 403)
        self.assertEqual(self.client.get(reverse('masters_directory')).context['masters'], [])

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('master_authorize', args=[self.player.pk]), {
            'acao': 'autorizar', 'confirmar': 'sim', 'versao': '1',
        }).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('master_authorize', args=[self.player.pk]), {
            'acao': 'autorizar', 'confirmar': 'sim', 'versao': '0',
        }).status_code, 409)
        self.assertEqual(self.client.post(reverse('master_authorize', args=[self.player.pk]), {
            'acao': 'autorizar', 'confirmar': 'sim', 'versao': '1',
        }).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.status_mestre, 'aprovado')
        self.assertFalse(profile.listado)

        self.client.force_login(self.player)
        self.assertEqual(self.client.post(reverse('participation_edit'), {
            'modo': 'mestre', 'apresentacao': 'Histórias de Cinéria', 'estilo': 'Investigação',
            'disponibilidade': 'Sábado', 'experiencia': '', 'combinados': '', 'listado': 'on',
        }).status_code, 302)
        self.assertEqual(len(self.client.get(reverse('masters_directory')).context['masters']), 1)
        self.client.force_login(self.staff)
        profile.refresh_from_db()
        self.assertEqual(self.client.post(reverse('master_authorize', args=[self.player.pk]), {
            'acao': 'suspender', 'confirmar': 'sim', 'versao': str(profile.versao),
        }).status_code, 302)
        self.assertEqual(self.client.get(reverse('masters_directory')).context['masters'], [])

    def test_sensitive_posts_keep_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.player)
        self.assertEqual(client.post(reverse('master_request')).status_code, 403)
        self.assertFalse(TbPerfilMestre.objects.filter(user=self.player).exists())
        client.force_login(self.staff)
        self.assertEqual(client.post(reverse('master_authorize', args=[self.player.pk]), {
            'acao': 'autorizar', 'confirmar': 'sim', 'versao': '0',
        }).status_code, 403)

    def test_public_portfolio_shows_saved_stories_only_while_listed_and_approved(self):
        profile = TbPerfilMestre.objects.create(
            user=self.player, modo='mestre', status_mestre='aprovado', listado=True,
            experiencia='Três campanhas narradas', combinados='Respeito à mesa',
        )
        url = reverse('public_profile', args=[self.player.username]) + '?aba=mestre'
        public = self.client.get(url)
        self.assertContains(public, 'Três campanhas narradas')
        self.assertContains(public, 'Respeito à mesa')

        profile.listado = False
        profile.save(update_fields=['listado'])
        private = self.client.get(url)
        self.assertNotContains(private, 'Três campanhas narradas')
        self.assertNotContains(private, 'Respeito à mesa')

        profile.listado = True
        profile.status_mestre = 'suspenso'
        profile.save(update_fields=['listado', 'status_mestre'])
        suspended = self.client.get(url)
        self.assertNotContains(suspended, 'Três campanhas narradas')
        self.assertNotContains(suspended, 'Respeito à mesa')

    def test_visitor_can_return_from_master_profile_and_find_empty_announcements(self):
        TbPerfilMestre.objects.create(
            user=self.player, modo='mestre', status_mestre='aprovado',
            listado=True, apresentacao='Histórias da comunidade')
        directory_url = reverse('masters_directory')
        profile_url = reverse('public_profile', args=[self.player.username])
        missions_url = reverse('sistemas_missoes')

        directory = self.client.get(directory_url)
        self.assertContains(directory, profile_url + '?aba=mestre')
        self.assertContains(directory, missions_url + '#anuncios')
        profile = self.client.get(profile_url + '?aba=mestre')
        self.assertContains(profile, f'href="{directory_url}" class="public-profile-back"')
        self.assertNotContains(profile, '#g01-masters-directory')
        missions = self.client.get(missions_url)
        self.assertContains(missions, 'id="anuncios"')
        self.assertContains(missions, 'Nenhuma mesa anunciada no site no momento.')
