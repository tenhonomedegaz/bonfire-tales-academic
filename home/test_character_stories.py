from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from home.character_stories import (decide_story, digest, edit_ticket, notification_context,
    review_ticket, save_story, story_context)
from home.character_story_models import CharacterStorySubmission
from home.models import TbPersonagem
from home.portal_models import PortalRequest


class CharacterStoryTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('story-owner')
        self.reviewer = users.objects.create_user('story-loremaster', is_staff=False)
        self.other = users.objects.create_user('story-other', is_staff=True)
        self.reviewer.user_permissions.add(Permission.objects.get(codename='review_portal_historia'))
        self.person = TbPersonagem.objects.create(dono=self.owner, nome='Personagem com história',
            historia='Texto original', nivel=5, aventuras=30, carteira_pc=12345, publico=False)

    def submit(self, text='História enviada'):
        self.person.refresh_from_db()
        return save_story(actor=self.owner, character_id=self.person.pk, text=text,
                          ticket=edit_ticket(self.owner, self.person), submit=True)

    def decide(self, item, action='changes', feedback='Falta explicar a origem da família.'):
        item = CharacterStorySubmission.objects.select_related('character').get(pk=item.pk)
        return decide_story(actor=self.reviewer, submission_id=item.pk, action=action,
                            feedback=feedback, ticket=review_ticket(self.reviewer, item))

    def test_submit_notifications_feedback_resubmit_and_approve(self):
        self.assertFalse(story_context(self.person)['approved'])
        item = self.submit()
        self.assertEqual(notification_context(self.reviewer)['pending_character_stories_count'], 1)
        self.assertEqual(notification_context(self.other)['pending_character_stories_count'], 0)
        self.decide(item)
        self.assertEqual(notification_context(self.owner)['character_story_changes_count'], 1)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('character_story', args=[self.person.pk]))
        self.assertContains(response, 'Falta explicar a origem da família.')
        self.assertContains(self.client.get(reverse('character_stories_inbox')), 'Ver história e pareceres')
        self.assertContains(response, 'Ver devolutivas')
        new = self.submit('História com a origem explicada')
        self.assertEqual(notification_context(self.owner)['character_story_changes_count'], 0)
        self.decide(new, action='approved', feedback='Agora está coerente com o cenário.')
        self.person.refresh_from_db()
        self.assertTrue(story_context(self.person)['approved'])
        self.assertEqual((self.person.nivel, self.person.aventuras, self.person.carteira_pc, self.person.publico),
                         (5, 30, 12345, False))
        self.assertEqual(PortalRequest.objects.count(), 0)
        self.assertContains(self.client.get(reverse('character_story', args=[self.person.pk])),
                            'Agora está coerente com o cenário.')

    def test_edit_after_submission_cannot_be_approved_and_old_approval_is_not_inherited(self):
        item = self.submit()
        self.person.refresh_from_db()
        save_story(actor=self.owner, character_id=self.person.pk, text='Novo rascunho',
                   ticket=edit_ticket(self.owner, self.person))
        with self.assertRaises(ValidationError):
            self.decide(item, action='approved', feedback='')
        new = self.submit('Versão corrigida')
        item.refresh_from_db()
        self.assertEqual(item.status, 'superseded')
        self.decide(new, action='approved', feedback='')
        TbPersonagem.objects.filter(pk=self.person.pk).update(historia='Edição externa posterior')
        self.person.refresh_from_db()
        self.assertFalse(story_context(self.person)['approved'])

    def test_idempotent_submit_and_review_do_not_duplicate_versions_or_feedback(self):
        token = edit_ticket(self.owner, self.person)
        data = dict(actor=self.owner, character_id=self.person.pk, text='Texto único', ticket=token, submit=True)
        item = save_story(**data)
        self.assertEqual(save_story(**data).pk, item.pk)
        self.assertEqual(self.submit('Texto único').pk, item.pk)
        token = review_ticket(self.reviewer, item)
        decision = dict(actor=self.reviewer, submission_id=item.pk, action='changes',
                        feedback='Explique melhor este ponto.', ticket=token)
        self.assertEqual(decide_story(**decision).pk, decide_story(**decision).pk)
        self.assertEqual(CharacterStorySubmission.objects.count(), 1)

    def test_permissions_ownership_self_review_and_changes_require_feedback(self):
        item = self.submit()
        with self.assertRaises(PermissionDenied):
            edit_ticket(self.other, self.person)
        with self.assertRaises(PermissionDenied):
            review_ticket(self.other, item)
        self.owner.user_permissions.add(Permission.objects.get(codename='review_portal_historia'))
        with self.assertRaises(PermissionDenied):
            review_ticket(get_user_model().objects.get(pk=self.owner.pk), item)
        with self.assertRaises(ValidationError):
            self.decide(item, feedback='')
        token = review_ticket(self.reviewer, item)
        self.reviewer.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            decide_story(actor=self.reviewer, submission_id=item.pk, action='approved', feedback='', ticket=token)

    def test_stale_owner_form_tampered_ticket_transfer_and_transaction_rollback(self):
        token = edit_ticket(self.owner, self.person)
        first = self.submit()
        with self.assertRaises(ValidationError):
            save_story(actor=self.owner, character_id=self.person.pk, text='Aba velha', ticket=token, submit=True)
        with self.assertRaises(ValidationError):
            save_story(actor=self.owner, character_id=self.person.pk, text='Texto', ticket='invalido', submit=True)
        self.person.refresh_from_db()
        token = edit_ticket(self.owner, self.person)
        with patch.object(CharacterStorySubmission.objects, 'create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                save_story(actor=self.owner, character_id=self.person.pk, text='Texto novo', ticket=token, submit=True)
        first.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual((first.status, self.person.historia), ('pending', 'História enviada'))
        token = review_ticket(self.reviewer, first)
        TbPersonagem.objects.filter(pk=self.person.pk).update(dono=self.other)
        with self.assertRaises(PermissionDenied):
            decide_story(actor=self.reviewer, submission_id=first.pk, action='approved', feedback='', ticket=token)

    def test_http_preview_changes_and_player_response_remain_private(self):
        item = self.submit('Texto <script>nunca executar()</script>')
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('gestao:editorial'), {'source': 'historia'})
        self.assertContains(response, self.person.nome)
        self.assertEqual(response.context['pending_character_stories_count'], 1)
        self.assertContains(response, 'Histórias para aprovar')
        url = reverse('gestao:story_review', args=[item.pk])
        response = self.client.get(url)
        self.assertContains(response, '&lt;script&gt;nunca executar()&lt;/script&gt;')
        self.assertNotContains(response, '<script>nunca executar()</script>')
        token = response.context['form'].initial['ticket']
        self.assertEqual(self.client.post(url, {'action': 'changes', 'feedback': 'Explique o vínculo com a região.',
                                              'ticket': token}).status_code, 302)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('character_story', args=[self.person.pk])),
                            'Explique o vínculo com a região.')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('character_story', args=[self.person.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('character_stories_inbox')), self.person.nome)

    def test_owner_http_draft_submit_csrf_and_legacy_info_endpoint(self):
        self.client.force_login(self.owner)
        url = reverse('character_story', args=[self.person.pk])
        response = self.client.get(url)
        self.assertContains(response, 'class="character-story-page"')
        token = response.context['form'].initial['ticket']
        self.assertEqual(self.client.post(url, {'ticket': token, 'text': 'Meu texto', 'action': 'submit'}).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, {'ticket': token, 'text': 'Texto', 'action': 'submit'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('personagem_info_salvar', args=[self.person.pk]),
            {'historia': 'Não pode sobrescrever', 'idade': '100'}).status_code, 409)
        self.person.refresh_from_db()
        self.assertEqual(self.person.historia, 'Meu texto')
        self.assertNotEqual(self.person.idade, '100')

    def test_sheet_feedback_is_not_exposed_to_an_unrelated_sheet_reader(self):
        item = self.submit()
        self.decide(item)
        self.person.refresh_from_db()
        html = render_to_string('home/partials/character_story_status.html', {
            'p': self.person, 'story_review': story_context(self.person),
            'can_read_story_feedback': False})
        self.assertNotIn('Falta explicar a origem da família.', html)
        self.assertIn('Ajustes solicitados', html)
