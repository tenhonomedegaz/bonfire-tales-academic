import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from home.gestao.role_policy import editable_permissions
from home.models import TbCronica, TbPerfilMestre, TbTrabalhoMestre
from home.portal_models import PortalRequest
from home.views import _cronica_pending_snapshot


class ManagementEditorialTests(TestCase):
    def setUp(self):
        self.author = get_user_model().objects.create_user('editorial-author')
        self.reviewer = get_user_model().objects.create_user('editorial-reviewer', is_staff=False)
        TbPerfilMestre.objects.create(user=self.author, status_mestre='aprovado')
        self.story = TbCronica.objects.create(titulo='Crônica pendente', slug='cronica-pendente',
            conteudo_markdown='Texto revisável', autor=self.author)
        self.work = TbTrabalhoMestre.objects.create(mestre=self.author, titulo='Mapa pendente',
            categoria='mapa', texto='Texto do mapa', estado='pendente', revisao=2)
        self.client.force_login(self.reviewer)
        self.url = reverse('gestao:editorial')

    def allow(self, *codes):
        self.reviewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home', codename__in=codes))

    def test_permission_scope_and_read_only_native_sources(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.allow('revisar_trabalho_mestre')
        response = self.client.get(self.url)
        self.assertContains(response, self.work.titulo)
        self.assertNotContains(response, self.story.titulo)
        self.assertTrue(response.context['management_access'])
        self.assertEqual(PortalRequest.objects.count(), 0)
        self.assertContains(self.client.get(reverse('master_gallery_review')), 'Central de gestão')
        self.assertEqual(self.client.get(reverse('cronicas_review')).status_code, 403)

    def test_union_filters_pagination_and_escaping(self):
        self.allow('revisar_trabalho_mestre', 'triage_tbcronica')
        self.work.titulo = '<script>alert(1)</script>'
        self.work.save()
        for number in range(27):
            TbTrabalhoMestre.objects.create(mestre=self.author, titulo=f'Mapa {number}',
                categoria='mapa', texto='Conteúdo', estado='pendente')
        response = self.client.get(self.url)
        self.assertEqual(response.context['entries'].paginator.count, 29)
        self.assertEqual(len(response.context['entries']), 25)
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertEqual(len(self.client.get(self.url, {'page': 2}).context['entries']), 4)
        result = self.client.get(self.url, {'q': 'Crônica', 'source': 'cronica'})
        self.assertEqual(result.context['entries'].paginator.count, 1)
        self.assertContains(result, '#review-' + str(self.story.pk))
        self.assertEqual(self.client.post(self.url).status_code, 405)
        isolated = self.client.get(reverse('master_gallery_review'), {'item': self.work.pk})
        self.assertEqual(len(isolated.context['works']), 1)
        self.assertEqual(self.client.get(reverse('master_gallery_review')).context['page_obj'].paginator.num_pages, 2)

    def test_published_edit_is_pending_without_duplicate_ticket(self):
        self.allow('change_tbcronica')
        self.story.status = 'aprovada'
        self.story.revisao_edicao = {'estado': 'pendente', 'titulo': 'Nova proposta'}
        self.story.save()
        self.assertEqual(self.client.get(self.url).context['entries'].paginator.count, 1)
        self.story.revisao_edicao = {}
        self.story.save()
        self.assertEqual(self.client.get(self.url).context['entries'].paginator.count, 0)
        self.assertEqual(PortalRequest.objects.count(), 0)

    def test_portfolio_native_decision_no_staff_no_duplicate_and_self_denial(self):
        self.allow('revisar_trabalho_mestre')
        url = reverse('master_work_review', args=[self.work.pk])
        data = {'acao': 'aprovar', 'revisao': 2, 'nota': 'Conferido'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.work.refresh_from_db()
        self.assertEqual((self.work.estado, self.work.revisor_id), ('publicado', self.reviewer.pk))
        self.assertEqual(self.client.get(self.url).context['entries'].paginator.count, 0)
        own = TbTrabalhoMestre.objects.create(mestre=self.reviewer, titulo='Próprio',
            categoria='arte', texto='Próprio', estado='pendente', revisao=2)
        self.assertEqual(self.client.post(reverse('master_work_review', args=[own.pk]), data).status_code, 409)

    def test_chronicle_native_audit_version_and_shell(self):
        self.allow('change_tbcronica')
        response = self.client.get(reverse('cronicas_review'))
        self.assertContains(response, 'Central de gestão')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'css/pages/gestao.css')
        data = {'action': 'aprovar', 'feedback': '',
                'expected_snapshot': _cronica_pending_snapshot(self.story)}
        url = reverse('cronica_review_action', args=[self.story.pk])
        self.assertEqual(self.client.post(url, json.dumps(data), content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, json.dumps(data), content_type='application/json').status_code, 409)
        self.story.refresh_from_db()
        self.assertEqual((self.story.status, self.story.revisado_por_id), ('aprovada', self.reviewer.pk))

    def test_csrf_and_permission_matrix(self):
        self.allow('revisar_trabalho_mestre')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reviewer)
        self.assertEqual(client.post(reverse('master_work_review', args=[self.work.pk]),
            {'acao': 'aprovar', 'revisao': 2}).status_code, 403)
        self.assertTrue({'revisar_trabalho_mestre', 'triage_tbcronica', 'change_tbcronica'} <=
                        {permission.codename for permission in editable_permissions()})
        self.reviewer.is_active = False
        self.reviewer.save()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_anonymous_review_uses_existing_login_route(self):
        self.client.logout()
        for route in ('cronicas_review', 'master_gallery_review', 'gestao:editorial'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/login/?next='), response.url)
