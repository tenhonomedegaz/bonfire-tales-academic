"""Focused regressions for navigation, master request queue and admin searches."""
from datetime import timedelta
import json
from pathlib import Path

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .master_participation import participation
from .context_processors import master_review
from .models import TbItemMundano, TbPerfilMestre
from .master_application_testdata import application_data


@override_settings(TEMPLATES=[{
    'BACKEND':'django.template.backends.django.DjangoTemplates', 'APP_DIRS':True,
    'DIRS':[str(Path(__file__).resolve().parent / 'templates')],
    'OPTIONS':{'libraries':{'humanize':'django.contrib.humanize.templatetags.humanize'},
               'context_processors':['django.template.context_processors.request',
                                     'django.contrib.auth.context_processors.auth',
                                     'django.contrib.messages.context_processors.messages',
                                     'home.context_processors.master_review']},
}], MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware'])
class SchmidtMaintenanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_superuser('qa-review', password='local-test-only')
        self.player = User.objects.create_user('qa-applicant', password='local-test-only')

    def test_world_navigation_lists_each_destination_once(self):
        request = RequestFactory().get('/')
        request.user = self.player
        html = render_to_string('home/components/header.html', {'user':self.player}, request)
        menu = BeautifulSoup(html, 'html.parser').select_one('[data-world-menu]')
        self.assertIsNotNone(menu)
        links = [a['href'] for a in menu.select('li a')]
        self.assertEqual(len(links), len(set(links)))
        self.assertIn(reverse('mundo_organizacoes'), links)
        self.assertIn(reverse('mundo_cronicas'), links)

    @override_settings(MASTER_APPLICATIONS_OPEN=True)
    def test_request_appears_in_staff_queue_without_changing_permission(self):
        self.client.force_login(self.player)
        self.assertEqual(self.client.post(reverse('master_request'), application_data()).status_code, 302)
        profile = TbPerfilMestre.objects.get(user=self.player)
        self.assertEqual(profile.status_mestre, 'pendente')
        partial = render_to_string('home/partials/master_profile_editor.html', {
            'community': participation(profile), 'user':self.player})
        self.assertIn('fila de permissões de mestre', partial)
        self.assertNotIn('Avaliar solicitações de mestre', partial)
        self.assertEqual(self.client.get(reverse('master_dashboard')).status_code, 403)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('master_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.player.username)
        self.assertEqual(response.context['pending_master_count'], 1)
        profile.refresh_from_db()
        self.assertEqual(profile.status_mestre, 'pendente')

    def test_pending_requests_are_not_hidden_by_approved_profiles(self):
        User = get_user_model()
        approved_users = User.objects.bulk_create([User(username='approved-%03d'%i) for i in range(101)])
        TbPerfilMestre.objects.bulk_create([TbPerfilMestre(user=user, status_mestre='aprovado',
            solicitado_em=timezone.now()) for user in approved_users])
        requested = timezone.now() - timedelta(days=10)
        TbPerfilMestre.objects.create(user=self.player, status_mestre='pendente', solicitado_em=requested)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('master_dashboard'))
        self.assertEqual([row.user_id for row in response.context['master_requests']], [self.player.pk])
        self.assertEqual(response.context['request_status'], 'pendente')

    def test_queue_filters_and_paginates(self):
        User = get_user_model()
        users = User.objects.bulk_create([User(username='pending-%03d'%i) for i in range(27)])
        TbPerfilMestre.objects.bulk_create([TbPerfilMestre(user=user, status_mestre='pendente',
            solicitado_em=timezone.now()) for user in users])
        self.client.force_login(self.staff)
        url = reverse('master_dashboard')
        first = self.client.get(url)
        self.assertEqual(len(first.context['master_requests']), 25)
        second = self.client.get(url, {'solicitacoes_pagina':2})
        self.assertEqual(len(second.context['master_requests']), 2)
        self.assertTrue(set(row.pk for row in first.context['master_requests']).isdisjoint(
            row.pk for row in second.context['master_requests']))
        filtered = self.client.get(url, {'solicitante':'pending-026'})
        self.assertEqual(len(filtered.context['master_requests']), 1)
        approved = self.client.get(url, {'permissao':'aprovado'})
        self.assertFalse(approved.context['master_requests'])

    def test_admin_links_to_review_and_export(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, reverse('master_dashboard') + '#permissoes')
        self.assertContains(response, reverse('admin:catalog_export'))

    def test_review_context_does_not_query_queue_for_players_or_anonymous(self):
        request = RequestFactory().get('/')
        for user in (AnonymousUser(), self.player):
            request.user = user
            with self.assertNumQueries(0):
                self.assertEqual(master_review(request), {
                    'master_review_access':False, 'pending_master_requests_count':0})

    def test_directory_exposes_pending_notice_only_to_authorizers(self):
        TbPerfilMestre.objects.create(user=self.player, status_mestre='pendente')
        url = reverse('masters_directory')
        moderator = get_user_model().objects.create_user('qa-moderator', is_staff=True)
        for user in (None, self.player, moderator):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'bft-review-notice')
            self.assertNotContains(response, 'class="bft-master-review-link"')
        moderator.user_permissions.add(Permission.objects.get(codename='autorizar_mestres'))
        for user in (moderator, self.staff):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.context['pending_master_requests_count'], 1)
            html = BeautifulSoup(response.content, 'html.parser')
            self.assertIn('1 solicitação de mestre', html.select_one('.bft-review-notice').get_text())
            for selector in ('.mh-nav', '.site-mobile-menu-panel', 'nav'):
                self.assertIsNotNone(html.select_one(selector + ' .bft-master-review-link'))
            for link in html.select('.bft-master-review-link'):
                self.assertEqual(link['href'], reverse('master_dashboard') + '?permissao=pendente#permissoes')
                self.assertEqual(link.select_one('.bft-review-count').get_text(), '1')

    def test_pending_notice_clears_after_review_but_shortcut_remains(self):
        TbPerfilMestre.objects.create(user=self.player, status_mestre='pendente', versao=1)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('masters_directory')), 'bft-review-notice')
        response = self.client.post(reverse('master_authorize', args=[self.player.pk]), {
            'acao':'autorizar', 'versao':'1', 'confirmar':'sim'})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('masters_directory'))
        self.assertEqual(response.context['pending_master_requests_count'], 0)
        self.assertNotContains(response, 'bft-review-notice')
        self.assertContains(response, 'class="bft-master-review-link"')
        self.assertNotContains(response, 'class="bft-review-count"')

    def test_admin_item_search_accepts_numeric_and_text_queries(self):
        item = TbItemMundano.objects.create(nome='Espada 100', slug='qa-espada-100')
        self.client.force_login(self.staff)
        for query in ['100', 'Espada', '']:
            response = self.client.get(reverse('admin:home_tbitemmundano_changelist'), {'q':query})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, item.nome)

    def test_master_review_keeps_confirmation_and_version_guards(self):
        profile = TbPerfilMestre.objects.create(user=self.player, status_mestre='pendente', versao=1)
        self.client.force_login(self.staff)
        url = reverse('master_authorize', args=[self.player.pk])
        self.assertEqual(self.client.post(url, {'acao':'autorizar','versao':'1'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'acao':'autorizar','versao':'0','confirmar':'sim'}).status_code, 409)
        profile.refresh_from_db()
        self.assertEqual(profile.status_mestre, 'pendente')

    def test_master_request_keeps_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.player)
        self.assertEqual(client.post(reverse('master_request')).status_code, 403)
        self.assertFalse(TbPerfilMestre.objects.filter(user=self.player).exists())

    def test_content_sync_does_not_restore_shop_typo(self):
        fixture = json.loads((Path(__file__).resolve().parent / 'fixtures/conteudo.json').read_text(encoding='utf-8'))
        item = next(row for row in fixture if row['model'] == 'home.tbitemmagico'
                    and row['fields']['slug'] == 'anel-do-comando-elemental')
        self.assertEqual(item['pk'], 101)
        self.assertEqual(item['fields']['loja'], 'Joalheria')
