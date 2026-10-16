"""Valida os espacos publicitarios com slots simulados, sem requisitar anuncios."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import override_settings
from django.urls import reverse


@override_settings(
    ADSENSE_ENABLED=True,
    ADSENSE_PUBLISHER_ID='ca-pub-test',
    ADSENSE_SIDEBAR_SLOT='1234567890',
    ADSENSE_HORIZONTAL_SLOT='0987654321',
)
class AdLayoutBrowserTests(StaticLiveServerTestCase):
    def test_simulated_slots_fit_desktop_and_mobile_and_login_has_none(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponivel.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponivel.')

        rendered_home = self.client.get(reverse('home'))
        self.assertContains(rendered_home, 'data-ad-slot="1234567890"')
        self.assertContains(rendered_home, 'data-ad-slot="0987654321"')

        with tempfile.TemporaryDirectory(prefix='bonfire-ads-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists(), 'Chrome nao abriu a porta de depuracao.')
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
                            return result

                def js(expression):
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })['result']
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(20):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}; pagina=' + str(js(
                        '({url: location.href, state: document.readyState, title: document.title, '
                        'ads: document.querySelectorAll("ins.adsbygoogle").length, '
                        'aside: document.querySelectorAll("aside").length, '
                        'body: document.body && document.body.innerText.slice(0, 150)})'
                    )))

                call('Network.enable')
                call('Network.setBlockedURLs', {'urls': [
                    '*googlesyndication.com*', '*doubleclick.net*',
                    '*googleads*', '*googletagservices.com*',
                ]})
                labels = (
                    'Publicidade lateral esquerda', 'Publicidade lateral direita',
                    'Publicidade acima do conte\u00fado', 'Publicidade ap\u00f3s o conte\u00fado',
                )
                for width in (360, 768, 1280, 1340, 1920):
                    with self.subTest(width=width):
                        call('Emulation.setDeviceMetricsOverride', {
                            'width': width, 'height': 800,
                            'deviceScaleFactor': 1, 'mobile': width <= 768,
                        })
                        call('Page.navigate', {'url': self.live_server_url + reverse('home')})
                        wait_for('document.querySelectorAll("ins.adsbygoogle").length === 4')
                        # Aguarda a folha responsiva antes de medir os breakpoints.
                        wait_for('document.styleSheets.length > 1')
                        areas = js('''(() => {
                            const labels = %s;
                            return labels.map(label => {
                                const node = [...document.querySelectorAll('aside')]
                                    .find(aside => aside.getAttribute('aria-label') === label);
                                return node && getComputedStyle(node).display !== 'none';
                            });
                        })()''' % json.dumps(labels))
                        self.assertEqual(areas, [width >= 1340, width >= 1340,
                                                 width < 1340, True])
                        self.assertLessEqual(js('document.documentElement.scrollWidth'), width)
                        self.assertEqual(js('document.querySelectorAll("ins.adsbygoogle").length'), 4)

                call('Page.navigate', {'url': self.live_server_url + reverse('login')})
                wait_for('!!document.querySelector("main")')
                self.assertEqual(js('document.querySelectorAll("ins.adsbygoogle").length'), 0)
                self.assertEqual(js('document.querySelectorAll("aside[aria-label^=Publicidade]").length'), 0)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
