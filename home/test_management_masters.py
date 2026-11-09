from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from home.gestao.role_policy import editable_permissions
from home.models import TbMesaAnuncio, TbPerfilMestre, TbImportacaoMestre, TbMestreLegado
from home.portal_models import PortalRequest


@override_settings(MASTER_APPLICATIONS_OPEN=False)
class ManagementMastersTests(TestCase):
    def setUp(self):
        self.master = get_user_model().objects.create_user('master-panel-owner')
        self.operator = get_user_model().objects.create_user('master-panel-reviewer', is_staff=False)
        self.profile = TbPerfilMestre.objects.create(user=self.master, status_mestre='pendente',
            apresentacao='Narrativa <script>nao executar</script>', estilo='Investigação',
            experiencia='Campanhas antigas', combinados='Conversa na sessão zero', versao=3)
        self.table = TbMesaAnuncio.objects.create(mestre=self.master, titulo='Rastro de cinzas',
            descricao='Um anúncio de teste', rank='Obsidiana', agenda_combinar=True,
            estado='pendente', revisao=1)
        self.client.force_login(self.operator)
        self.dashboard = reverse('master_dashboard')

    def allow(self, *codes):
        self.operator.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home', codename__in=codes))

    def test_announcements_only_does_not_expose_applications_or_authorize_masters(self):
        self.assertEqual(self.client.get(self.dashboard).status_code, 403)
        self.allow('revisar_mesa_anuncio')
        response = self.client.get(self.dashboard)
        self.assertContains(response, 'Central de gestão')
        self.assertContains(response, self.table.titulo)
        self.assertNotContains(response, self.profile.estilo)
        self.assertNotContains(response, 'master-note-')
        self.assertNotContains(response, 'commercial-note-')
        self.assertTrue(response.context['management_access'])
        self.assertEqual(self.client.post(reverse('master_authorize', args=[self.master.pk]),
            {'acao': 'autorizar', 'confirmar': 'sim', 'versao': 3}).status_code, 403)
        result = self.client.get(reverse('gestao:editorial'))
        self.assertContains(result, '?anuncio=' + str(self.table.pk))
        self.assertEqual(result.context['entries'].paginator.count, 1)
        self.assertEqual(PortalRequest.objects.count(), 0)

    def test_authorizer_can_read_saved_presentation_without_an_editorial_permission(self):
        self.allow('autorizar_mestres')
        response = self.client.get(self.dashboard)
        self.assertContains(response, 'Apresentação de mestre')
        self.assertContains(response, '&lt;script&gt;nao executar&lt;/script&gt;')
        self.assertContains(response, self.profile.experiencia)
        self.assertNotContains(response, self.table.titulo)
        self.assertContains(response, 'temporariamente encerradas')
        self.assertEqual(self.client.get(reverse('gestao:editorial')).status_code, 403)
        self.assertEqual(self.client.post(reverse('master_request'), {}).status_code, 403)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.versao, 3)
        self.assertEqual(self.profile.status_mestre, 'pendente')

    def test_native_authorization_requires_existing_fogueira_and_preserves_texts(self):
        self.allow('autorizar_mestres')
        url = reverse('master_authorize', args=[self.master.pk])
        data = {'acao': 'autorizar', 'confirmar': 'sim', 'versao': 3, 'nota': 'Conferido'}
        self.assertEqual(self.client.post(url, data).status_code, 409)
        archive = TbImportacaoMestre.objects.create(fonte='masters-panel-tests', checksum='c' * 64, dados={})
        TbMestreLegado.objects.create(importacao=archive, numero=12, nome='Mestre de teste',
            rotulo_original='F12', user=self.master)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.status_mestre, self.profile.avaliador_id), ('aprovado', self.operator.pk))
        self.assertEqual(self.profile.apresentacao, 'Narrativa <script>nao executar</script>')
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.is_staff)
        self.assertFalse(self.operator.is_superuser)

    def test_announcement_decision_uses_native_state_version_and_reviewer(self):
        self.allow('revisar_mesa_anuncio')
        self.profile.status_mestre = 'aprovado'
        self.profile.save()
        url = reverse('master_table_action', args=[self.table.pk])
        data = {'acao': 'aprovar', 'revisao': 1, 'nota': 'Divulgação conferida'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.table.refresh_from_db()
        self.assertEqual((self.table.estado, self.table.revisao, self.table.revisor_id),
                         ('publicado', 2, self.operator.pk))
        self.assertEqual(self.client.get(reverse('gestao:editorial')).context['entries'].paginator.count, 0)

    def test_announcements_pagination_and_direct_link(self):
        self.allow('revisar_mesa_anuncio')
        for index in range(27):
            TbMesaAnuncio.objects.create(mestre=self.master, titulo=f'Mesa {index}',
                descricao='Texto', estado='pendente', rank='Obsidiana', agenda_combinar=True)
        self.assertEqual(len(self.client.get(self.dashboard).context['review_queue']), 25)
        self.assertEqual(len(self.client.get(self.dashboard, {'anuncios_pagina': 2}).context['review_queue']), 3)
        isolated = self.client.get(self.dashboard, {'anuncio': self.table.pk})
        self.assertEqual(len(isolated.context['review_queue']), 1)
        self.assertContains(isolated, 'table-' + str(self.table.pk))

    def test_no_implicit_staff_access_csrf_and_matrix(self):
        self.operator.is_staff = True
        self.operator.save()
        self.assertEqual(self.client.get(self.dashboard).status_code, 403)
        self.allow('autorizar_mestres')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.operator)
        self.assertEqual(client.post(reverse('master_authorize', args=[self.master.pk]),
            {'acao': 'autorizar', 'confirmar': 'sim', 'versao': 3}).status_code, 403)
        self.assertTrue({'autorizar_mestres', 'revisar_mesa_anuncio'} <=
                        {permission.codename for permission in editable_permissions()})
