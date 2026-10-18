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
            nome='Corda de favorita 30 pés', slug='corda-browser', preco='1 PO',
            imagem_url='//external.example/item.svg')
        mundane_other = TbItemMundano.objects.create(nome='Tocha comum', slug='tocha-browser', preco='1 PC')
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
                for _ in range(150):
                    if port_file.exists() or process.poll() is not None:
                        break
                    time.sleep(.2)
                self.assertTrue(port_file.exists())
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
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
                    for _ in range(150):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}; estado=' + str(js('JSON.stringify({url:location.href,ready:document.readyState,initialized:document.querySelector("[data-shop-root]")?.dataset.shopInit,count:document.querySelector("[data-shop-count]")?.textContent,selected:document.querySelector("[data-mkt-row].is-selected")?.dataset.target})')))

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
                self.assertIn('9 metros [30 pés]', js('document.querySelector("[data-mkt-row]").textContent'))
                js('document.querySelector("[data-shop-search]").value = "9 metros"; '
                   'document.querySelector("[data-shop-search]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                self.assertTrue(js('document.querySelector("[data-mkt-row]").closest("li").hidden === false'))
                self.assertTrue(js('document.querySelector(".mkt-count").getAttribute("role") === "status"'))
                js('document.querySelector("[data-shop-search]").value = "carteira da ficha"; '
                   'document.querySelector("[data-shop-search]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                self.assertTrue(js('document.querySelector("[data-mkt-row][data-target=guide-economia]").closest("li").hidden === false'))
                self.assertTrue(js('document.querySelector("[data-mkt-row][data-target=guide-sobre]").closest("li").hidden === true'))
                js('document.querySelector("[data-mkt-row][data-target=guide-economia]").click()')
                wait_for('document.querySelector("[data-shop-detail]")?.textContent.includes("carteira da ficha")')
                self.assertFalse(js('document.querySelector("[data-shop-detail] form[data-shop-buy]") !== null'))
                js('document.querySelector("[data-shop-search]").value = ""; '
                   'document.querySelector("[data-shop-search]").dispatchEvent(new Event("input", {bubbles:true}))')
                js(f'document.querySelector(\'[data-mkt-row][data-target="mu-{mundane.pk}"]\').click()')
                self.assertTrue(js('document.querySelector("[data-shop-detail] .mkt-sigil-letter") !== null'))
                self.assertFalse(js('document.querySelector("[data-shop-detail] img") !== null'))
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
                js(f'document.querySelector(\'[data-mkt-row][data-target="mu-{mundane_other.pk}"]\').click()')
                self.assertEqual(js('new URL(location.href).searchParams.get("item")'),
                                 f'mu-{mundane_other.pk}')
                call('Page.reload')
                wait_for(f'document.querySelector(\'[data-mkt-row][data-target="mu-{mundane_other.pk}"]\')?.classList.contains("is-selected")')
                js('history.back()')
                wait_for('document.querySelector("[data-shop-detail]")?.textContent.includes("Corda de favorita")')
                js('document.querySelector("[data-shop-favorite] button").click()')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "true"')
                self.assertTrue(MarketItemFavorite.objects.filter(user=user, mundane_item=mundane).exists())
                js('document.querySelector("[data-shop-favorites]").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                self.assertTrue(js('location.search.includes("favoritos=1")'))
                call('Page.reload')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "true"')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                self.assertTrue(js('document.querySelector("[data-shop-favorites]").checked'))
                js('history.back()')
                wait_for('document.querySelector("[data-shop-favorites]")?.checked === false')
                self.assertEqual(js('document.querySelector("[data-shop-count]")?.textContent'), '4')
                js('history.forward()')
                wait_for('document.querySelector("[data-shop-favorites]")?.checked === true')
                self.assertEqual(js('document.querySelector("[data-shop-count]")?.textContent'), '1')
                js('document.querySelector("[data-shop-favorite] button").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "0"')
                self.assertFalse(MarketItemFavorite.objects.filter(user=user, mundane_item=mundane).exists())
                js('document.querySelector("[data-shop-favorites]").click()')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "4"')
                wait_for('document.querySelector("[data-shop-detail]")?.textContent.includes("Corda de favorita")')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "false"')
                call('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 900,
                                                            'deviceScaleFactor': 1, 'mobile': False})
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_magicos')})
                wait_for('document.querySelector("[data-shop-stock]") !== null')
                js('document.querySelector("[data-shop-stock]").value = "catalogo"; '
                   'document.querySelector("[data-shop-stock]").dispatchEvent(new Event("change", {bubbles:true}))')
                wait_for('document.querySelector("[data-shop-favorite] button") !== null')
                self.assertEqual(js('document.querySelector("[data-shop-detail] img")?.getAttribute("src")'),
                                 '/static/assets/logo.png')
                js('document.querySelector("[data-shop-favorite] button").click()')
                wait_for('document.querySelector("[data-shop-favorite] button")?.getAttribute("aria-pressed") === "true"')
                self.assertTrue(MarketItemFavorite.objects.filter(user=user, magic_item=magic).exists())
                js('document.querySelector("[data-shop-search]").value = "Anel"; '
                   'document.querySelector("[data-shop-search]").dispatchEvent(new Event("input", {bubbles:true}))')
                js('document.querySelector("[data-shop-search]").value = "Anel de favorita"; '
                   'document.querySelector("[data-shop-search]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "1"')
                self.assertTrue(js('new URL(location.href).searchParams.get("busca") === "Anel de favorita"'))
                js('history.back()')
                wait_for('document.querySelector("[data-shop-search]")?.value === ""')
                self.assertFalse(js('new URL(location.href).searchParams.has("busca")'))
                js('history.forward()')
                wait_for('document.querySelector("[data-shop-search]")?.value === "Anel de favorita"')
                js('document.querySelector("[data-shop-sort]").value = "preco-desc"; '
                   'document.querySelector("[data-shop-sort]").dispatchEvent(new Event("change", {bubbles:true}))')
                self.assertTrue(js('new URL(location.href).searchParams.get("ordem") === "preco-desc"'))
                call('Page.reload')
                wait_for('document.querySelector("[data-shop-sort]")?.value === "preco-desc"')
                self.assertEqual(js('document.querySelector("[data-shop-search]")?.value'), 'Anel de favorita')
                self.assertEqual(js('document.querySelector("[data-shop-count]")?.textContent'), '1')
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
