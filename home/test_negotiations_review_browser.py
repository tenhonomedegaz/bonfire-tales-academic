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

from .models import TbAnuncioItemMagico, TbPersonagem


class NegotiationReviewBrowserTests(StaticLiveServerTestCase):
    def test_buy_and_cancel_require_review_with_character_and_price(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome ou Edge indisponível.')

        buyer_user = get_user_model().objects.create_user('review-buyer')
        seller_user = get_user_model().objects.create_user('review-seller')
        buyer = TbPersonagem.objects.create(dono=buyer_user, nome='Comprador', carteira_pc=1000)
        recipient = TbPersonagem.objects.create(dono=buyer_user, nome='Destinatária', carteira_pc=900)
        seller = TbPersonagem.objects.create(dono=seller_user, nome='Vendedor')
        listing = TbAnuncioItemMagico.objects.create(vendedor=seller, nome='Espada de revisão', preco_pc=500)
        own_listing = TbAnuncioItemMagico.objects.create(vendedor=buyer, nome='Escudo de revisão', preco_pc=300)
        self.client.force_login(buyer_user)

        with tempfile.TemporaryDirectory(prefix='bonfire-negotiations-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
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

                def call(method, params):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('id') == sequence:
                            self.assertNotIn('error', result, method)
                            return result.get('result', {})

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

                call('Network.enable', {})
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mercado_comunidade')})
                wait_for(f'document.querySelector("#nt-offer-{listing.pk} .nt-buy-form") !== null')
                wait_for('document.querySelector("#nt-announcement").textContent.length > 0')
                js('''(() => { const search = document.querySelector('#nt-search');
                    search.value = 'espada'; search.dispatchEvent(new Event('input', {bubbles:true})); })()''')
                self.assertEqual(js('document.querySelector("#nt-count").textContent'), '1')
                self.assertFalse(js(f'document.querySelector("#nt-offer-{listing.pk}").hidden'))
                self.assertIn('q=espada', js('location.search'))
                js('''(() => { const search = document.querySelector('#nt-search');
                    search.value = 'sem resultado'; search.dispatchEvent(new Event('input', {bubbles:true})); })()''')
                self.assertFalse(js('document.querySelector("#nt-list-empty").hidden'))
                self.assertFalse(js('document.querySelector("#nt-reader-empty").hidden'))
                self.assertTrue(js(f'document.querySelector("#nt-offer-{listing.pk}").hidden'))
                js('document.querySelector(".nt-clear").click()')
                self.assertFalse(js(f'document.querySelector("#nt-offer-{listing.pk}").hidden'))
                js('document.querySelector("[data-nt-area=meus]").click()')
                self.assertFalse(js(f'document.querySelector("#nt-offer-{own_listing.pk}").hidden'))
                self.assertTrue(js(f'document.querySelector("#nt-offer-{listing.pk}").hidden'))
                self.assertIn('area=meus', js('location.search'))
                js('history.back()')
                wait_for('document.querySelector("[data-nt-area=venda]").getAttribute("aria-current") === "page"')
                self.assertFalse(js(f'document.querySelector("#nt-offer-{listing.pk}").hidden'))
                js('''window.reviewSubmits = [];
                    document.querySelectorAll('form[data-nt-review]').forEach(form => form.addEventListener('submit', event => {
                        window.reviewSubmits.push([form.dataset.ntReview, event.defaultPrevented]);
                        if (!event.defaultPrevented) event.preventDefault();
                    }));''')
                self.assertEqual(js(f'document.querySelector("#nt-offer-{listing.pk} .nt-buy-form").method'), 'post')
                self.assertTrue(js(f'!!document.querySelector("#nt-offer-{listing.pk} [name=csrfmiddlewaretoken]")'))
                js(f'document.querySelector("#nt-offer-{listing.pk} [name=comprador]").value = "{recipient.pk}"')
                js(f'document.querySelector("#nt-offer-{listing.pk} .nt-buy-form button").click()')
                wait_for('document.querySelector("#nt-review").open')
                self.assertIn('Espada de revisão', js('document.querySelector("#nt-review [data-nt-product]").textContent'))
                self.assertIn('Destinatária', js('document.querySelector("#nt-review [data-nt-character]").textContent'))
                self.assertTrue(js('document.querySelector("#nt-review [data-nt-price]").textContent.length > 0'))
                self.assertEqual(js('JSON.stringify(window.reviewSubmits)'), '[["buy",true]]')
                self.assertTrue(js('''(() => { const r = document.querySelector('#nt-review').getBoundingClientRect();
                    return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight; })()'''))
                js('document.querySelector(".nt-review-actions [data-nt-close]").click()')
                wait_for('!document.querySelector("#nt-review").open')
                wait_for(f'document.activeElement === document.querySelector("#nt-offer-{listing.pk} .nt-buy-form button")')
                js(f'document.querySelector("#nt-offer-{listing.pk} .nt-buy-form button").click()')
                wait_for('document.querySelector("#nt-review").open')
                js('document.querySelector("[data-nt-proceed]").click()')
                wait_for('window.reviewSubmits.length === 3')
                self.assertEqual(js('JSON.stringify(window.reviewSubmits)'), '[["buy",true],["buy",true],["buy",false]]')

                js('document.querySelector("[data-nt-area=meus]").click()')
                js(f'document.querySelector("#nt-offer-{own_listing.pk} .nt-cancel-form button").click()')
                wait_for('document.querySelector("#nt-review").open')
                self.assertIn('Escudo de revisão', js('document.querySelector("#nt-review [data-nt-product]").textContent'))
                self.assertIn('Comprador', js('document.querySelector("#nt-review [data-nt-character]").textContent'))
                self.assertTrue(js('document.querySelector("#nt-review [data-nt-price-row]").hidden'))
                js('document.querySelector("[data-nt-proceed]").click()')
                wait_for('window.reviewSubmits.length === 5')
                self.assertEqual(js('JSON.stringify(window.reviewSubmits.slice(-2))'), '[["cancel",true],["cancel",false]]')
                buyer.refresh_from_db()
                recipient.refresh_from_db()
                listing.refresh_from_db()
                own_listing.refresh_from_db()
                self.assertEqual(buyer.carteira_pc, 1000)
                self.assertEqual(recipient.carteira_pc, 900)
                self.assertEqual(listing.status, 'ativo')
                self.assertEqual(own_listing.status, 'ativo')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
