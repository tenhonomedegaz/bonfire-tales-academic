"""A master reviews the permanent MM slot before its existing debit and grant."""

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

from .models import MestreOuroDireito, TbCosmetico, TbTransacaoMestre, UserProfile


class CharacterSlotRedemptionBrowserTests(StaticLiveServerTestCase):
    def test_mobile_cancel_then_confirm_debits_once(self):
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

        user = get_user_model().objects.create_superuser('slot-review-master', 'slot@example.test', 'test')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.moedas_mestragem = 6000
        profile.save(update_fields=['moedas_mestragem'])
        for slug, kind in (('titulo-mestre-ouro', 'titulo'), ('moldura-mestre-ouro', 'moldura')):
            TbCosmetico.objects.get_or_create(slug=slug, defaults={
                'tipo': kind, 'nome': slug, 'raridade': 'lendario',
                'origem': 'mestre_ouro', 'escopo': 'perfil', 'ativo': True,
            })
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-slot-review-', ignore_cleanup_errors=True) as directory:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={directory}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(directory) / 'DevToolsActivePort'
                for _ in range(100):
                    if port_file.exists():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.exists())
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    page = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=15)
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        message = json.loads(ws.recv())
                        if message.get('id') == sequence:
                            self.assertNotIn('error', message, method)
                            return message['result']

                def js(expression):
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('character_slots')})
                for _ in range(100):
                    if js('document.readyState === "complete" && !!document.querySelector(".bs-acquire form")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('!!document.querySelector(".bs-acquire form")'))
                js('document.querySelector(".bs-acquire form button").click()')
                state = json.loads(js('''JSON.stringify((() => {
                    const dialog = document.querySelector('[data-slot-redemption-dialog]');
                    return {open: dialog.open, text: dialog.textContent,
                        width: dialog.getBoundingClientRect().width,
                        viewport: innerWidth, focused: dialog.contains(document.activeElement)};
                })())'''))
                self.assertTrue(state['open'], state)
                self.assertIn('5000 MM', state['text'])
                self.assertIn('6000 MM', state['text'])
                self.assertLessEqual(state['width'], state['viewport'])
                self.assertTrue(state['focused'], state)
                js('document.querySelector("[data-slot-redemption-cancel]").click()')
                self.assertFalse(js('document.querySelector("[data-slot-redemption-dialog]").open'))
                profile.refresh_from_db()
                self.assertEqual(profile.moedas_mestragem, 6000)
                self.assertFalse(MestreOuroDireito.objects.filter(user=user).exists())

                js('document.querySelector(".bs-acquire form button").click()')
                js('document.querySelector("[data-slot-redemption-confirm]").click()')
                for _ in range(100):
                    if MestreOuroDireito.objects.filter(user=user).exists():
                        break
                    time.sleep(.1)
                self.assertEqual(MestreOuroDireito.objects.filter(user=user).count(), 1)
                profile.refresh_from_db()
                self.assertEqual(profile.moedas_mestragem, 1000)
                self.assertEqual(TbTransacaoMestre.objects.filter(mestre=user, tipo='resgate', valor_mm=-5000).count(), 1)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
