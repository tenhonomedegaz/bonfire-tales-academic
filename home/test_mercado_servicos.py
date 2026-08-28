# -*- coding: utf-8 -*-
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from home.market_services import (
    create_loan_proposal, register_transaction, respond_loan,
    start_training, sync_overdue_loans, sync_training,
)
from home.models import (
    TbEmprestimoPersonagem, TbIdioma, TbPersonagem,
    TbPersonagemProficiencia, TbTransacao,
)
from home.views import _opcoes_resposta


class RedirectDeOpcoesTests(SimpleTestCase):
    def test_redirect_preserva_query_string(self):
        request = RequestFactory().post('/teste/')
        plain = _opcoes_resposta(request, None, '/destino/', msg='trocada')
        queried = _opcoes_resposta(
            request, None, '/destino/?aba=magias', msg='trocada')
        self.assertEqual(plain['Location'], '/destino/?opcao=trocada')
        self.assertEqual(
            queried['Location'], '/destino/?aba=magias&opcao=trocada')


class MercadoServicosTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.borrower_user = User.objects.create_user('devedor', password='x')
        self.lender_user = User.objects.create_user('credor', password='x')
        self.staff_user = User.objects.create_user(
            'staff_mercado', password='x', is_staff=True)
        self.borrower = TbPersonagem.objects.create(
            dono=self.borrower_user, nome='Devedor', publico=True,
            aventuras=2, carteira_pc=20000)
        self.lender = TbPersonagem.objects.create(
            dono=self.lender_user, nome='Credor', publico=True,
            aventuras=2, carteira_pc=100000)
        self.language = TbIdioma.objects.create(
            slug='idioma-teste', nome='Idioma de Teste')

    def test_training_charges_upfront_blocks_second_and_completes(self):
        row, status = start_training(
            self.borrower, 'idioma:%s' % self.language.slug)
        self.assertEqual(status, 'treinamento_iniciado')
        self.borrower.refresh_from_db()
        self.assertEqual(self.borrower.carteira_pc, 10000)
        self.assertFalse(TbPersonagemProficiencia.objects.filter(
            id_personagem=self.borrower, nome=self.language.nome).exists())

        _other, status = start_training(
            self.borrower, 'idioma:%s' % self.language.slug)
        self.assertEqual(status, 'treinamento_ativo')

        row.conclui_em = timezone.now() - timedelta(seconds=1)
        row.save(update_fields=['conclui_em'])
        sync_training(self.borrower)
        row.refresh_from_db()
        self.assertEqual(row.status, 'concluido')
        self.assertTrue(TbPersonagemProficiencia.objects.filter(
            id_personagem=self.borrower, tipo='idioma',
            nome=self.language.nome).exists())
        self.assertTrue(TbTransacao.objects.filter(
            id_personagem=self.borrower, tipo='treinamento',
            valor_pc=-10000).exists())

    def test_loan_acceptance_overdue_fine_and_income_garnishment(self):
        loan, status = create_loan_proposal(
            self.borrower, self.lender, 'solicitar', 60000)
        self.assertEqual(status, 'emprestimo_solicitado')
        loan, status = respond_loan(self.lender_user, loan.pk, 'aceitar')
        self.assertEqual(status, 'emprestimo_aceito')
        self.borrower.refresh_from_db()
        self.lender.refresh_from_db()
        self.assertEqual(self.borrower.carteira_pc, 80000)
        self.assertEqual(self.lender.carteira_pc, 40000)

        self.borrower.carteira_pc = 0
        self.borrower.save(update_fields=['carteira_pc'])
        loan.vence_em = timezone.now() - timedelta(seconds=1)
        loan.save(update_fields=['vence_em'])
        sync_overdue_loans(personagem=self.borrower)
        loan.refresh_from_db()
        self.assertEqual(loan.valor_total_pc, 72000)
        self.assertTrue(loan.multa_aplicada)

        self.borrower.carteira_pc = 10000
        self.borrower.save(update_fields=['carteira_pc'])
        register_transaction(
            self.borrower, 'aventura', 'Renda depois do vencimento', 10000)
        self.borrower.refresh_from_db()
        self.lender.refresh_from_db()
        loan.refresh_from_db()
        self.assertEqual(self.borrower.carteira_pc, 0)
        self.assertEqual(self.lender.carteira_pc, 50000)
        self.assertEqual(loan.valor_pago_pc, 10000)
        self.assertTrue(TbTransacao.objects.filter(
            id_personagem=self.borrower, tipo='repasse-divida',
            valor_pc=-10000).exists())

    def test_rank_limit_and_active_contract_are_enforced(self):
        _loan, status = create_loan_proposal(
            self.borrower, self.lender, 'solicitar', 60100)
        self.assertEqual(status, 'emprestimo_limite')
        loan = TbEmprestimoPersonagem.objects.create(
            credor=self.lender, devedor=self.borrower, proponente=self.borrower,
            valor_original_pc=10000, valor_total_pc=10000, status='ativo',
            aceito_em=timezone.now(), vence_em=timezone.now() + timedelta(days=30))
        other_user = get_user_model().objects.create_user('terceiro', password='x')
        other = TbPersonagem.objects.create(
            dono=other_user, nome='Terceiro', aventuras=2, publico=True)
        _loan, status = create_loan_proposal(
            self.borrower, other, 'solicitar', 10000)
        self.assertEqual(status, 'emprestimo_ativo')
        self.assertEqual(loan.status, 'ativo')

    def test_overdue_fee_uses_original_value_after_partial_payment(self):
        loan = TbEmprestimoPersonagem.objects.create(
            credor=self.lender, devedor=self.borrower, proponente=self.borrower,
            valor_original_pc=20000, valor_total_pc=20000, valor_pago_pc=10000,
            status='ativo', aceito_em=timezone.now(),
            vence_em=timezone.now() - timedelta(seconds=1))
        sync_overdue_loans()
        loan.refresh_from_db()
        self.assertEqual(loan.valor_total_pc, 24000)
        self.assertEqual(loan.saldo_devedor_pc, 14000)

    def test_staff_can_monitor_and_reconcile_open_loans(self):
        due = timezone.now() + timedelta(days=10)
        loan = TbEmprestimoPersonagem.objects.create(
            credor=self.lender, devedor=self.borrower, proponente=self.borrower,
            valor_original_pc=20000, valor_total_pc=20000, status='ativo',
            aceito_em=timezone.now(), vence_em=due)
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('mercado_servicos'))
        self.assertContains(response, 'Controle de empréstimos')
        self.assertContains(response, '@devedor')

        response = self.client.post(
            reverse('mercado_staff_emprestimo', args=[loan.pk]),
            {'acao': 'prorrogar'})
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertGreaterEqual(loan.vence_em, due + timedelta(days=29))
        self.assertTrue(TbTransacao.objects.filter(
            id_personagem=self.borrower, tipo='ajuste',
            detalhes_json__operacao_staff='prorrogar').exists())

    def test_non_staff_cannot_control_loans(self):
        loan = TbEmprestimoPersonagem.objects.create(
            credor=self.lender, devedor=self.borrower, proponente=self.borrower,
            valor_original_pc=10000, valor_total_pc=10000)
        self.client.force_login(self.borrower_user)
        response = self.client.post(
            reverse('mercado_staff_emprestimo', args=[loan.pk]),
            {'acao': 'cancelar'})
        self.assertEqual(response.status_code, 404)

    def test_services_are_in_market_and_sheet_has_no_training_tab(self):
        self.client.force_login(self.borrower_user)
        response = self.client.get(reverse('mercado_servicos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Treinamentos')
        self.assertContains(response, 'Empréstimos')
        sheet = self.client.get(reverse('ficha_detail', args=[self.borrower.pk]))
        self.assertNotContains(sheet, 'data-tab="treinamentos"')
