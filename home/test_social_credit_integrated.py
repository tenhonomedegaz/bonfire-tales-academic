"""The community reward remains recoverable after its funding story is hidden."""

import json
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.models import (
    SocialCreditEntry, SocialCreditPolicy, SocialCreditReaderRecognition,
    SocialCreditRedemption, SocialCreditWallet, TbCronica, TbCronicaDenuncia,
    TbPersonagem, TbPersonagemAventura, TbTransacao,
)
from home.social_credits import (
    reverse_moderated_story_credits, reverse_social_redemption,
    settle_reader_milestones,
)
from home.views import _cronica_pending_snapshot


class CommunityRewardLifecycleTests(TestCase):
    def test_publication_readers_redemption_and_moderation_recover_once(self):
        users = get_user_model()
        author = users.objects.create_user('lifecycle-author', password='test')
        reader = users.objects.create_user('lifecycle-reader', password='test')
        second_reader = users.objects.create_user('lifecycle-reader-2', password='test')
        reviewer = users.objects.create_user('lifecycle-reviewer', password='test', is_staff=True)
        reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronica'))
        moderator = users.objects.create_user('lifecycle-moderator', password='test', is_staff=True)
        moderator.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronicadenuncia'))
        admin = users.objects.create_superuser('lifecycle-admin', 'admin@example.test', 'test')
        character = TbPersonagem.objects.create(dono=author, nome='Personagem do autor')
        policy = SocialCreditPolicy.objects.create(
            version='lifecycle-test-only', first_publication_amount=7, active=True,
            reader_recognition_enabled=True, reader_milestone_size=2,
            reader_milestone_amount=5, reader_consolidation_hours=24,
            reader_story_credit_cap=5, reader_author_period_credit_cap=5,
            reader_period_days=30, redemption_enabled=True, redemption_cost=5,
            redemption_gold_pc=200, redemption_gold_source='Tabela ficticia do teste',
            redemption_counts_for_progression=False, redemption_period_days=30,
            redemption_period_limit=1, redemption_character_limit=1,
        )
        story = TbCronica.objects.create(
            titulo='Relato do ciclo', slug='relato-do-ciclo',
            conteudo_markdown='Texto para revisao', autor=author, status='pendente',
        )

        self.client.force_login(reviewer)
        self.assertEqual(self.client.post(
            reverse('cronica_review_action', args=[story.pk]),
            json.dumps({'action': 'aprovar', 'expected_snapshot': _cronica_pending_snapshot(story)}),
            content_type='application/json',
        ).status_code, 200)
        story.refresh_from_db()
        self.assertEqual(story.status, 'aprovada')
        for account in (reader, second_reader):
            self.client.force_login(account)
            self.assertEqual(self.client.post(
                reverse('cronica_curtir', args=[story.pk]),
                json.dumps({'curtido': True}), content_type='application/json',
            ).status_code, 200)
        SocialCreditReaderRecognition.objects.filter(cronica=story).update(
            first_seen_at=timezone.now() - timedelta(days=2))
        self.assertEqual(len(settle_reader_milestones(policy.pk, story.pk)), 1)
        self.assertEqual(SocialCreditWallet.objects.get(user=author).balance, 12)

        self.client.force_login(author)
        request_id = uuid4()
        payload = {'action': 'redeem_social_credit', 'character_id': character.pk,
                   'request_id': str(request_id)}
        self.assertEqual(self.client.post(reverse('profile'), payload).status_code, 200)
        self.assertEqual(self.client.post(reverse('profile'), payload).status_code, 200)
        redemption = SocialCreditRedemption.objects.get(request_id=request_id)
        self.assertEqual(SocialCreditWallet.objects.get(user=author).balance, 7)
        self.assertEqual(TbPersonagemAventura.objects.filter(
            id_personagem=character, origem='recompensa_comunidade').count(), 1)

        self.client.force_login(reader)
        self.assertEqual(self.client.post(reverse('cronica_denunciar', args=[story.pk]),
                                          {'motivo': 'Conteudo inadequado'}).status_code, 302)
        report = TbCronicaDenuncia.objects.get(cronica=story, comentario__isnull=True)
        self.client.force_login(moderator)
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]),
                                          {'action': 'ocultar'}).status_code, 302)
        self.assertEqual(settle_reader_milestones(policy.pk, story.pk), [])
        self.assertEqual(reverse_moderated_story_credits(
            report.pk, actor_id=admin.pk)[1], 'review_required')
        self.assertEqual(SocialCreditWallet.objects.get(user=author).balance, 7)

        self.assertEqual(reverse_social_redemption(
            redemption.pk, actor_id=admin.pk, reason='Crônica ocultada')[1], 'reversed')
        reversals, state = reverse_moderated_story_credits(report.pk, actor_id=admin.pk)
        self.assertEqual((state, len(reversals)), ('reversed', 2))
        self.assertEqual(reverse_moderated_story_credits(
            report.pk, actor_id=admin.pk), ([], 'nothing_to_reverse'))
        self.assertEqual(reverse_social_redemption(
            redemption.pk, actor_id=admin.pk, reason='Repetição')[1], 'already_reversed')

        character.refresh_from_db()
        self.assertEqual((character.aventuras, character.carteira_pc), (0, 0))
        self.assertEqual(SocialCreditWallet.objects.get(user=author).balance, 0)
        self.assertEqual(SocialCreditEntry.objects.count(), 6)
        self.assertEqual(TbTransacao.objects.filter(id_personagem=character).count(), 2)
        redemption.refresh_from_db()
        self.assertIsNotNone(redemption.reversed_at)
        report.refresh_from_db()
        self.assertEqual([event['acao'] for event in report.historico_decisoes[-2:]],
                         ['credit_reversal_review', 'credit_reversal'])
