# -*- coding: utf-8 -*-
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings
from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from home.market_services import (
    create_loan_proposal, pay_loan, register_transaction, respond_loan,
    start_training, sync_overdue_loans, sync_training,
    tables_played,
)
from home.models import (
    TbEmprestimoPersonagem, TbIdioma, TbItemMundano, TbPersonagem,
    TbPersonagemAventura, TbPersonagemProficiencia, TbTransacao,
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

    def test_community_reward_does_not_count_as_played_table(self):
        TbPersonagemAventura.objects.create(
            id_personagem=self.borrower, nome_aventura='Mesa', qtd_aventuras=2)
        TbPersonagemAventura.objects.create(
            id_personagem=self.borrower, nome_aventura='Recompensa da comunidade',
            qtd_aventuras=20, origem='recompensa_comunidade')
        self.borrower.aventuras = 22
        self.borrower.save(update_fields=['aventuras'])

        self.assertEqual(tables_played(self.borrower), 1)

    def test_legacy_adventures_survive_later_community_reward(self):
        self.borrower.aventuras = 3
        self.borrower.save(update_fields=['aventuras'])
        TbPersonagemAventura.objects.create(
            id_personagem=self.borrower, nome_aventura='Recompensa da comunidade',
            qtd_aventuras=1, origem='recompensa_comunidade')
        self.borrower.aventuras = 4
        self.borrower.save(update_fields=['aventuras'])

        self.assertEqual(tables_played(self.borrower), 3)

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

    def test_active_loan_review_receives_exact_remaining_balance(self):
        TbEmprestimoPersonagem.objects.create(
            credor=self.lender, devedor=self.borrower, proponente=self.lender,
            valor_original_pc=10000, valor_total_pc=10000,
            valor_pago_pc=200, status='ativo')
        self.client.force_login(self.borrower_user)
        response = self.client.get(
            reverse('mercado_servicos') + f'?personagem={self.borrower.pk}')
        self.assertContains(response, 'data-balance-pc="9800"')
        self.assertContains(response, 'name="valor_po" value="" formnovalidate')

    def test_payment_above_remaining_balance_debits_only_the_balance(self):
        loan = TbEmprestimoPersonagem.objects.create(
            credor=self.lender, devedor=self.borrower, proponente=self.lender,
            valor_original_pc=10000, valor_total_pc=10000,
            valor_pago_pc=200, status='ativo')
        _loan, status = pay_loan(self.borrower_user, loan.pk, 20000)
        self.assertEqual(status, 'emprestimo_quitado')
        loan.refresh_from_db()
        self.borrower.refresh_from_db()
        self.lender.refresh_from_db()
        self.assertEqual(loan.valor_pago_pc, 10000)
        self.assertEqual(self.borrower.carteira_pc, 10200)
        self.assertEqual(self.lender.carteira_pc, 109800)

    def test_training_catalog_groups_tools_without_changing_payment_tokens(self):
        for slug, subcategory in (
            ('kit-teste', 'ferramenta_artesao'),
            ('flauta-teste', 'instrumento'),
            ('xadrez-teste', 'conjunto_jogo'),
        ):
            TbItemMundano.objects.create(
                slug=slug, nome=slug, categoria='ferramenta', subcategoria=subcategory)
        self.client.force_login(self.borrower_user)
        response = self.client.get(reverse('mercado_servicos'))
        self.assertEqual(response.status_code, 200)
        rows = response.context['treinamentos_disponiveis']
        indices = {row['token']: index for index, row in enumerate(rows)}
        self.assertLess(indices['idioma:idioma-teste'], indices['ferramenta:kit-teste'])
        self.assertLess(indices['ferramenta:kit-teste'], indices['ferramenta:flauta-teste'])
        self.assertLess(indices['ferramenta:flauta-teste'], indices['ferramenta:xadrez-teste'])
        self.assertIn({'token': 'ferramenta:flauta-teste', 'nome': 'flauta-teste',
                       'grupo': 'Instrumentos'}, rows)
        self.assertContains(response, '<optgroup label="Instrumentos">')
        self.assertContains(response, 'id="training-search"')
        self.assertContains(response, 'id="training-group"')

    def test_service_actions_return_to_their_own_section_without_charging(self):
        self.client.force_login(self.borrower_user)
        training = self.client.post(
            reverse('mercado_iniciar_treinamento', args=[self.borrower.pk]),
            {'treinamento': 'invalido'})
        self.assertEqual(training.status_code, 302)
        self.assertTrue(training['Location'].endswith('#treinamentos'))
        loan = self.client.post(
            reverse('mercado_propor_emprestimo', args=[self.borrower.pk]),
            {'contraparte': self.lender.pk, 'papel': 'invalido'})
        self.assertEqual(loan.status_code, 302)
        self.assertTrue(loan['Location'].endswith('#emprestimos'))
        self.borrower.refresh_from_db()
        self.assertEqual(self.borrower.carteira_pc, 20000)
        self.assertEqual(TbTransacao.objects.filter(id_personagem=self.borrower).count(), 0)


class MercadoServicosBrowserTests(StaticLiveServerTestCase):
    def test_training_search_groups_and_loan_tab_stay_separate(self):
        import json
        import shutil
        import subprocess
        import tempfile
        import time
        from pathlib import Path
        from urllib.request import urlopen

        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponível.')

        user = get_user_model().objects.create_user('training-browser')
        borrower = TbPersonagem.objects.create(
            dono=user, nome='Aprendiz', carteira_pc=20000, aventuras=2)
        lender_user = get_user_model().objects.create_user('credor-browser')
        lender = TbPersonagem.objects.create(
            dono=lender_user, nome='Credor', carteira_pc=50000, aventuras=2)
        loan = TbEmprestimoPersonagem.objects.create(
            credor=lender, devedor=borrower, proponente=lender,
            valor_original_pc=10000, valor_total_pc=10000, status='pendente')
        TbIdioma.objects.create(slug='idioma-teste', nome='Idioma de Teste')
        for slug, subcategory in (
            ('kit-teste', 'ferramenta_artesao'),
            ('flauta-teste', 'instrumento'),
            ('xadrez-teste', 'conjunto_jogo'),
        ):
            TbItemMundano.objects.create(
                slug=slug, nome=slug, categoria='ferramenta', subcategoria=subcategory)
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-training-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                for _ in range(80):
                    if port_file.exists():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.exists())
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=10)
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('id') == sequence:
                            self.assertNotIn('error', result, method)
                            return result['result']

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_servicos')})
                wait_for('document.querySelector("#training-choice") !== null')
                self.assertEqual(js('Array.from(document.querySelectorAll("#training-choice optgroup")).map(group => group.label).join(",")'), 'Idiomas,Ferramentas,Instrumentos,Jogos')
                self.assertTrue(js('document.querySelector("#treinamentos").textContent.includes("instrumento ou jogo")'))
                self.assertTrue(js('document.querySelector("#emprestimos").hidden'))
                js('window.__trainingMarker = 42')
                js('document.querySelector("#training-search").value = "flauta"; document.querySelector("#training-search").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('Array.from(document.querySelectorAll("#training-choice option")).filter(option => option.value).length === 1')
                self.assertEqual(js('document.querySelector("#training-choice optgroup").label'), 'Instrumentos')
                js('document.querySelector("#training-group").value = "Jogos"; document.querySelector("#training-group").dispatchEvent(new Event("change", {bubbles:true}))')
                wait_for('document.querySelector("#training-choice").disabled && document.querySelector("#training-search-status").textContent.includes("Nenhum")')
                js('document.querySelector("[data-training-clear]").click()')
                wait_for('document.querySelectorAll("#training-choice optgroup").length === 4 && !document.querySelector("#training-choice").disabled')
                js('document.querySelector("#tab-emprestimos").click()')
                wait_for('location.hash === "#emprestimos" && document.querySelector("#treinamentos").hidden && !document.querySelector("#emprestimos").hidden')
                self.assertEqual(js('window.__trainingMarker'), 42)
                js('history.back()')
                wait_for('location.hash === "" && !document.querySelector("#treinamentos").hidden && document.querySelector("#emprestimos").hidden')
                self.assertEqual(js('window.__trainingMarker'), 42)
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                js('document.querySelector("#training-choice").value = "idioma:idioma-teste"; document.querySelector(".training-start button[type=submit]").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertTrue(js('document.querySelector("[data-service-subject]").textContent.includes("Idioma de Teste")'))
                self.assertTrue(js('document.querySelector("[data-service-amount]").textContent.includes("100 PO")'))
                borrower.refresh_from_db()
                self.assertEqual(borrower.carteira_pc, 20000)
                js('document.querySelector("[data-service-back]").click()')
                wait_for('!document.querySelector("#service-review").open')
                borrower.refresh_from_db()
                self.assertEqual(borrower.carteira_pc, 20000)
                js('document.querySelector(".training-start button[type=submit]").click()')
                wait_for('document.querySelector("#service-review").open')
                js('document.querySelector("[data-service-confirm]").click()')
                wait_for('document.querySelector(".service-feedback")?.textContent.includes("Treinamento iniciado")')
                borrower.refresh_from_db()
                self.assertEqual(borrower.carteira_pc, 10000)
                js('document.querySelector("#tab-emprestimos").click()')
                wait_for('!document.querySelector("#emprestimos").hidden && !!document.querySelector("button[value=aceitar]")')
                js('document.querySelector("button[value=aceitar]").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertTrue(js('document.querySelector("[data-service-note]").textContent.includes("transferido")'))
                loan.refresh_from_db()
                self.assertEqual(loan.status, 'pendente')
                js('document.querySelector("[data-service-back]").click()')
                wait_for('!document.querySelector("#service-review").open')
                loan.refresh_from_db()
                self.assertEqual(loan.status, 'pendente')
                js('document.querySelector("button[value=aceitar]").click()')
                wait_for('document.querySelector("#service-review").open')
                js('document.querySelector("[data-service-confirm]").click()')
                wait_for('!!document.querySelector(".loan-payment")')
                loan.refresh_from_db()
                self.assertEqual(loan.status, 'ativo')
                borrower.refresh_from_db()
                self.assertEqual(borrower.carteira_pc, 20000)
                js('document.querySelector(".loan-payment button:not([name])").click()')
                self.assertFalse(js('document.querySelector("#service-review").open'))
                loan.refresh_from_db()
                self.assertEqual(loan.valor_pago_pc, 0)
                js('document.querySelector(".loan-payment input[name=valor_po]").value = "2"; document.querySelector(".loan-payment button:not([name])").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertTrue(js('document.querySelector("[data-service-amount]").textContent.includes("2 PO")'))
                js('document.querySelector("[data-service-confirm]").click()')
                wait_for('document.querySelector(".service-feedback")?.textContent.includes("Pagamento registrado")')
                loan.refresh_from_db()
                self.assertEqual(loan.valor_pago_pc, 200)
                borrower.refresh_from_db()
                self.assertEqual(borrower.carteira_pc, 19800)
                js('document.querySelector(".loan-payment input[name=valor_po]").value = "200"; document.querySelector(".loan-payment button:not([name])").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertEqual(js('document.querySelector("[data-service-amount]").textContent'), '98 PO')
                js('document.querySelector("[data-service-back]").click()')
                wait_for('!document.querySelector("#service-review").open')
                loan.refresh_from_db()
                self.assertEqual(loan.valor_pago_pc, 200)
                js('document.querySelector(".loan-payment input[name=valor_po]").value = "0"')
                js('document.querySelector(".loan-payment button[name=valor_po]").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertTrue(js('document.querySelector("#service-review-title").textContent.includes("quitação")'))
                loan.refresh_from_db()
                self.assertEqual(loan.status, 'ativo')
                js('document.querySelector("[data-service-confirm]").click()')
                wait_for('document.querySelector(".service-feedback")?.textContent.includes("quitado")')
                loan.refresh_from_db()
                self.assertEqual(loan.status, 'quitado')
                borrower.refresh_from_db()
                self.assertEqual(borrower.carteira_pc, 10000)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
