from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.deploy_sync import MEMORY_MODELS
from home.models import TbCronica, TbCronicaComentario, TbCronicaDenuncia


class CronicaCommentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.autor = user.objects.create_user('autor-comentario', password='senha')
        cls.leitor = user.objects.create_user('leitor-comentario', password='senha')
        cls.outro = user.objects.create_user('outro-comentario', password='senha')
        cls.staff = user.objects.create_user('staff-comentario', password='senha', is_staff=True)
        cls.staff.user_permissions.add(Permission.objects.get(
            codename='change_tbcronicadenuncia', content_type__app_label='home',
        ))
        cls.staff_sem_moderacao = user.objects.create_user(
            'staff-sem-moderacao', password='senha', is_staff=True,
        )
        cls.story = TbCronica.objects.create(
            titulo='Relato da Lua Velada', slug='cronica-com-comentarios',
            conteudo_markdown='Texto público', autor=cls.autor, status='aprovada',
        )
        cls.pending = TbCronica.objects.create(
            titulo='Rascunho', slug='cronica-em-revisao',
            conteudo_markdown='Segredo', autor=cls.autor, status='pendente',
        )

    def comment(self, text='Comentário seguro', story=None, **extra):
        return self.client.post(reverse('cronica_comentar', args=[(story or self.story).pk]), {
            'texto': text, 'chave_operacao': str(extra.pop('chave_operacao', uuid4())), **extra,
        })

    def report(self, reason='Conteúdo inadequado', **extra):
        return self.client.post(reverse('cronica_denunciar', args=[self.story.pk]), {
            'motivo': reason, **extra,
        })

    def test_create_reply_and_only_public_story(self):
        self.client.force_login(self.leitor)
        self.assertEqual(self.comment(story=self.pending).status_code, 404)
        self.assertEqual(self.comment().status_code, 302)
        parent = TbCronicaComentario.objects.get()
        self.assertEqual(self.comment('Resposta', resposta_a=parent.pk).status_code, 302)
        self.assertEqual(self.comment('Terceiro nível', resposta_a=TbCronicaComentario.objects.latest('pk').pk).status_code, 404)
        page = self.client.get(reverse('cronica_detail', args=[self.story.slug]))
        self.assertContains(page, 'Comentário seguro')
        self.assertContains(page, 'Resposta')
        self.assertNotContains(page, 'Terceiro nível')

    def test_duplicate_operation_is_replayed_without_duplicate_comment(self):
        self.client.force_login(self.leitor)
        key = uuid4()
        self.assertEqual(self.comment(chave_operacao=key).status_code, 302)
        self.assertEqual(self.comment(chave_operacao=key).status_code, 302)
        self.assertEqual(TbCronicaComentario.objects.count(), 1)
        self.client.force_login(self.outro)
        self.assertEqual(self.comment(chave_operacao=key).status_code, 409)

    def test_comment_edit_preserves_history_and_rejects_stale_revision(self):
        self.client.force_login(self.leitor)
        self.comment()
        comment = TbCronicaComentario.objects.get()
        url = reverse('cronica_editar_comentario', args=[comment.pk])
        self.client.force_login(self.outro)
        self.assertEqual(self.client.post(url, {'texto': 'Ataque', 'revisao': 1}).status_code, 404)
        self.client.force_login(self.leitor)
        self.assertEqual(self.client.post(url, {'texto': 'Texto editado', 'revisao': 1}).status_code, 302)
        self.assertEqual(self.client.post(url, {'texto': 'Texto antigo', 'revisao': 1}).status_code, 409)
        comment.refresh_from_db()
        self.assertEqual(comment.revisao, 2)
        self.assertEqual(comment.historico_edicoes[0]['texto'], 'Comentário seguro')
        self.assertEqual(comment.texto, 'Texto editado')

    def test_report_hides_comment_without_erasing_it_or_its_replies(self):
        self.client.force_login(self.leitor)
        self.comment('Texto denunciado')
        parent = TbCronicaComentario.objects.get()
        self.client.force_login(self.autor)
        self.comment('Resposta ainda pública', resposta_a=parent.pk)
        self.client.force_login(self.outro)
        self.assertEqual(self.report(comentario_id=parent.pk).status_code, 302)
        self.assertEqual(self.report(comentario_id=parent.pk).status_code, 302)
        self.assertEqual(TbCronicaDenuncia.objects.count(), 1)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('cronica_denuncias')), 'Texto denunciado')
        report = TbCronicaDenuncia.objects.get()
        self.assertEqual(report.alvo_snapshot, 'Texto denunciado')
        self.assertEqual(report.revisao_alvo, 1)
        url = reverse('cronica_moderar_denuncia', args=[report.pk])
        self.assertEqual(self.client.post(url, {'action': 'ocultar'}).status_code, 302)
        self.assertEqual(self.client.post(url, {'action': 'ocultar'}).status_code, 409)
        parent.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(parent.estado, 'oculto')
        self.assertEqual(parent.texto, 'Texto denunciado')
        self.assertEqual(report.estado, 'ocultada')
        self.assertEqual(report.decidido_por, self.staff)
        self.assertEqual([event['acao'] for event in report.historico_decisoes], ['ocultar'])
        self.client.logout()
        page = self.client.get(reverse('cronica_detail', args=[self.story.slug]))
        self.assertNotContains(page, 'Texto denunciado')
        self.assertContains(page, 'Comentário ocultado')
        self.assertContains(page, 'Resposta ainda pública')
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(url, {'action': 'restaurar'}).status_code, 302)
        parent.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(parent.estado, 'publico')
        self.assertEqual([event['acao'] for event in report.historico_decisoes], ['ocultar', 'restaurar'])

    def test_staff_can_dismiss_report_without_hiding_comment(self):
        self.client.force_login(self.leitor)
        self.comment()
        comment = TbCronicaComentario.objects.get()
        self.client.force_login(self.outro)
        self.report(comentario_id=comment.pk)
        report = TbCronicaDenuncia.objects.get()
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]), {
            'action': 'descartar',
        }).status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.estado, 'pendente')
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]), {
            'action': 'descartar',
        }).status_code, 302)
        comment.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(comment.estado, 'publico')
        self.assertEqual(report.estado, 'descartada')

    def test_staff_without_moderation_permission_cannot_review_or_decide(self):
        self.client.force_login(self.leitor)
        self.assertEqual(self.report().status_code, 302)
        report = TbCronicaDenuncia.objects.get()
        self.client.force_login(self.staff_sem_moderacao)
        self.assertEqual(self.client.get(reverse('cronica_denuncias')).status_code, 403)
        self.assertEqual(self.client.post(
            reverse('cronica_moderar_denuncia', args=[report.pk]),
            {'action': 'ocultar'},
        ).status_code, 403)
        report.refresh_from_db()
        self.story.refresh_from_db()
        self.assertEqual(report.estado, 'pendente')
        self.assertEqual(self.story.status, 'aprovada')

    def test_admin_navigation_opens_moderation_queue(self):
        superuser = get_user_model().objects.create_superuser(
            'super-moderacao', 'moderacao@example.invalid', 'senha',
        )
        self.client.force_login(self.leitor)
        self.assertEqual(self.report().status_code, 302)
        self.client.force_login(superuser)
        dashboard = self.client.get(reverse('admin:index'))
        self.assertContains(dashboard, 'Moderação de crônicas')
        self.assertContains(dashboard, reverse('cronica_denuncias'))
        queue = self.client.get(reverse('cronica_denuncias'))
        self.assertContains(queue, 'Relato da Lua Velada')

    def test_multiple_hides_restore_only_after_last_decision_is_reverted(self):
        self.client.force_login(self.leitor)
        self.comment('Texto comum')
        comment = TbCronicaComentario.objects.get()
        self.client.force_login(self.autor)
        self.report(comentario_id=comment.pk)
        self.client.force_login(self.outro)
        self.report(comentario_id=comment.pk)
        reports = list(TbCronicaDenuncia.objects.order_by('pk'))
        self.client.force_login(self.staff)
        for report in reports:
            self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]), {
                'action': 'ocultar',
            }).status_code, 302)
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[reports[0].pk]), {
            'action': 'restaurar',
        }).status_code, 302)
        comment.refresh_from_db()
        self.assertEqual(comment.estado, 'oculto')
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[reports[1].pk]), {
            'action': 'restaurar',
        }).status_code, 302)
        comment.refresh_from_db()
        self.assertEqual(comment.estado, 'publico')

    def test_story_report_hides_story_but_preserves_records(self):
        self.client.force_login(self.leitor)
        self.assertEqual(self.report().status_code, 302)
        report = TbCronicaDenuncia.objects.get()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]), {
            'action': 'ocultar',
        }).status_code, 302)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'oculta')
        self.assertEqual(self.story.conteudo_markdown, 'Texto público')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('cronica_detail', args=[self.story.slug])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('busca') + '?q=Lua%20Velada'), self.story.titulo)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('cronica_moderar_denuncia', args=[report.pk]), {
            'action': 'restaurar',
        }).status_code, 302)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'aprovada')
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])), 'Texto público')

    def test_limits_permissions_and_escaping(self):
        self.assertEqual(self.comment().status_code, 302)
        self.client.force_login(self.leitor)
        self.assertEqual(self.comment('').status_code, 400)
        self.assertEqual(self.comment('x' * 2001).status_code, 400)
        self.assertEqual(self.comment('<script>alert(1)</script>').status_code, 302)
        page = self.client.get(reverse('cronica_detail', args=[self.story.slug]))
        self.assertContains(page, '&lt;script&gt;')
        self.assertNotContains(page, '<script>alert(1)</script>')
        self.assertEqual(self.report('x').status_code, 400)
        self.assertEqual(self.report('x' * 501).status_code, 400)
        self.client.force_login(self.autor)
        self.assertEqual(self.report().status_code, 400)
        self.client.force_login(self.leitor)
        for index in range(4):
            self.assertEqual(self.comment(f'Mensagem {index}').status_code, 302)
        self.assertEqual(self.comment('Mensagem extra').status_code, 429)
        self.assertEqual(TbCronicaComentario.objects.count(), 5)
        self.assertIn('TbCronicaComentario', MEMORY_MODELS)
        self.assertIn('TbCronicaDenuncia', MEMORY_MODELS)
