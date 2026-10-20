"""Review of existing market trades before their AJAX POST."""

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

from home.models import TbItemMagico, TbItemMundano, TbPersonagem


class MarketTransactionReviewBrowserTests(StaticLiveServerTestCase):
    def test_buy_and_sell_review_on_mobile_preserves_original_post(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires an isolated PostgreSQL test database.')
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

        user = get_user_model().objects.create_user('market-review-browser')
        character = TbPersonagem.objects.create(dono=user, nome='Ficha Revisão', carteira_pc=10000)
        mundane = TbItemMundano.objects.create(nome='Corda de Revisão', slug='corda-review', preco='1 PO')
        character.inventario.create(nome='Corda de Revisão', qtd=2, custo='1 PO', id_item_mundano=mundane)
        magic = TbItemMagico.objects.create(nome='Anel de Revisão', slug='anel-review', preco=1)
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-market-review-', ignore_cleanup_errors=True) as profile:
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
                    for _ in range(250):
                        if js(expression):
                            return
                        time.sleep(.2)
                    state = js('''({page:location.href, ready:document.readyState,
                        calls:window.tradeCalls, reviewOpen:document.querySelector('[data-shop-review]')?.open,
                        feedback:document.querySelector('[data-shop-feedback]')?.textContent,
                        formPresent:!!document.querySelector('[data-shop-detail] [data-shop-buy]'),
                        formValid:document.querySelector('[data-shop-detail] [data-shop-buy]')?.checkValidity()})''')
                    self.fail(f'Timed out waiting for {expression}; state={state}')

                def intercept_trades():
                    js('''(() => {
                      window.tradeCalls = [];
                      const original = window.fetch;
                      window.fetch = (url, options = {}) => {
                        if (options.method === 'POST' && options.body instanceof FormData && options.body.has('item')) {
                          window.tradeCalls.push({url: String(url), fields: Object.fromEntries(options.body)});
                          return Promise.resolve(new Response(JSON.stringify({ok:true, carteira_display:'99 PO'}),
                            {status:200, headers:{'Content-Type':'application/json'}}));
                        }
                        return original(url, options);
                      };
                    })()''')

                call('Network.enable')
                call('Page.bringToFront')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_mundanos')})
                wait_for(f'document.querySelector(\'[data-mkt-row][data-target="mu-{mundane.pk}"]\') !== null')
                intercept_trades()
                js(f'document.querySelector(\'[data-mkt-row][data-target="mu-{mundane.pk}"]\').click()')
                wait_for('document.querySelector("[data-shop-detail] [data-shop-buy]") !== null')
                js('document.querySelector("[data-shop-detail] [data-shop-buy] button[type=submit]").click()')
                wait_for('document.querySelector("[data-shop-review]").open')
                self.assertIn('Corda de Revisão', js('document.querySelector("[data-shop-review-item]").textContent'))
                self.assertIn(character.nome, js('document.querySelector("[data-shop-review-character]").textContent'))
                self.assertTrue(js('document.querySelector("[data-shop-review-total-row]").hidden'))
                self.assertLessEqual(js('document.querySelector("[data-shop-review]").getBoundingClientRect().right'), 360)
                self.assertEqual(js('tradeCalls.length'), 0)
                js('document.querySelector("[data-shop-review-cancel]").click()')
                wait_for('!document.querySelector("[data-shop-review]").open')
                self.assertEqual(js('tradeCalls.length'), 0)
                js('document.querySelector("[data-shop-detail] [data-shop-buy] button[type=submit]").click()')
                wait_for('document.querySelector("[data-shop-review]").open')
                js('document.querySelector("[data-shop-review-confirm]").click()')
                wait_for('tradeCalls.length === 1')
                self.assertEqual(js('tradeCalls[0].fields.item'), mundane.slug)
                self.assertIn(str(character.pk), js('tradeCalls[0].url'))

                js('document.querySelector("[data-shop-tab=vender]").click()')
                wait_for('document.querySelector("[data-shop-pane=vender] [data-mkt-row]") !== null')
                js('document.querySelector("[data-shop-pane=vender] [data-mkt-row]").click()')
                wait_for('document.querySelector("[data-shop-detail] [data-shop-sell]") !== null')
                js('document.querySelector("[data-shop-sell] [name=qtd]").value = "2"')
                js('document.querySelector("[data-shop-sell] button[type=submit]").click()')
                wait_for('document.querySelector("[data-shop-review]").open')
                self.assertEqual(js('document.querySelector("[data-shop-review-quantity]").textContent'), '2')
                self.assertIn('Crédito', js('document.querySelector("[data-shop-review-price-label]").textContent'))
                js('document.querySelector("[data-shop-review-confirm]").click()')
                wait_for('tradeCalls.length === 2')
                self.assertEqual(js('tradeCalls[1].fields.qtd'), '2')

                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_magicos')})
                wait_for(f'document.querySelector(\'[data-mkt-row][data-target="mi-{magic.pk}"]\') !== null')
                intercept_trades()
                js(f'document.querySelector(\'[data-mkt-row][data-target="mi-{magic.pk}"]\').click()')
                wait_for('document.querySelector("[data-shop-detail] [data-shop-buy]") !== null')
                js('document.querySelector("[data-shop-buy] button[type=submit]").click()')
                wait_for('document.querySelector("[data-shop-review]").open')
                self.assertIn('Anel de Revisão', js('document.querySelector("[data-shop-review-item]").textContent'))
                self.assertFalse(js('document.querySelector("[data-shop-review-total-row]").hidden'))
                self.assertEqual(js('document.querySelector("[data-shop-review-total]").textContent'), js('document.querySelector("[data-shop-detail] [data-market-total]").textContent'))
                self.assertEqual(js('tradeCalls.length'), 0)
                js('document.querySelector("[data-shop-review-confirm]").click()')
                wait_for('tradeCalls.length === 1')
                self.assertEqual(js('tradeCalls[0].fields.item'), magic.slug)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
