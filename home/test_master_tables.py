"""Moderation and public visibility of site listings on an isolated database."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .master_commercial import commercial_eligibility
from .master_commercial_admin import EvidenceForm, CommercialAuthorizationForm
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

    def test_free_listing_requires_owner_staff_review_and_current_revision(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('master_table_create'), self.payload()).status_code, 403)

        self.client.force_login(self.master)
        result = self.client.post(reverse('master_table_create'), self.payload())
        self.assertEqual(result.status_code, 302, result.content[:500])
        table = TbMesaAnuncio.objects.get(mestre=self.master)
        self.assertEqual(table.estado, 'pendente')
        self.assertTrue(table.preco_demonstrativo)
        self.assertEqual(table.revisao, 1)
        self.assertContains(self.client.get(reverse('profile') + '?aba=mestre'), 'Preparar anúncio')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 404)
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
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse('sistemas_missoes')), table.titulo)

        TbPerfilMestre.objects.filter(user=self.master).update(status_mestre='suspenso')
        self.assertEqual(self.client.get(reverse('master_table_detail', args=[table.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('sistemas_missoes')), table.titulo)
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

    def test_verified_tables_enable_only_demonstrative_paid_listing(self):
        today = timezone.localdate()
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        self.assertFalse(CommercialAuthorizationForm(data={
            'user': self.master.pk, 'autorizada': True, 'observacao': ''}).is_valid())
        adventures = [TbAventuraMestre.objects.create(
            mestre=self.master, nome=f'Mesa verificada {n}', data=today-timedelta(days=n),
            jogadores=5, recompensa_mm=0) for n in range(3)]
        self.assertFalse(EvidenceForm(data={
            'aventura': adventures[0].pk, 'aberta': True, 'validada': True,
            'observacao': ''}).is_valid())
        for n, adventure in enumerate(adventures):
            TbVerificacaoMesa.objects.create(aventura=adventure, aberta=n == 0,
                validada=True, observacao='Realização conferida pela equipe', validado_por=self.staff)
        self.assertEqual(commercial_eligibility(self.master)['completed_tables'], 3)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        TbAutorizacaoVitrine.objects.create(user=self.master, autorizada=True,
            observacao='Vitrine piloto autorizada', avaliado_por=self.staff)
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

    def test_staff_reviewer_can_verify_and_revoke_without_changing_rewards(self):
        reviewer = get_user_model().objects.create_user(
            'table_reviewer', password='test-pass', is_staff=True)
        reviewer.user_permissions.add(Permission.objects.get(codename='autorizar_mestres'))
        day = timezone.localdate()
        adventures = [TbAventuraMestre.objects.create(
            mestre=self.master, nome=f'Mesa {n}', data=day-timedelta(days=n),
            jogadores=4, recompensa_mm=0) for n in range(3)]
        self.client.force_login(reviewer)
        dashboard = self.client.get(reverse('master_dashboard'))
        self.assertContains(dashboard, 'Verificar mesas realizadas')
        self.assertContains(dashboard, 'Autorizar vitrine demonstrativa')
        for n, adventure in enumerate(adventures):
            response = self.client.post(reverse('master_verify_table', args=[adventure.pk]), {
                'acao': 'validar', 'aberta': 'sim' if n == 0 else '',
                'observacao': 'Mesa concluída e divulgação conferida', 'confirmar': 'sim',
            })
            self.assertEqual(response.status_code, 302)
        self.assertEqual(TbVerificacaoMesa.objects.filter(validada=True).count(), 3)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        auth_url = reverse('master_authorize_listing', args=[self.master.pk])
        self.assertEqual(self.client.post(auth_url, {'acao': 'autorizar',
            'observacao': 'Piloto autorizado', 'confirmar': 'sim'}).status_code, 302)
        self.assertTrue(commercial_eligibility(self.master)['eligible'])
        self.assertFalse(commercial_eligibility(
            self.master, today=day + timedelta(days=30))['eligible'])
        self.assertEqual(self.client.post(reverse('master_verify_table', args=[adventures[0].pk]), {
            'acao': 'invalidar', 'observacao': 'Evidência retirada', 'confirmar': 'sim',
        }).status_code, 302)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
        self.assertEqual(self.client.post(reverse('master_verify_table', args=[adventures[0].pk]), {
            'acao': 'validar', 'aberta': 'sim', 'observacao': 'Evidência reconferida',
            'confirmar': 'sim',
        }).status_code, 302)
        self.assertTrue(commercial_eligibility(self.master)['eligible'])
        self.assertEqual(self.client.post(auth_url, {'acao': 'revogar',
            'observacao': 'Piloto encerrado', 'confirmar': 'sim'}).status_code, 302)
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
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
        self.assertFalse(commercial_eligibility(self.master)['eligible'])
