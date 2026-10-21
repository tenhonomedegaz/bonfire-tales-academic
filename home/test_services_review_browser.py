"""Browser coverage for loan review before the existing payment POST."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import TbEmprestimoPersonagem, TbPersonagem


class ServicesReviewBrowserTests(StaticLiveServerTestCase):
    def test_payment_review_identifies_debtor_and_caps_amount_on_mobile(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome or Edge unavailable.')

        user = get_user_model().objects.create_user('loan-review-browser')
        creditor_user = get_user_model().objects.create_user('loan-creditor-browser')
        debtor = TbPersonagem.objects.create(
            dono=user, nome='Ficha Devedora', carteira_pc=20000, aventuras=2)
        creditor = TbPersonagem.objects.create(
            dono=creditor_user, nome='Ficha Credora', carteira_pc=50000, aventuras=2)
        loan = TbEmprestimoPersonagem.objects.create(
            credor=creditor, devedor=debtor, proponente=creditor,
            valor_original_pc=10000, valor_total_pc=10000,
            valor_pago_pc=200, status='ativo')
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-loan-review-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                for _ in range(150):
                    if port_file.exists() or process.poll() is not None:
                        break
                    time.sleep(.2)
                self.assertTrue(port_file.exists(), 'Browser did not start.')
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=10) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=30)
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
                    for _ in range(200):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Timed out waiting for {expression}')

                call('Network.enable')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                url = self.live_server_url + reverse('mercado_servicos') + f'?personagem={debtor.pk}#emprestimos'
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector(".loan-payment") && document.readyState === "complete"')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), 360)
                js('document.querySelector(".loan-payment input[name=valor_po]").value = "200"; document.querySelector(".loan-payment button:not([name])").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertEqual(js('document.querySelector("[data-service-subject]").textContent'), 'Ficha Devedora → Ficha Credora')
                self.assertEqual(js('document.querySelector("[data-service-amount]").textContent'), '98 PO')
                self.assertLessEqual(js('document.querySelector("#service-review").getBoundingClientRect().right'), 360)
                js('document.querySelector("[data-service-back]").click()')
                wait_for('!document.querySelector("#service-review").open')
                loan.refresh_from_db()
                self.assertEqual(loan.valor_pago_pc, 200)

                js('document.querySelector(".loan-payment input[name=valor_po]").value = "0"; document.querySelector(".loan-payment button[name=valor_po]").click()')
                wait_for('document.querySelector("#service-review").open')
                self.assertEqual(js('document.querySelector("[data-service-subject]").textContent'), 'Ficha Devedora → Ficha Credora')
                js('document.querySelector("#service-review").dispatchEvent(new Event("close"))')
                js('document.querySelector("[data-service-confirm]").click()')
                for _ in range(200):
                    loan.refresh_from_db()
                    if loan.status == 'quitado':
                        break
                    time.sleep(.2)
                self.assertEqual(loan.status, 'quitado')
                debtor.refresh_from_db()
                creditor.refresh_from_db()
                self.assertEqual(debtor.carteira_pc, 10200)
                self.assertEqual(creditor.carteira_pc, 59800)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
