"""The shared checkout review stays usable without submitting a real payment."""

import base64
import hashlib
import hmac
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
from django.test import override_settings
from django.urls import reverse

from home.models import AsaasCheckoutOrder


@override_settings(BONFIRE_CHECKOUT_SIGNING_SECRET='review-browser-secret')
class CommerceReviewBrowserTests(StaticLiveServerTestCase):
    def test_review_account_cancel_and_confirm_without_checkout_request(self):
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
        user, _ = get_user_model().objects.get_or_create(
            username='checkout-review-owner',
            defaults={'email': 'checkout-review@example.test'},
        )
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-checkout-review-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Timed out waiting for {expression}')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('colaborador')})
                wait_for('document.readyState === "complete" && document.querySelector("form[data-purchase-review]") !== null')
                js('''(() => {
                    const form = document.querySelector('form[data-purchase-review]');
                    window.reviewSubmits = [];
                    form.addEventListener('submit', event => {
                        window.reviewSubmits.push(event.defaultPrevented);
                        if (!event.defaultPrevented) event.preventDefault();
                    });
                })()''')
                self.assertTrue(js('document.querySelector("form[data-purchase-review]").method === "post"'))
                self.assertTrue(js('document.querySelector("form[data-purchase-review]").target === "_blank"'))
                self.assertTrue(js('document.querySelector("form[data-purchase-review] [name=csrfmiddlewaretoken]") !== null'))
                self.assertTrue(js('document.querySelector("form[data-purchase-review] [name=product]") !== null'))

                js('document.querySelector("form[data-purchase-review] button").click()')
                wait_for('document.querySelector("#co-review").open')
                self.assertIn('checkout-review-owner', js('document.querySelector(".co-account-target").textContent'))
                self.assertTrue(js('document.querySelector("[data-co-product]").textContent.length > 0'))
                self.assertTrue(js('document.querySelector("[data-co-amount]").textContent.startsWith("R$")'))
                self.assertTrue(js('''(() => {
                    const r = document.querySelector('#co-review').getBoundingClientRect();
                    return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight;
                })()'''))
                self.assertTrue(js('document.querySelector("[data-co-proceed]").getBoundingClientRect().height >= 44'))
                js('document.querySelector(".co-dialog-actions [data-co-close]").click()')
                wait_for('!document.querySelector("#co-review").open')
                wait_for('document.activeElement === document.querySelector("form[data-purchase-review] button")')
                js('window.reviewSubmits = []; document.querySelector("form[data-purchase-review] button").click()')
                wait_for('document.querySelector("#co-review").open')
                js('document.querySelector("[data-co-proceed]").click()')
                wait_for('window.reviewSubmits.length === 2')
                self.assertEqual(js('JSON.stringify(window.reviewSubmits)'), '[true,false]')
                self.assertFalse(AsaasCheckoutOrder.objects.filter(user=user).exists())

                payload = {'discord_id': '987654321', 'discord_name': 'Discord Buyer',
                           'product': 'token-boost', 'mode': 'single',
                           'exp': int(time.time()) + 300}
                encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
                signature = base64.urlsafe_b64encode(hmac.new(
                    b'review-browser-secret', encoded.encode(), hashlib.sha256).digest()
                ).decode().rstrip('=')
                token = encoded + '.' + signature
                call('Page.navigate', {'url': self.live_server_url + reverse('colaborador_discord_checkout') + '?token=' + token})
                wait_for('document.readyState === "complete" && document.querySelector("form[data-purchase-review]") !== null')
                js('''(() => {
                    window.reviewSubmits = [];
                    document.querySelector('form[data-purchase-review]').addEventListener('submit', event => {
                        window.reviewSubmits.push(event.defaultPrevented);
                        if (!event.defaultPrevented) event.preventDefault();
                    });
                })()''')
                js('document.querySelector("form[data-purchase-review] button").click()')
                wait_for('document.querySelector("#co-review").open')
                self.assertIn('Discord Buyer (ID 987654321)', js('document.querySelector("[data-co-account-target]").textContent'))
                self.assertIn('Discord que receberá a compra', js('document.querySelector("[data-co-account-label]").textContent'))
                self.assertFalse(js('document.querySelector("[data-co-account-target]").hidden'))
                self.assertEqual(js('window.reviewSubmits.length'), 1)
                js('document.querySelector(".co-dialog-actions [data-co-close]").click()')
                self.assertEqual(js('window.reviewSubmits.length'), 1)
                js('document.querySelector("form[data-purchase-review] button").click()')
                wait_for('document.querySelector("#co-review").open')
                js('document.querySelector("[data-co-proceed]").click()')
                wait_for('window.reviewSubmits.length === 3')
                self.assertEqual(js('JSON.stringify(window.reviewSubmits)'), '[true,true,false]')
                self.assertFalse(AsaasCheckoutOrder.objects.exists())
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
