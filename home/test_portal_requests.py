from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from home.gestao.requests import act_on_request, create_request, visible_requests
from home.gestao.request_views import portal_context
from home.models import TbPersonagem
from home.portal_models import PortalActivity, PortalRequest


class PortalRequestTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('portal-owner')
        self.stranger = users.objects.create_user('portal-stranger')
        self.reviewer = users.objects.create_user('portal-reviewer', is_staff=False)
        self.admin = users.objects.create_user('portal-admin', is_superuser=True, is_staff=False)
        self.reviewer.user_permissions.add(Permission.objects.get(codename='review_portal_ticket'))
        self.character = TbPersonagem.objects.create(nome='Personagem do portal', dono=self.owner)

    def create(self, **changes):
        data = dict(actor=self.owner, request_id=uuid4(), queue='ticket', title='Ajuda de teste',
                    description='Descricao da solicitacao de teste.')
        data.update(changes)
        return create_request(**data)

    def act(self, task, action, actor=None, **changes):
        data = dict(actor=actor or self.reviewer, task_id=task.pk, request_id=uuid4(),
                    version=task.version, action=action, note='Parecer de teste completo.')
        data.update(changes)
        return act_on_request(**data)

    def test_creation_replay_and_character_access(self):
        operation = uuid4()
        task = self.create(request_id=operation)
        self.assertEqual(self.create(request_id=operation).pk, task.pk)
        self.assertEqual(PortalRequest.objects.count(), 1)
        self.assertEqual(PortalActivity.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.create(request_id=operation, title='Dados divergentes')
        with self.assertRaises(ValidationError):
            self.create(queue='ficha')
        with self.assertRaises(PermissionDenied):
            self.create(actor=self.stranger, queue='ficha', character_id=self.character.pk)
        valid = self.create(queue='ficha', character_id=self.character.pk)
        self.assertEqual(valid.character_id, self.character.pk)

    def test_return_resubmit_and_finish_preserve_versions_and_character(self):
        task = self.create()
        task = self.act(task, 'start')
        self.assertEqual(task.assignee_id, self.reviewer.pk)
        task = self.act(task, 'return')
        old_description = task.description
        task = self.act(task, 'resubmit', self.owner, description='Descricao revisada pelo solicitante.')
        task = self.act(task, 'finish')
        self.assertEqual(task.status, 'done')
        event = task.activities.get(action='resubmit')
        self.assertEqual(event.before['description'], old_description)
        self.assertEqual(task.version, 5)
        self.character.refresh_from_db()
        self.assertEqual(self.character.nivel, 1)

    def test_stale_version_replay_and_scope(self):
        task = self.create()
        operation = uuid4()
        self.act(task, 'start', request_id=operation)
        replay = self.act(task, 'start', request_id=operation)
        self.assertEqual(replay.version, 2)
        self.assertEqual(task.activities.filter(action='start').count(), 1)
        with self.assertRaises(ValidationError):
            self.act(task, 'comment')
        with self.assertRaises(PermissionDenied):
            self.act(replay, 'finish', self.stranger)
        another_queue = self.create(queue='regras')
        with self.assertRaises(PermissionDenied):
            self.act(another_queue, 'start')
        self.assertFalse(visible_requests(self.stranger).exists())
        self.assertEqual(list(visible_requests(self.reviewer)), [replay])
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):
            self.act(replay, 'finish')

    def test_http_owner_isolation_csrf_and_escaped_comments(self):
        task = self.create(description='<script>alert(1)</script> descricao segura')
        route = reverse('gestao:request_detail', args=[task.pk])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(route).status_code, 404)
        self.assertNotContains(self.client.get(reverse('gestao:requests')), task.title)
        self.client.force_login(self.owner)
        response = self.client.get(route)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        token = uuid4()
        response = self.client.post(route, {'request_id': token, 'version': 1,
            'action': 'comment', 'note': 'Meu comentario de teste.'})
        self.assertRedirects(response, route, fetch_redirect_response=False)
        self.assertContains(self.client.get(route), 'Meu comentario de teste.')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(route, {'action': 'comment'}).status_code, 403)

    def test_dashboard_counts_do_not_leak_other_queues(self):
        task = self.create()
        self.create(queue='regras')
        context = portal_context(self.reviewer)
        self.assertEqual(context['portal_total_pending'], 1)
        self.assertEqual([row['key'] for row in context['portal_queues']], ['ticket'])
        self.assertEqual([event.task_id for event in context['portal_recent_activity']], [task.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('gestao:people')).status_code, 403)

    def test_full_http_creation_and_no_auto_role_assignment(self):
        self.client.force_login(self.owner)
        route = reverse('gestao:request_create')
        response = self.client.get(route)
        operation = response.context['form'].initial['request_id']
        data = {'request_id': operation, 'queue': 'ticket', 'title': 'Pedido via interface',
                'description': 'Descricao completa enviada pela interface.'}
        self.assertEqual(self.client.post(route, data).status_code, 302)
        self.assertEqual(self.client.post(route, data).status_code, 302)
        self.assertEqual(PortalRequest.objects.count(), 1)
        self.assertFalse(self.owner.groups.exists())
        self.assertFalse(self.owner.is_superuser)
        self.assertFalse(self.owner.is_staff)
