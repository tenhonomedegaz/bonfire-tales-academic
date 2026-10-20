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

from .models import TbItemMagico, TbItemMundano, TbPersonagem, TbPersonagemItem


class MercadoCharacterSwitchBrowserTests(StaticLiveServerTestCase):
    def test_character_switch_preserves_browse_state_and_retargets_trade(self):
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

        user = get_user_model().objects.create_user('market-switch-user')
        first = TbPersonagem.objects.create(dono=user, nome='Aventureiro A', carteira_pc=1000)
        second = TbPersonagem.objects.create(dono=user, nome='Aventureiro B', carteira_pc=2000)
        item = TbItemMundano.objects.create(nome='Corda de Teste', slug='corda-de-teste', preco='1 PO')
        magic = TbItemMagico.objects.create(nome='Anel de Teste', slug='anel-de-teste', preco=1, loja='Joalheria')
        no_price = TbItemMagico.objects.create(nome='Relíquia de Missão', slug='reliquia-de-missao', preco=0, loja='Joalheria')
        TbPersonagemItem.objects.create(id_personagem=first, nome=item.nome, custo='1 PO')
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-market-switch-', ignore_cleanup_errors=True) as profile:
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
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_mundanos')})
                wait_for('document.querySelector("[data-shop-buy]") !== null')
                js('window.__marketMarker = 42')
                first_sheet = reverse('ficha_detail', args=[first.pk]) + '?aba=mochila'
                second_sheet = reverse('ficha_detail', args=[second.pk]) + '?aba=mochila'
                self.assertTrue(js(f'document.querySelector("[data-market-sheet-link]").href.endsWith({json.dumps(first_sheet)})'))
                js('document.querySelector("[data-shop-search]").value = "corda"; document.querySelector("[data-shop-search]").dispatchEvent(new Event("input"))')
                wait_for('document.querySelector("[data-shop-count]").textContent === "1"')
                js('window.__marketFetch = window.fetch; window.fetch = () => Promise.reject(new Error("offline"))')
                js(f'document.querySelector("[data-shop-personagem]").value = "{second.pk}"; document.querySelector("[data-shop-personagem]").dispatchEvent(new Event("change"))')
                self.assertTrue(js(f'document.querySelector("[data-market-sheet-link]").href.endsWith({json.dumps(first_sheet)})'))
                wait_for('document.querySelector("[data-shop-feedback]")?.textContent.includes("Não foi possível trocar")')
                self.assertTrue(js(f'document.querySelector("[data-market-sheet-link]").href.endsWith({json.dumps(first_sheet)})'))
                js('window.fetch = window.__marketFetch')
                js(f'document.querySelector("[data-shop-personagem]").value = "{second.pk}"; document.querySelector("[data-shop-personagem]").dispatchEvent(new Event("change"))')
                wait_for(f'document.querySelector("[data-shop-personagem]").value === "{second.pk}" && document.querySelector("[data-shop-buy]")?.action.endsWith("/{second.pk}/comprar/")')
                self.assertTrue(js(f'document.querySelector("[data-market-sheet-link]").href.endsWith({json.dumps(second_sheet)})'))
                self.assertEqual(js('window.__marketMarker'), 42)
                self.assertEqual(js('document.querySelector("[data-shop-search]").value'), 'corda')
                self.assertEqual(js('document.querySelector("[data-shop-count]").textContent'), '1')
                self.assertTrue(js('location.search.includes("personagem=")'))
                self.assertEqual(js('document.querySelectorAll("[data-shop-venda] [data-mkt-row]").length'), 0)
                self.assertTrue(js('document.querySelector("[data-shop-carteira]").textContent.includes("20 PO")'))
                js('document.querySelector("[data-shop-picker] button[type=submit]").click()')
                self.assertEqual(js('window.__marketMarker'), 42)
                js('document.querySelector("[data-shop-buy] button[type=submit]").click()')
                wait_for('document.querySelector("[data-shop-review]").open')
                self.assertIn(second.nome, js('document.querySelector("[data-shop-review-character]").textContent'))
                self.assertIn(item.nome, js('document.querySelector("[data-shop-review-item]").textContent'))
                js('document.querySelector("[data-shop-review-confirm]").click()')
                wait_for('document.querySelector("[data-shop-feedback]")?.textContent.includes("Comprado:")')
                self.assertTrue(js('document.querySelector("[data-shop-carteira]").textContent.includes("19 PO")'))
                second.refresh_from_db()
                first.refresh_from_db()
                self.assertEqual(second.carteira_pc, 1900)
                self.assertEqual(first.carteira_pc, 1000)
                self.assertTrue(TbPersonagemItem.objects.filter(id_personagem=second, nome=item.nome).exists())
                js('history.back()')
                wait_for(f'document.querySelector("[data-shop-personagem]").value === "{first.pk}" && document.querySelector("[data-shop-buy]")?.action.endsWith("/{first.pk}/comprar/")')
                self.assertTrue(js(f'document.querySelector("[data-market-sheet-link]").href.endsWith({json.dumps(first_sheet)})'))
                self.assertEqual(js('window.__marketMarker'), 42)
                self.assertEqual(js('document.querySelector("[data-shop-search]").value'), 'corda')
                self.assertEqual(js('document.querySelectorAll("[data-shop-venda] [data-mkt-row]").length'), 1)
                call('Emulation.setDeviceMetricsOverride', {'width': 360, 'height': 800,
                                                            'deviceScaleFactor': 1, 'mobile': True})
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_itens_magicos')})
                wait_for('document.querySelector("[data-shop-personagem]") !== null')
                wait_for('document.querySelector("[data-shop-buy]") !== null')
                self.assertTrue(js('document.querySelector("[data-magic-shop=joalheria]") !== null'))
                self.assertEqual(js('document.querySelector("[data-shop-count]").textContent'), '1')
                js('window.__magicMarker = 21')
                js(f'document.querySelector("[data-shop-personagem]").value = "{second.pk}"; document.querySelector("[data-shop-personagem]").dispatchEvent(new Event("change"))')
                wait_for(f'document.querySelector("[data-market-sheet-link]")?.href.endsWith({json.dumps(second_sheet)})')
                self.assertTrue(js(f'document.querySelector("[data-market-sheet-link]").href.endsWith({json.dumps(second_sheet)})'))
                self.assertEqual(js('window.__magicMarker'), 21)
                self.assertTrue(js('document.querySelector("[data-shop-carteira]").textContent.includes("19 PO")'))
                self.assertTrue(js(f'document.querySelector("[data-shop-buy]")?.action.endsWith("/{second.pk}/comprar-magico/")'))
                self.assertFalse(js('document.querySelector("[data-shop-buy] [name=qtd]") !== null'))
                js(f'document.querySelector(\'[data-mkt-row][data-target="mi-{magic.pk}"]\').click()')
                wait_for('document.querySelector("[data-shop-root]")?.classList.contains("is-sheet-open")')
                self.assertTrue(js('document.querySelector("[data-shop-buy] button[type=submit]").getClientRects().length > 0'))
                js('document.querySelector("[data-shop-buy] button[type=submit]").click()')
                wait_for('document.querySelector("[data-shop-review]").open')
                self.assertIn(second.nome, js('document.querySelector("[data-shop-review-character]").textContent'))
                self.assertIn(magic.nome, js('document.querySelector("[data-shop-review-item]").textContent'))
                js('document.querySelector("[data-shop-review-confirm]").click()')
                wait_for('document.querySelector("[data-shop-feedback]")?.textContent.includes("Comprado:")')
                second.refresh_from_db()
                self.assertEqual(second.carteira_pc, 1800)
                self.assertTrue(TbPersonagemItem.objects.filter(id_personagem=second, id_item_magico=magic).exists())
                js('document.querySelector(".mkt-sheet-close").click()')
                js('document.querySelector("[data-shop-stock]").value = "catalogo"; document.querySelector("[data-shop-stock]").dispatchEvent(new Event("change", {bubbles:true}))')
                wait_for('document.querySelector("[data-shop-count]")?.textContent === "2"')
                js(f'document.querySelector(\'[data-mkt-row][data-target="mi-{no_price.pk}"]\').click()')
                self.assertFalse(js('document.querySelector("[data-shop-detail] [data-shop-buy]") !== null'))
                self.assertFalse(TbPersonagemItem.objects.filter(id_personagem=second, id_item_magico=no_price).exists())
                self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
