from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import ProgrammingError
from django.urls import reverse

from home.models import TbEventoConquista, TbPersonagem, TbPersonagemAventura, UserProfile
from home.conquistas import progresso_aventuras_por_origem
from home.test_criador import _CriadorBase


class AdventureBotLinkTests(_CriadorBase):
    def setUp(self):
        self.owner = self._novo_usuario('quest-link-owner')
        self.staff = self._novo_usuario('quest-link-staff', staff=True)
        profile = UserProfile.objects.get(user=self.owner)
        profile.discord_user_id = '123456789012345678'
        profile.save(update_fields=['discord_user_id'])
        self.character = TbPersonagem.objects.create(dono=self.owner, nome='Aventureiro', nivel=1)
        self.url = reverse('personagem_registrar_aventuras', args=[self.character.pk])
        self.client.force_login(self.staff)

    def launch(self, quest_id='quest-123', quantity=1):
        return self.client.post(self.url, {
            'nome_aventura': 'Missão confirmada', 'mestre': self.staff.pk,
            'data_missao': '2026-09-28', 'aventuras': quantity,
            'bot_quest_id': quest_id,
        })

    def bot(self, *, status='finished', player='123456789012345678', reward=None,
            removed=False, removed_with_reward=False, partial_reward=None):
        participant = {'userId': player}
        if removed:
            participant.update(removedAt='2026-09-28T10:00:00Z',
                               removedWithReward=removed_with_reward,
                               rewardAmount=partial_reward)
        quest = SimpleNamespace(id='quest-123', status=status,
                                questPlayers=[participant],
                                rewardAventurasOverride=reward,
                                endDate=datetime(2026, 9, 28, 12, tzinfo=timezone.utc))
        query = MagicMock()
        query.only.return_value.first.return_value = quest if status == 'finished' else None
        return patch('home.models.BotQuest.objects.filter', return_value=query)

    def test_exact_finished_participant_link_is_recorded_once_and_survives_reversal(self):
        with self.bot():
            self.assertEqual(self.launch().status_code, 302)
            ledger = TbPersonagemAventura.objects.get()
            self.assertEqual(ledger.detalhes_json['bot_quest_id'], 'quest-123')
            fact = TbEventoConquista.objects.get(tipo='adventure_recorded')
            self.assertEqual(fact.payload_json['bot_quest_id'], 'quest-123')
            self.assertEqual(fact.payload_json['bot_quest_proof']['discord_user_id'],
                             '123456789012345678')
            self.assertEqual(fact.payload_json['bot_quest_proof']['quest_end_at'],
                             '2026-09-28T12:00:00+00:00')
            self.assertIn('verified_at', fact.payload_json['bot_quest_proof'])
            self.assertEqual(progresso_aventuras_por_origem(self.owner)['site_vinculadas_ao_bot'], 1)
            self.client.force_login(self.owner)
            with patch('home.models.BotCharacterLog.objects.filter', return_value=MagicMock()):
                page = self.client.get(reverse('public_profile', args=[self.owner.username]))
            self.assertContains(page, 'Vinculadas por ID a missões finalizadas do bot: 1')
            self.client.force_login(self.staff)
            self.assertEqual(self.launch().status_code, 302)
            self.assertEqual(TbPersonagemAventura.objects.count(), 1)
            self.assertEqual(TbEventoConquista.objects.count(), 1)
            self.client.post(reverse('personagem_reverter_aventura',
                                     args=[self.character.pk, ledger.pk]))
            ledger.refresh_from_db()
            self.assertTrue(ledger.revertido)
            self.assertEqual(progresso_aventuras_por_origem(self.owner)['site_vinculadas_ao_bot'], 0)
            self.assertEqual(TbEventoConquista.objects.get(
                tipo='adventure_reverted').payload_json['bot_quest_id'], 'quest-123')
            self.assertEqual(self.launch().status_code, 302)
            self.assertEqual(TbPersonagemAventura.objects.count(), 2)

    def test_unconfirmed_mismatch_or_missing_bot_never_credits(self):
        with self.bot(player='different'):
            self.launch()
        with self.bot(status='running'):
            self.launch()
        with self.bot(reward=2):
            self.launch(quantity=1)
        with self.bot(removed=True):
            self.launch()
        with patch('home.models.BotQuest.objects.filter',
                   side_effect=ProgrammingError('bot unavailable')):
            self.launch()
        self.character.refresh_from_db()
        self.assertEqual(self.character.aventuras, 0)
        self.assertEqual(TbPersonagemAventura.objects.count(), 0)
        self.assertEqual(TbEventoConquista.objects.count(), 0)

    def test_partial_reward_requires_bot_amount_and_preserves_proof(self):
        with self.bot(removed=True, removed_with_reward=True, partial_reward=2):
            self.launch(quantity=1)
            self.assertFalse(TbPersonagemAventura.objects.exists())
            self.launch(quantity=2)
        ledger = TbPersonagemAventura.objects.get()
        proof = ledger.detalhes_json['bot_quest_proof']
        self.assertTrue(proof['removed_with_reward'])
        self.assertEqual(proof['reward_amount'], 2)
        self.assertEqual(TbEventoConquista.objects.get(
            tipo='adventure_recorded').payload_json['bot_quest_proof'], proof)

    def test_link_without_verified_discord_identity_is_refused(self):
        profile = UserProfile.objects.get(user=self.owner)
        profile.discord_user_id = None
        profile.save(update_fields=['discord_user_id'])
        with self.bot():
            self.launch()
        self.assertFalse(TbPersonagemAventura.objects.exists())
