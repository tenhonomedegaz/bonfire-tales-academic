from unittest.mock import MagicMock, patch

from django.db import ProgrammingError
from django.urls import reverse

from home.models import TbPersonagem, TbPersonagemAventura, UserProfile
from home.conquistas import progresso_aventuras_por_origem
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

    def test_public_profile_never_renders_or_queries_adventure_tracking(self):
        for visitor in (None, self.owner, self.staff):
            with self.subTest(visitor=visitor):
                self.client.logout()
                if visitor:
                    self.client.force_login(visitor)
                with patch('home.conquistas.progresso_aventuras_por_origem') as progress:
                    page = self.client.get(self.url)
                    progress.assert_not_called()
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, 'data-adventure-progress')
                self.assertNotContains(page, 'Progresso de aventuras')
                self.assertNotContains(page, 'Saldo sem lançamento identificado')

    def test_community_reward_is_excluded_from_site_adventure_progress(self):
        TbPersonagemAventura.objects.create(
            id_personagem=self.archived, nome_aventura='Recompensa da comunidade',
            qtd_aventuras=1, origem='recompensa_comunidade')
        self.archived.aventuras += 1
        self.archived.save(update_fields=['aventuras'])

        progress = progresso_aventuras_por_origem(self.owner)

        self.assertEqual(progress['site_total'], 3)
        self.assertEqual(progress['saldo_sem_ledger'], 2)

    def test_individual_bot_credits_deduplicate_exact_site_link(self):
        TbPersonagemAventura.objects.filter(id_personagem=self.archived).update(revertido=True)
        TbPersonagemAventura.objects.create(
            id_personagem=self.archived, nome_aventura='Vinculada', qtd_aventuras=1,
            detalhes_json={'bot_quest_id': 'quest-linked'})
        quest_query = MagicMock()
        quest_query.values.return_value = [
            {'id': 'quest-linked', 'questPlayers': [{
                'userId': '123456789012345678', 'rewardAmount': 1,
                'rewardFinalizedAt': '2026-09-28T12:00:00Z'}]},
            {'id': 'quest-only', 'questPlayers': [{
                'userId': '123456789012345678', 'rewardAmount': 2,
                'rewardFinalizedAt': '2026-09-28T13:00:00Z'}]},
        ]
        with patch('home.models.BotQuest.objects.filter', return_value=quest_query), \
             patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
            progress = progresso_aventuras_por_origem(self.owner, '123456789012345678')
            self.assertEqual(progress['total_conciliado'], 3)
            self.assertEqual(progress['bot_creditos_adicionais'], 2)
            self.client.force_login(self.owner)
            self.assertNotContains(self.client.get(self.url), 'Total rastreável por lançamentos')

    def test_reverted_bot_link_stays_out_of_total_until_explicit_relink(self):
        TbPersonagemAventura.objects.filter(id_personagem=self.archived).update(revertido=True)
        ledger = TbPersonagemAventura.objects.create(
            id_personagem=self.archived, nome_aventura='Vinculada', qtd_aventuras=2,
            detalhes_json={'bot_quest_id': 'quest-reverted'})
        quest_query = MagicMock()
        quest_query.values.return_value = [{'id': 'quest-reverted', 'questPlayers': [{
            'userId': '123456789012345678', 'rewardAmount': 2,
            'rewardFinalizedAt': '2026-09-28T13:00:00Z'}]}]
        with patch('home.models.BotQuest.objects.filter', return_value=quest_query), \
             patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
            active = progresso_aventuras_por_origem(self.owner, '123456789012345678')
            self.assertEqual(active['total_conciliado'], 2)
            ledger.revertido = True
            ledger.save(update_fields=['revertido'])
            reversed_progress = progresso_aventuras_por_origem(
                self.owner, '123456789012345678')
            self.assertEqual(reversed_progress['total_conciliado'], 0)
            self.assertEqual(reversed_progress['bot_creditos_estornados'], 1)
            self.client.force_login(self.owner)
            self.assertNotContains(self.client.get(self.url),
                                'missão vinculada estornada, excluída do total')
            TbPersonagemAventura.objects.create(
                id_personagem=self.archived, nome_aventura='Relançada', qtd_aventuras=2,
                detalhes_json={'bot_quest_id': 'quest-reverted'})
            relinked = progresso_aventuras_por_origem(self.owner, '123456789012345678')
            self.assertEqual(relinked['total_conciliado'], 2)
            self.assertEqual(relinked['bot_creditos_estornados'], 0)

    def test_ambiguous_overlap_or_unproved_bot_credit_has_no_total(self):
        quest_query = MagicMock()
        quest_query.values.return_value = [{'id': 'quest-only', 'questPlayers': [{
            'userId': '123456789012345678', 'rewardAmount': 2,
            'rewardFinalizedAt': '2026-09-28T13:00:00Z'}]}]
        with patch('home.models.BotQuest.objects.filter', return_value=quest_query), \
             patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
            progress = progresso_aventuras_por_origem(self.owner, '123456789012345678')
        self.assertIsNone(progress['total_conciliado'])  # Site sem ID pode ser a mesma missão.
        TbPersonagemAventura.objects.filter(id_personagem=self.archived).update(revertido=True)
        quest_query.values.return_value = [{'id': 'quest-unproved', 'questPlayers': [{
            'userId': '123456789012345678'}]}]
        with patch('home.models.BotQuest.objects.filter', return_value=quest_query), \
             patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
            progress = progresso_aventuras_por_origem(self.owner, '123456789012345678')
        self.assertIsNone(progress['total_conciliado'])
        self.assertEqual(progress['bot_sem_prova'], 1)

    def test_linked_credit_disagreement_or_bot_failure_never_publishes_total(self):
        TbPersonagemAventura.objects.filter(id_personagem=self.archived).update(revertido=True)
        TbPersonagemAventura.objects.create(
            id_personagem=self.archived, nome_aventura='Divergente', qtd_aventuras=1,
            detalhes_json={'bot_quest_id': 'quest-mismatch'})
        quest_query = MagicMock()
        quest_query.values.return_value = [{'id': 'quest-mismatch', 'questPlayers': [{
            'userId': '123456789012345678', 'rewardAmount': 2,
            'rewardFinalizedAt': '2026-09-28T13:00:00Z'}]}]
        with patch('home.models.BotQuest.objects.filter', return_value=quest_query), \
             patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
            progress = progresso_aventuras_por_origem(self.owner, '123456789012345678')
        self.assertEqual(progress['conflitos_vinculo'], 1)
        self.assertIsNone(progress['total_conciliado'])
        with patch('home.models.BotQuest.objects.filter',
                   side_effect=ProgrammingError('bot indisponível')), \
             patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
            progress = progresso_aventuras_por_origem(self.owner, '123456789012345678')
        self.assertFalse(progress['bot_creditos_disponiveis'])
        self.assertIsNone(progress['total_conciliado'])
