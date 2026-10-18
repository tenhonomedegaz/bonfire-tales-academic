"""The mobile creator announces steps and keeps keyboard validation in place."""

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


class CreatorStepperBrowserTests(StaticLiveServerTestCase):
    def test_named_mobile_steps_and_keyboard_validation(self):
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
        user = get_user_model().objects.create_user('creator-stepper-owner')
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-creator-stepper-', ignore_cleanup_errors=True) as profile:
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

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800,
                    'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('criacao_ficha')})
                for _ in range(80):
                    if js('document.readyState === "complete" && document.querySelectorAll(".cf-step-tab").length === 6'):
                        break
                    time.sleep(.1)
                self.assertEqual(js('document.querySelectorAll(".cf-step-tab").length'), 6)
                state = json.loads(js('JSON.stringify({names:[...document.querySelectorAll(".cf-step-tab")].map(el=>el.getAttribute("aria-label")),current:[...document.querySelectorAll(".cf-step-tab[aria-current=step]")].map(el=>el.dataset.stepTab),labelVisible:getComputedStyle(document.querySelector(".cf-step-name")).display !== "none",firstVisible:!document.querySelectorAll(".cf-step")[0].hidden,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                self.assertEqual(state['names'], [
                    'Etapa 1: Atributos', 'Etapa 2: Raça', 'Etapa 3: Classe',
                    'Etapa 4: Antecedente', 'Etapa 5: Talentos', 'Etapa 6: Revisão',
                ])
                self.assertTrue(state['labelVisible'], state)
                self.assertEqual(state['current'], ['0'], state)
                self.assertTrue(state['firstVisible'], state)
                self.assertLessEqual(state['scroll'], state['client'], state)

                js('document.querySelectorAll(".cf-step-tab")[1].focus()')
                call('Input.dispatchKeyEvent', {
                    'type': 'keyDown', 'key': 'Enter', 'code': 'Enter',
                    'windowsVirtualKeyCode': 13,
                })
                call('Input.dispatchKeyEvent', {
                    'type': 'keyUp', 'key': 'Enter', 'code': 'Enter',
                    'windowsVirtualKeyCode': 13,
                })
                self.assertTrue(js('!document.querySelectorAll(".cf-step")[0].hidden'))
                self.assertTrue(js('!document.querySelectorAll("[data-step-err]")[0].hidden'))
                self.assertEqual(js('document.querySelector(".cf-step-tab[aria-current=step]")?.dataset.stepTab'), '0')

                # Complete the existing point-buy rule through its UI, then
                # advance with the same keyboard control.
                js('''(() => {
                    document.querySelector('#cf-nome').value = 'Teste de navegação';
                    const targets = [15, 14, 13, 12, 10, 8];
                    document.querySelectorAll('[data-point-buy] tr[data-attr]').forEach((row, i) => {
                        for (let score = 8; score < targets[i]; score++) {
                            row.querySelector('[data-inc]').click();
                        }
                        if (Number(row.querySelector('[data-score]').value) !== targets[i]) {
                            throw new Error('A compra de pontos não atingiu o alvo');
                        }
                    });
                    const asi = ['#cf-asi2', '#cf-asi1'];
                    asi.forEach((selector, i) => {
                        const select = document.querySelector(selector);
                        select.selectedIndex = i + 1;
                        select.dispatchEvent(new Event('change', {bubbles: true}));
                    });
                    return window.PointBuy.state().complete;
                })()''')
                self.assertTrue(js('window.PointBuy.state().complete'))
                js('document.querySelectorAll(".cf-step-tab")[1].focus()')
                call('Input.dispatchKeyEvent', {
                    'type': 'keyDown', 'key': 'Enter', 'code': 'Enter',
                    'windowsVirtualKeyCode': 13,
                })
                call('Input.dispatchKeyEvent', {
                    'type': 'keyUp', 'key': 'Enter', 'code': 'Enter',
                    'windowsVirtualKeyCode': 13,
                })
                self.assertEqual(js('document.querySelector(".cf-step-tab[aria-current=step]")?.dataset.stepTab'), '1')
                self.assertTrue(js('!document.querySelectorAll(".cf-step")[1].hidden'))
                self.assertTrue(js('document.querySelectorAll(".cf-step")[0].hidden'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
