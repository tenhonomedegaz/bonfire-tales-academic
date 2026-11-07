"""Presentation of API-backed options embedded in editorial Markdown."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbOpcaojogo


class EmbeddedOptionsMarkdownTests(StaticLiveServerTestCase):
    def test_detail_renders_safe_markdown_and_escaped_fallback_at_360px(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome or Edge unavailable.')

        description = (
            '**Destaque** <img src=x onerror=alert(1)> '
            '[perigo](javascript:alert(1)) [referencia](https://example.org)'
        )
        TbOpcaojogo.objects.create(
            nome='Opcao Editorial', slug='opcao-editorial', tipo='Estilo de Luta',
            descricao=description,
        )
        api_response = self.client.get(reverse('api_opcoes'), {'tipo': 'Estilo de Luta'})
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()['opcoes'][0]['descricao'], description)

        with tempfile.TemporaryDirectory(prefix='bonfire-embedded-option-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists(), 'Chrome did not start.')
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
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Timed out: {expression}')

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('home')})
                wait_for('typeof window.bonfireOptionsWidget?.hydrate === "function"')
                js('''(() => {
                    const widget = document.createElement('div');
                    widget.className = 'bonfire-options-widget';
                    widget.dataset.tipo = 'Estilo de Luta';
                    document.querySelector('main').appendChild(widget);
                    window.bonfireOptionsWidget.hydrate();
                })()''')
                wait_for('document.querySelector(".bonfire-options-item") !== null')
                js('document.querySelector(".bonfire-options-item").click()')
                wait_for('document.querySelector(".bonfire-options-detail-panel strong") !== null')
                self.assertEqual(js('document.querySelectorAll(".bonfire-options-detail-panel img[onerror], .bonfire-options-detail-panel a[href^=javascript], .bonfire-options-detail-panel script").length'), 0)
                self.assertEqual(js('document.querySelectorAll(".bonfire-options-detail-panel a[href=\\"https://example.org\\"]").length'), 1)
                js('window.renderBonfireMarkdown = undefined; document.querySelector(".bonfire-options-item").click()')
                self.assertEqual(js('document.querySelectorAll(".bonfire-options-detail-panel img, .bonfire-options-detail-panel a, .bonfire-options-detail-panel script").length'), 0)
                self.assertTrue(js('document.querySelector(".bonfire-options-detail-panel").textContent.includes("<img src=x")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
