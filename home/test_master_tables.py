"""Moderation and public visibility of site listings on an isolated database."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import TbMesaAnuncio, TbPerfilMestre


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

    def test_create_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.master)
        self.assertEqual(client.post(reverse('master_table_create'), self.payload()).status_code, 403)
        self.assertFalse(TbMesaAnuncio.objects.exists())
