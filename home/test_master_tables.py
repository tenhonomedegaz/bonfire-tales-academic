"""Moderation and public visibility of site listings on an isolated database."""

from datetime import datetime, time, timedelta, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .master_commercial import commercial_eligibility
from .master_commercial_admin import CommercialAuthorizationForm
from .models import (TbAutorizacaoVitrine, TbAventuraMestre, TbMesaAnuncio,
                     TbPerfilMestre, TbTransacaoMestre, TbVerificacaoMesa)


class MasterTableFlowTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.master = users.objects.create_user('table_master', password='test-pass')
        self.other = users.objects.create_user('table_other', password='test-pass')
        self.staff = users.objects.create_superuser('table_staff', 'staff@example.test', 'test-pass')
        TbPerfilMestre.objects.create(user=self.master, status_mestre='aprovado', modo='mestre')

    def payload(self, **updates):
        day = timezone.localdate() + timedelta(days=10)
        data = {
            'titulo': 'A torre das cinzas', 'descricao': 'Uma aventura no vale.',
            'data_missao': day.isoformat(), 'hora_missao': '19:30',
            'duracao_minutos': '180', 'vagas': '5', 'ranks': ['Obsidiana'],
            'formato': 'oneshot', 'plataforma': 'Roll20', 'mesa_url': '',
            'discord_url': '', 'regras_url': '', 'tags': 'investigação',
            'modalidade': 'gratuita', 'cobranca': 'sessao', 'preco_unidade': 'pessoa',
            'sessoes': '1', 'cortesias': '0', 'revisao': '0', 'acao': 'enviar',
        }
        data.update(updates)
        return data

    def test_missions_navigation_clears_filters_and_opens_existing_master_flow(self):
        missions_url = reverse('sistemas_missoes')
        with patch('home.views.logger.exception'):
            response = self.client.get(missions_url, {'q': 'cinzas', 'status': 'finished'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{missions_url}"')
        self.assertContains(response, 'Limpar filtros')
        self.assertContains(response, 'href="#anuncios"')
        self.assertContains(response, f'href="{reverse("profile")}?aba=mestre"')
        with patch('home.views.logger.exception'):
            cleared = self.client.get(missions_url)
        self.assertEqual(cleared.status_code, 200)
        self.assertNotContains(cleared, 'Limpar filtros')
        self.assertEqual(cleared.context['search'], '')
        self.assertEqual(cleared.context['status'], '')

    def test_official_mission_uses_brasilia_schedule_and_collapsed_synopsis(self):
        quest = SimpleNamespace(
            id='qa-official-quest', name='Travessia das Brumas',
            description='Primeiro trecho.\nSegundo trecho.',
            questDate=datetime(2026, 11, 5, 1, 30, tzinfo=datetime_timezone.utc),
            playersAmount=4, questPlayers=[], participationRequests=[], subscribedPlayers=[],
            mandatoryPlayers=[], highPriorityPlayers=[], status='idle', type='Aventura',
            tags=[], questMaster='Mestre QA', tableUrl='', guildId='', channelId='',
        )
        queryset = MagicMock()
        queryset.exclude.return_value = queryset
        queryset.order_by.return_value.__getitem__.return_value = [quest]
        with patch('home.models.BotQuest.objects.filter', return_value=queryset):
            response = self.client.get(reverse('sistemas_missoes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Travessia das Brumas')
        self.assertContains(response, '04/11/2026 · 22:30 · Brasília')
        self.assertContains(response, 'datetime="2026-11-05T01:30:00+00:00"')
        self.assertContains(response, '<details class="mh-synopsis">', html=False)
        self.assertContains(response, 'Apresentação da missão')
        self.assertContains(response, 'Primeiro trecho.<br>Segundo trecho.')
        self.assertNotContains(response, '05/11/2026 · 01:30')

    def test_free_listing_requires_owner_staff_review_and_current_revision(self):
        discord_url = 'https://discord.com/channels/123/456'
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('master_table_create'), self.payload()).status_code, 403)

        self.client.force_login(self.master)
        result = self.client.post(reverse('master_table_create'), self.payload(discord_url=discord_url))
        self.assertEqual(result.status_code, 302, result.content[:500])
        table = TbMesaAnuncio.objects.get(mestre=self.master)
        self.assertEqual(table.estado, 'pendente')
        self.assertEqual(table.discord_url, discord_url)
        self.assertTrue(table.preco_demonstrativo)
        self.assertEqual(table.revisao, 1)
        self.assertContains(self.client.get(reverse('profile') + '?aba=mestre'), 'Preparar anúncio')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('sistemas_missoes')), discord_url)
        self.assertEqual(self.client.post(reverse('master_table_action', args=[table.pk]), {
            'acao': 'aprovar', 'revisao': '1',
        }).status_code, 403)

        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('master_dashboard')), table.titulo)
        self.assertEqual(self.client.post(reverse('master_table_action', args=[table.pk]), {
            'acao': 'aprovar', 'revisao': '0',
        }).status_code, 409)
        self.assertEqual(self.client.post(reverse('master_table_action', args=[table.pk]), {
            'acao': 'aprovar', 'revisao': '1',
        }).status_code, 302)
        table.refresh_from_db()
        self.assertEqual(table.estado, 'publicado')
        TbPerfilMestre.objects.filter(user=self.master).update(listado=True)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse('sistemas_missoes')), table.titulo)
        self.assertContains(self.client.get(reverse('sistemas_missoes')),
                            f'href="{discord_url}" target="_blank" rel="noopener noreferrer">Consultar inscrição no Discord')
        table.discord_url = ''
        table.save(update_fields=['discord_url'])
        no_channel = self.client.get(reverse('sistemas_missoes'))
        self.assertContains(no_channel, table.titulo)
        self.assertNotContains(no_channel, 'Consultar inscrição no Discord')
        # 01:30 UTC belongs to the previous calendar day in Brasilia.
        utc_day = timezone.now().date() + timedelta(days=10)
        table.data = datetime.combine(utc_day, time(1, 30), tzinfo=datetime_timezone.utc)
        table.save(update_fields=['data'])
        brasilia_time = table.data.astimezone(ZoneInfo('America/Sao_Paulo'))
        schedule = brasilia_time.strftime('%d/%m/%Y · %H:%M') + ' · Brasília'
        self.assertContains(self.client.get(reverse('sistemas_missoes')), schedule)
        self.assertContains(self.client.get(reverse('master_table_detail', args=[table.pk])), schedule)
        public_profile = self.client.get(reverse('public_profile', args=[self.master.username]))
        self.assertContains(public_profile, reverse('master_table_detail', args=[table.pk]), count=2)

        TbPerfilMestre.objects.filter(user=self.master).update(status_mestre='suspenso')
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('sistemas_missoes')), table.titulo)
        self.assertNotContains(self.client.get(reverse('public_profile', args=[self.master.username])),
                               reverse('master_table_detail', args=[table.pk]))
        self.client.force_login(self.master)
        profile_page = self.client.get(reverse('profile') + '?aba=mestre')
        self.assertContains(profile_page, table.titulo)
        self.assertNotContains(profile_page, 'Preparar anúncio')

    def test_paid_listing_stays_demonstrative_and_unpublished(self):
        self.client.force_login(self.master)
        paid = self.payload(modalidade='paga', preco='100.00', inclusoes='Preparação',
                            condicoes='Sessão agendada', acao='rascunho')
        self.assertEqual(self.client.post(reverse('master_table_create'), paid).status_code, 302)
        table = TbMesaAnuncio.objects.get(mestre=self.master)
        self.assertEqual(table.estado, 'rascunho')
        self.assertTrue(table.preco_demonstrativo)
        paid.update(revisao=str(table.revisao), acao='enviar')
        self.assertEqual(self.client.post(reverse('master_table_edit', args=[table.pk]), paid).status_code, 200)
        table.refresh_from_db()
        self.assertEqual(table.estado, 'rascunho')

    @patch('home.master_commercial.completed_activity', return_value={
        'completed_tables': 3, 'open_tables': 1, 'system_tables': 2,
        'manual_tables': 1, 'activity_unavailable': False,
    })
    def test_completed_activity_enables_only_demonstrative_paid_listing(self, activity):
        today = timezone.localdate()
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        self.assertFalse(CommercialAuthorizationForm(data={
            'user': self.master.pk, 'autorizada': True, 'observacao': ''}).is_valid())
        adventures = [TbAventuraMestre.objects.create(
            mestre=self.master, nome=f'Mesa legada {n}', data=today-timedelta(days=n),
            jogadores=5, recompensa_mm=0) for n in range(3)]
        for n, adventure in enumerate(adventures):
            TbVerificacaoMesa.objects.create(aventura=adventure, aberta=n == 0,
                validada=True, observacao='Realização conferida pela equipe', validado_por=self.staff)
        with patch('home.master_commercial.completed_activity', return_value={
            'completed_tables': 0, 'open_tables': 0, 'system_tables': 0,
            'manual_tables': 0, 'activity_unavailable': False,
        }):
            TbAutorizacaoVitrine.objects.create(user=self.master, autorizada=True,
                observacao='Vitrine piloto autorizada', avaliado_por=self.staff)
            eligibility = commercial_eligibility(self.master)
            self.assertEqual(eligibility['completed_tables'], 0)
            self.assertEqual(eligibility['open_tables'], 0)
            self.assertFalse(eligibility['eligible'])
        TbAutorizacaoVitrine.objects.filter(user=self.master).update(autorizada=False)
        self.assertEqual(commercial_eligibility(self.master)['completed_tables'], 3)
        activity.assert_called_with(self.master, today)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        TbAutorizacaoVitrine.objects.filter(user=self.master).update(autorizada=True)
        self.assertTrue(commercial_eligibility(self.master)['eligible'])

        self.client.force_login(self.master)
        paid = self.payload(modalidade='paga', preco='100.00', inclusoes='Preparação e sessão',
                            condicoes='Sessão agendada', acao='enviar')
        response = self.client.post(reverse('master_table_create'), paid)
        self.assertEqual(response.status_code, 302, response.content[:500])
        table = TbMesaAnuncio.objects.get(mestre=self.master)
        self.assertEqual(table.estado, 'pendente')
        self.assertTrue(table.preco_demonstrativo)
        self.client.force_login(self.staff)
        response = self.client.post(reverse('master_table_action', args=[table.pk]),
                                    {'acao': 'aprovar', 'revisao': table.revisao})
        self.assertEqual(response.status_code, 302, response.content[:500])
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('master_table_detail', args=[table.pk])),
                            'Preço ilustrativo')
        self.assertContains(self.client.get(reverse('sistemas_missoes')), table.titulo)
        self.assertEqual(TbTransacaoMestre.objects.count(), 0)
        self.assertEqual(TbAventuraMestre.objects.count(), 3)

        TbAutorizacaoVitrine.objects.filter(user=self.master).update(autorizada=False)
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('sistemas_missoes')), table.titulo)
        self.client.force_login(self.master)
        self.assertContains(self.client.get(reverse('profile') + '?aba=mestre'), table.titulo)

    def test_create_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.master)
        self.assertEqual(client.post(reverse('master_table_create'), self.payload()).status_code, 403)
        self.assertFalse(TbMesaAnuncio.objects.exists())

    def test_profile_actions_open_existing_routes_and_owner_can_close(self):
        self.client.force_login(self.master)
        self.assertContains(self.client.get(reverse('profile') + '?aba=mestre'),
                            reverse('master_table_create'))
        self.assertEqual(self.client.post(reverse('master_table_create'), self.payload()).status_code, 302)
        table = TbMesaAnuncio.objects.get(mestre=self.master)
        profile = self.client.get(reverse('profile') + '?aba=mestre')
        self.assertContains(profile, reverse('master_table_edit', args=[table.pk]))
        self.assertContains(profile, reverse('master_table_detail', args=[table.pk]))
        action_url = reverse('master_table_action', args=[table.pk])
        self.assertContains(profile, action_url)
        self.assertContains(profile, 'name="revisao" value="1"', html=False)

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(action_url, {
            'acao': 'encerrar', 'revisao': table.revisao,
        }).status_code, 404)
        self.client.force_login(self.master)
        self.assertEqual(self.client.post(action_url, {
            'acao': 'encerrar', 'revisao': 0,
        }).status_code, 409)
        self.assertEqual(self.client.post(action_url, {
            'acao': 'encerrar', 'revisao': table.revisao,
        }).status_code, 302)
        table.refresh_from_db()
        self.assertEqual(table.estado, 'encerrado')
        page = self.client.get(reverse('profile') + '?aba=mestre')
        self.assertContains(page, table.titulo)
        self.assertNotContains(page, 'Encerrar anúncio')
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 200)

    @patch('home.master_commercial.completed_activity', return_value={
        'completed_tables': 3, 'open_tables': 1, 'system_tables': 2,
        'manual_tables': 1, 'activity_unavailable': False,
    })
    def test_staff_reviewer_authorizes_and_revokes_without_manual_verification(self, activity):
        reviewer = get_user_model().objects.create_user(
            'table_reviewer', password='test-pass', is_staff=True)
        reviewer.user_permissions.add(Permission.objects.get(codename='autorizar_mestres'))
        day = timezone.localdate()
        adventures = [TbAventuraMestre.objects.create(
            mestre=self.master, nome=f'Mesa {n}', data=day-timedelta(days=n),
            jogadores=4, recompensa_mm=0) for n in range(3)]
        verification = TbVerificacaoMesa.objects.create(
            aventura=adventures[0], aberta=True, validada=True,
            observacao='Registro legado preservado', validado_por=self.staff)
        verification_fields = ('pk', 'aventura_id', 'aberta', 'validada',
                               'observacao', 'validado_por_id', 'validado_em')
        old_verifications = list(TbVerificacaoMesa.objects.order_by('pk').values(*verification_fields))
        old_adventures = list(TbAventuraMestre.objects.order_by('pk').values(
            'pk', 'mestre_id', 'nome', 'data', 'jogadores', 'recompensa_mm'))
        self.client.force_login(reviewer)
        dashboard = self.client.get(reverse('master_dashboard'))
        self.assertNotContains(dashboard, 'Verificar mesas realizadas')
        self.assertNotContains(dashboard, 'data-master-moderation="verificacao"')
        self.assertContains(dashboard, 'Autorizar vitrine demonstrativa')
        for adventure in adventures:
            for action in ('validar', 'invalidar'):
                with self.subTest(adventure=adventure.pk, action=action):
                    response = self.client.post(reverse('master_verify_table', args=[adventure.pk]), {
                        'acao': action, 'aberta': 'sim',
                        'observacao': 'Tentativa no fluxo encerrado', 'confirmar': 'sim',
                    })
                    self.assertEqual(response.status_code, 410)
                    self.assertEqual(list(TbVerificacaoMesa.objects.order_by('pk').values(
                        *verification_fields)), old_verifications)
        legacy_admin = admin.site._registry[TbVerificacaoMesa]
        request = RequestFactory().post('/')
        request.user = reviewer
        self.assertTrue(legacy_admin.has_view_permission(request, verification))
        self.assertFalse(legacy_admin.has_add_permission(request))
        self.assertFalse(legacy_admin.has_change_permission(request, verification))
        self.assertFalse(legacy_admin.has_delete_permission(request, verification))
        self.assertTrue({'aventura', 'aberta', 'validada', 'observacao',
                         'validado_por', 'validado_em'}.issubset(
            legacy_admin.get_readonly_fields(request)))
        with self.assertRaises(PermissionDenied):
            legacy_admin.save_model(request, verification, None, change=True)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        auth_url = reverse('master_authorize_listing', args=[self.master.pk])
        self.assertEqual(self.client.post(auth_url, {'acao': 'autorizar',
            'observacao': 'Piloto autorizado', 'confirmar': 'sim'}).status_code, 302)
        self.assertTrue(commercial_eligibility(self.master)['eligible'])
        current_activity = activity.return_value
        activity.return_value = dict(current_activity, completed_tables=0, open_tables=0,
                                     system_tables=0, manual_tables=0)
        self.assertFalse(commercial_eligibility(
            self.master, today=day + timedelta(days=30))['eligible'])
        activity.assert_called_with(self.master, day + timedelta(days=30))
        activity.return_value = current_activity
        self.assertTrue(commercial_eligibility(self.master)['eligible'])
        self.assertEqual(self.client.post(auth_url, {'acao': 'revogar',
            'observacao': 'Piloto encerrado', 'confirmar': 'sim'}).status_code, 302)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        TbPerfilMestre.objects.create(user=reviewer, status_mestre='aprovado', modo='mestre')
        self.assertEqual(self.client.post(reverse('master_authorize_listing', args=[reviewer.pk]), {
            'acao': 'autorizar', 'observacao': 'Autoavaliação', 'confirmar': 'sim',
        }).status_code, 403)
        self.assertFalse(TbAutorizacaoVitrine.objects.filter(user=reviewer).exists())
        self.assertEqual(TbTransacaoMestre.objects.count(), 0)
        self.assertEqual(TbAventuraMestre.objects.count(), 3)
        self.client.force_login(self.master)
        self.assertEqual(self.client.post(auth_url, {'acao': 'autorizar',
            'observacao': 'Autoavaliação', 'confirmar': 'sim'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('master_verify_table', args=[adventures[0].pk]), {
            'acao': 'validar', 'observacao': 'Autoavaliação', 'confirmar': 'sim'}).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(reviewer)
        self.assertEqual(csrf_client.post(auth_url, {'acao': 'autorizar',
            'observacao': 'Tentativa sem CSRF', 'confirmar': 'sim'}).status_code, 403)
        self.assertEqual(csrf_client.post(reverse('master_verify_table', args=[adventures[0].pk]), {
            'acao': 'invalidar', 'observacao': 'Tentativa sem CSRF', 'confirmar': 'sim',
        }).status_code, 403)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        self.assertEqual(list(TbVerificacaoMesa.objects.order_by('pk').values(
            *verification_fields)), old_verifications)
        self.assertEqual(list(TbAventuraMestre.objects.order_by('pk').values(
            'pk', 'mestre_id', 'nome', 'data', 'jogadores', 'recompensa_mm')), old_adventures)
        self.assertEqual(TbTransacaoMestre.objects.count(), 0)
