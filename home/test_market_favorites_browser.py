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

from home.models import MarketItemFavorite, TbItemMagico, TbItemMundano


class MarketFavoriteBrowserTests(StaticLiveServerTestCase):
    def test_save_filter_reload_and_other_market_on_mobile(self):
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

        user = get_user_model().objects.create_user('market-favorite-browser')
        mundane = TbItemMundano.objects.create(
            nome='Corda de favorita', slug='corda-browser', preco='1 PO',
            imagem_url='//external.example/item.svg')
        TbItemMundano.objects.create(nome='Tocha comum', slug='tocha-browser', preco='1 PC')
        magic = TbItemMagico.objects.create(
            nome='Anel de favorita', slug='anel-browser', preco=1,
            imagem_url='/static/assets/logo.png')
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-favorites-', ignore_cleanup_errors=True) as profile:
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
                call('Emulation.setDeviceMetricsOverride', {'width': 360, 'height': 800,
                                                            'deviceScaleFactor': 1, 'mobile': True})
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_mundanos')})
                wait_for('document.querySelector("[data-shop-favorite] button") !== null')
                self.assertTrue(js('document.querySelector("[data-shop-detail] .mkt-sigil-letter") !== null'))
                self.assertFalse(js('document.querySelector("[data-shop-detail] img") !== null'))
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
                js('document.querySelector("[data-shop-favorite] button").click()')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "true"')
                self.assertTrue(MarketItemFavorite.objects.filter(user=user, mundane_item=mundane).exists())
                js('document.querySelector("[data-shop-favorites]").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                call('Page.reload')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "true"')
                js('document.querySelector("[data-shop-favorites]").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                js('document.querySelector("[data-shop-favorite] button").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "0"')
                self.assertFalse(MarketItemFavorite.objects.filter(user=user, mundane_item=mundane).exists())
                js('document.querySelector("[data-shop-favorites]").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "2"')
                wait_for('document.querySelector("[data-shop-detail]")?.textContent.includes("Corda de favorita")')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "false"')
                call('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 900,
                                                            'deviceScaleFactor': 1, 'mobile': False})
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_magicos')})
                wait_for('document.querySelector("[data-shop-favorite] button") !== null')
                self.assertEqual(js('document.querySelector("[data-shop-detail] img")?.getAttribute("src")'),
                                 '/static/assets/logo.png')
                js('document.querySelector("[data-shop-favorite] button").click()')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "true"')
                self.assertTrue(MarketItemFavorite.objects.filter(user=user, magic_item=magic).exists())
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
