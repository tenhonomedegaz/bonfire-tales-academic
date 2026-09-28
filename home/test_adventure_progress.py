from unittest.mock import MagicMock, patch

from django.db import ProgrammingError
from django.urls import reverse

from home.models import TbPersonagem, TbPersonagemAventura, UserProfile
from home.test_criador import _CriadorBase


class AdventureProgressProfileTests(_CriadorBase):
    def setUp(self):
        self.owner = self._novo_usuario('adventure-progress-owner')
        self.staff = self._novo_usuario('adventure-progress-staff', staff=True)
        profile = UserProfile.objects.get(user=self.owner)
        profile.discord_user_id = '123456789012345678'
        profile.save(update_fields=['discord_user_id'])
        self.archived = TbPersonagem.objects.create(
            dono=self.owner, nome='Ficha arquivada', arquivado=True, aventuras=5)
        TbPersonagemAventura.objects.create(
            id_personagem=self.archived, nome_aventura='Missão válida', qtd_aventuras=3)
        TbPersonagemAventura.objects.create(
            id_personagem=self.archived, nome_aventura='Missão estornada',
            qtd_aventuras=2, revertido=True)
        self.url = reverse('public_profile', args=[self.owner.username])

    def test_owner_sees_distinct_sources_and_legacy_balance_visitor_does_not(self):
        external = MagicMock()
        external.order_by.return_value.values.return_value = [{
            'id': 'bot-log-1', 'characterName': 'Ficha externa', 'adventuresPlayed': 7,
        }]
        with patch('home.models.BotCharacterLog.objects.filter', return_value=external) as bot_query:
            self.client.force_login(self.owner)
            owner_page = self.client.get(self.url)
            self.assertContains(owner_page, 'Site: 3 aventuras')
            self.assertContains(owner_page, 'Saldo sem lançamento identificado: 2')
            self.assertContains(owner_page, 'Ficha externa: 7 aventuras declaradas')
            self.assertContains(owner_page, 'fontes ainda não foram conciliadas')
            bot_query.assert_called_once_with(discordUserId='123456789012345678')

        self.client.logout()
        with patch('home.conquistas.progresso_aventuras_por_origem') as progress:
            visitor_page = self.client.get(self.url)
            progress.assert_not_called()
        self.assertNotContains(visitor_page, 'Progresso de aventuras')
        self.assertNotContains(visitor_page, 'Ficha externa')
        self.client.force_login(self.staff)
        staff_page = self.client.get(self.url)
        self.assertContains(staff_page, 'Site: 3 aventuras')

    def test_missing_external_table_does_not_hide_verified_site_progress(self):
        self.client.force_login(self.owner)
        with patch('home.models.BotCharacterLog.objects.filter',
                   side_effect=ProgrammingError('bot indisponível')):
            page = self.client.get(self.url)
        self.assertContains(page, 'Site: 3 aventuras')
        self.assertContains(page, 'Dados do bot temporariamente indisponíveis')

    def test_divergent_balance_is_flagged_without_inventing_missions(self):
        self.archived.aventuras = 1
        self.archived.save(update_fields=['aventuras'])
        self.client.force_login(self.owner)
        with patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()) as bot_query:
            # A lista externa vazia é um caso válido; a divergência é do ledger local.
            bot_query.return_value.order_by.return_value.values.return_value = []
            page = self.client.get(self.url)
        self.assertContains(page, 'Site: 3 aventuras')
        self.assertContains(page, '1 ficha com saldo inferior ao ledger')
