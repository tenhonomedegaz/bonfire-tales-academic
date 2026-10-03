import json
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from home.deploy_sync import MEMORY_MODELS
from home.models import TbCronica, TbCronicaComentario, TbCronicaNotificacao, TbPerfilSeguidor


class CronicaDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.author = user.objects.create_user('author-discovery', password='test')
        cls.reader = user.objects.create_user('reader-discovery', password='test')
        cls.other = user.objects.create_user('other-discovery', password='test')
        cls.staff = user.objects.create_user('staff-discovery', password='test', is_staff=True)
        cls.staff.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home',
        ))
        cls.staff_sem_publicacao = user.objects.create_user(
            'staff-discovery-unprivileged', password='test', is_staff=True,
        )
        now = timezone.now()
        cls.older = TbCronica.objects.create(titulo='História antiga', slug='historia-antiga',
            conteudo_markdown='Texto antigo', autor=cls.author, status='aprovada',
            data_publicacao=now - timedelta(days=2))
        cls.newer = TbCronica.objects.create(titulo='História nova', slug='historia-nova',
            conteudo_markdown='Texto novo', autor=cls.other, status='aprovada',
            data_publicacao=now)
        cls.pending = TbCronica.objects.create(titulo='História privada', slug='historia-privada',
            conteudo_markdown='Segredo', autor=cls.author, status='pendente')

    def test_recent_followed_and_private_exclusion(self):
        TbPerfilSeguidor.objects.create(seguidor=self.reader, alvo=self.author)
        response = self.client.get(reverse('mundo_cronicas'))
        stories = list(response.context['cronicas'])
        self.assertEqual([s.pk for s in stories], [self.newer.pk, self.older.pk])
        self.assertNotContains(response, 'História privada')
        self.client.force_login(self.reader)
        response = self.client.get(reverse('mundo_cronicas'), {'feed': 'seguindo'})
        self.assertEqual([s.pk for s in response.context['cronicas']], [self.older.pk])
        self.client.logout()
        self.assertEqual(list(self.client.get(reverse('mundo_cronicas'), {'feed': 'seguindo'}).context['cronicas']), [])

    def test_editorial_highlight_requires_staff_and_publication(self):
        url = reverse('cronica_destaque', args=[self.older.pk])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(url, {'destaque': 'true'}).status_code, 302)
        self.older.refresh_from_db()
        self.assertFalse(self.older.destaque_editorial)
        self.client.force_login(self.staff_sem_publicacao)
        self.assertEqual(self.client.post(url, {'destaque': 'true'}).status_code, 403)
        self.assertNotContains(self.client.get(reverse('cronica_detail', args=[self.older.slug])),
                               'Destacar editorialmente')
        self.older.refresh_from_db()
        self.assertFalse(self.older.destaque_editorial)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.older.slug])),
                            'Destacar editorialmente')
        self.assertEqual(self.client.post(url, {'destaque': 'true'}).status_code, 302)
        self.assertContains(self.client.get(reverse('mundo_cronicas')), 'Destaques editoriais')
        self.assertEqual(self.client.post(reverse('cronica_destaque', args=[self.pending.pk]), {'destaque': 'true'}).status_code, 404)
        self.assertEqual(self.client.post(url, {'destaque': 'false'}).status_code, 302)
        self.older.refresh_from_db()
        self.assertFalse(self.older.destaque_editorial)

    def test_approval_sets_publication_date_and_notifies_once(self):
        self.client.force_login(self.staff)
        url = reverse('cronica_review_action', args=[self.pending.pk])
        payload = json.dumps({'action': 'aprovar'})
        self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 409)
        self.pending.refresh_from_db()
        self.assertIsNotNone(self.pending.data_publicacao)
        self.assertEqual(TbCronicaNotificacao.objects.filter(destinatario=self.author, cronica=self.pending).count(), 1)
        original_date = self.pending.data_publicacao
        self.pending.revisao_edicao = {'estado': 'pendente', 'submetida_em': '2026-09-28T00:00:00+00:00',
            'titulo': 'Título alterado', 'conteudo_markdown': 'Novo texto', 'resumo': '', 'imagem_url': '',
            'personagem_nome': '', 'territorio': '', 'regiao': ''}
        self.pending.save(update_fields=['revisao_edicao'])
        payload = json.dumps({'action': 'aprovar', 'expected_revision': '2026-09-28T00:00:00+00:00'})
        self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.data_publicacao, original_date)

    def test_comment_reply_dedup_and_private_inbox(self):
        self.client.force_login(self.reader)
        key = str(uuid4())
        url = reverse('cronica_comentar', args=[self.older.pk])
        payload = {'texto': 'Comentário', 'chave_operacao': key}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        parent = TbCronicaComentario.objects.get(chave_operacao=key)
        self.assertEqual(TbCronicaNotificacao.objects.filter(destinatario=self.author, comentario=parent).count(), 1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {'texto': 'Resposta', 'chave_operacao': str(uuid4()), 'resposta_a': parent.pk}).status_code, 302)
        reply = TbCronicaComentario.objects.exclude(pk=parent.pk).get()
        self.assertEqual(set(TbCronicaNotificacao.objects.filter(comentario=reply).values_list('destinatario_id', flat=True)),
                         {self.reader.pk, self.author.pk})
        inbox = reverse('cronica_notificacoes')
        self.assertEqual(self.client.get(inbox).status_code, 200)
        self.assertNotContains(self.client.get(inbox), f'#comentario-{parent.pk}')
        self.client.force_login(self.reader)
        self.assertContains(self.client.get(inbox), f'#comentario-{reply.pk}')
        notification = TbCronicaNotificacao.objects.get(destinatario=self.reader)
        reply.estado = 'oculto'
        reply.save(update_fields=['estado'])
        self.assertNotContains(self.client.get(inbox), f'#comentario-{reply.pk}')
        reply.estado = 'publico'
        reply.save(update_fields=['estado'])
        mark_url = reverse('cronica_notificacao_ler', args=[notification.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(mark_url).status_code, 302)
        notification.refresh_from_db()
        self.assertIsNone(notification.lida_em)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(mark_url).status_code, 302)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.lida_em)

    def test_notification_table_is_protected_from_catalog_sync(self):
        self.assertIn('TbCronicaNotificacao', MEMORY_MODELS)


class CronicaPublicationMigrationTests(TransactionTestCase):
    def test_backfill_uses_original_submission_not_later_review(self):
        executor = MigrationExecutor(connection)
        before = [('home', '0116_cronica_comentarios_denuncias')]
        after = [('home', '0117_cronica_descoberta_notificacoes')]
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        author = old_apps.get_model('auth', 'User').objects.create(username='author-old-publication')
        story = old_apps.get_model('home', 'TbCronica').objects.create(
            titulo='Publicada antes', slug='publicada-antes', conteudo_markdown='Texto',
            autor_id=author.pk, status='aprovada', data_revisao=timezone.now() + timedelta(days=1),
        )
        submission = story.data_submissao
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        migrated = executor.loader.project_state(after).apps.get_model('home', 'TbCronica').objects.get(pk=story.pk)
        self.assertEqual(migrated.data_publicacao, submission)
        self.assertFalse(migrated.destaque_editorial)
