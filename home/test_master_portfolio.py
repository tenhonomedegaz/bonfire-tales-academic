"""Owner, reviewer and visitor boundaries for the approved master portfolio."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from .models import TbPerfilMestre, TbTrabalhoMestre


class MasterPortfolioFlowTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.master = users.objects.create_user('portfolio_master', password='test-pass')
        self.visitor = users.objects.create_user('portfolio_visitor', password='test-pass')
        self.staff = users.objects.create_superuser('portfolio_staff', 'staff@example.test', 'test-pass')
        TbPerfilMestre.objects.create(user=self.master, status_mestre='aprovado',
                                      modo='mestre', listado=True)

    def payload(self, **changes):
        data = {'titulo': 'O vale oculto', 'categoria': 'relato',
                'descricao': 'Uma história de Cinéria', 'texto': 'A chama guiou o grupo.',
                'video_url': '', 'revisao': '0', 'acao': 'enviar'}
        data.update(changes)
        return data

    def test_work_requires_review_and_authorized_public_profile(self):
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.post(reverse('master_work_create'), self.payload()).status_code, 403)
        self.client.force_login(self.master)
        self.assertEqual(self.client.post(reverse('master_work_create'), self.payload()).status_code, 302)
        work = TbTrabalhoMestre.objects.get(mestre=self.master)
        self.assertEqual((work.estado, work.revisao), ('pendente', 1))
        self.assertContains(self.client.get(reverse('master_gallery')), work.titulo)
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(reverse('master_work_detail', args=[work.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('public_profile', args=[self.master.username]) + '?aba=mestre'), work.titulo)
        self.assertEqual(self.client.post(reverse('master_work_review', args=[work.pk]),
                                          {'acao': 'aprovar', 'revisao': 1}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('master_gallery_review')), work.titulo)
        self.assertEqual(self.client.post(reverse('master_work_review', args=[work.pk]),
                                          {'acao': 'aprovar', 'revisao': 0}).status_code, 409)
        self.assertEqual(self.client.post(reverse('master_work_review', args=[work.pk]),
                                          {'acao': 'aprovar', 'revisao': 1}).status_code, 302)
        work.refresh_from_db()
        self.assertEqual(work.estado, 'publicado')
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(reverse('master_work_detail', args=[work.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse('public_profile', args=[self.master.username]) + '?aba=mestre'), work.titulo)
        TbPerfilMestre.objects.filter(user=self.master).update(status_mestre='suspenso')
        self.assertEqual(self.client.get(reverse('master_work_detail', args=[work.pk])).status_code, 404)
        self.client.force_login(self.master)
        self.assertContains(self.client.get(reverse('master_gallery')), work.titulo)
        self.assertEqual(self.client.post(reverse('master_work_edit', args=[work.pk]),
                                          self.payload(revisao='2')).status_code, 403)

    def test_edit_unpublishes_and_blocks_stale_version(self):
        work = TbTrabalhoMestre.objects.create(mestre=self.master, titulo='Anterior',
                                               categoria='relato', texto='Antigo',
                                               estado='publicado', revisao=3)
        self.client.force_login(self.master)
        endpoint = reverse('master_work_edit', args=[work.pk])
        self.assertEqual(self.client.post(endpoint, self.payload(revisao='2')).status_code, 200)
        work.refresh_from_db()
        self.assertEqual((work.titulo, work.estado, work.revisao), ('Anterior', 'publicado', 3))
        self.assertEqual(self.client.post(endpoint, self.payload(revisao='3', acao='rascunho')).status_code, 302)
        work.refresh_from_db()
        self.assertEqual((work.estado, work.revisao), ('rascunho', 4))
        self.assertEqual(self.client.get(reverse('master_work_detail', args=[work.pk])).status_code, 200)
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(reverse('master_work_detail', args=[work.pk])).status_code, 404)

    def test_csrf_and_invalid_url_do_not_create_work(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.master)
        self.assertEqual(client.post(reverse('master_work_create'), self.payload()).status_code, 403)
        self.client.force_login(self.master)
        self.assertEqual(self.client.post(reverse('master_work_create'),
                                          self.payload(video_url='http://example.com/')).status_code, 200)
        self.assertFalse(TbTrabalhoMestre.objects.exists())

    def test_gallery_reviewer_permission_does_not_grant_master_authorization(self):
        reviewer = get_user_model().objects.create_user('portfolio_reviewer', password='test-pass',
                                                        is_staff=True)
        reviewer.user_permissions.add(Permission.objects.get(
            codename='revisar_trabalho_mestre'))
        work = TbTrabalhoMestre.objects.create(mestre=self.master, titulo='Mapa do vale',
                                               categoria='mapa', texto='Rotas seguras',
                                               estado='pendente', revisao=1)
        self.client.force_login(reviewer)
        self.assertEqual(self.client.get(reverse('master_dashboard')).status_code, 200)
        self.assertContains(self.client.get(reverse('master_gallery_review')), work.titulo)
        self.assertEqual(self.client.post(reverse('master_work_review', args=[work.pk]),
                                          {'acao': 'aprovar', 'revisao': 1}).status_code, 302)
        self.assertEqual(self.client.post(reverse('master_authorize', args=[self.master.pk]),
                                          {'acao': 'suspender', 'confirmar': 'sim', 'versao': 0}).status_code, 403)
        work.refresh_from_db()
        self.assertEqual(work.estado, 'publicado')
