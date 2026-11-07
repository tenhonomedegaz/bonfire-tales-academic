"""A vitrine de jogadores só revela fichas que o dono publicou."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import TbPersonagem, UserProfile


class JogadoresPublicPrivacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('vitrine-owner')
        cls.private_owner = User.objects.create_user('vitrine-private')
        cls.public = TbPersonagem.objects.create(
            dono=cls.owner, nome='Heroi publicado', publico=True)
        cls.private = TbPersonagem.objects.create(
            dono=cls.owner, nome='Segredo da mesa', publico=False)
        TbPersonagem.objects.create(
            dono=cls.private_owner, nome='Outro segredo', publico=False)

    def test_vitrine_conta_busca_e_abre_somente_fichas_publicas(self):
        url = reverse('jogadores')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        cards = {card['user'].username: card for card in response.context['cards']}
        self.assertEqual(cards[self.owner.username]['character_count'], 1)
        self.assertEqual(cards[self.private_owner.username]['character_count'], 0)
        self.assertContains(response, reverse('ficha_publica', args=[self.public.pk]))
        self.assertNotContains(response, reverse('ficha_detail', args=[self.public.pk]))
        self.assertNotContains(response, self.private.nome)
        self.assertNotContains(response, '2 personagens')

        filtered = self.client.get(url + '?filtro=personagens')
        filtered_users = [card['user'].username for card in filtered.context['cards']]
        self.assertIn(self.owner.username, filtered_users)
        self.assertNotIn(self.private_owner.username, filtered_users)
        searched = self.client.get(url + '?q=Segredo%20da%20mesa')
        self.assertNotContains(searched, self.owner.username)

    def test_visitas_anonimas_nao_criam_perfil_ausente(self):
        UserProfile.objects.filter(user=self.private_owner).delete()
        url = reverse('jogadores')
        with CaptureQueriesContext(connection) as queries:
            first = self.client.get(url)
            second = self.client.get(url)
        self.assertContains(first, self.private_owner.username)
        self.assertContains(second, self.private_owner.username)
        self.assertFalse(UserProfile.objects.filter(user=self.private_owner).exists())
        self.assertEqual([
            q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
                ('INSERT ', 'UPDATE ', 'DELETE '))
        ], [])

    def test_ordem_por_atividade_ignora_atualizacao_privada(self):
        other = get_user_model().objects.create_user('vitrine-ativo')
        visible = TbPersonagem.objects.create(
            dono=other, nome='Outro heroi publicado', publico=True)
        now = timezone.now()
        TbPersonagem.objects.filter(pk=self.public.pk).update(
            atualizado_em=now - timedelta(days=3))
        TbPersonagem.objects.filter(pk=visible.pk).update(
            atualizado_em=now - timedelta(days=2))
        TbPersonagem.objects.filter(pk=self.private.pk).update(
            atualizado_em=now)
        response = self.client.get(reverse('jogadores') + '?ordem=atividade')
        names = [card['user'].username for card in response.context['cards']]
        self.assertLess(names.index(other.username), names.index(self.owner.username))
