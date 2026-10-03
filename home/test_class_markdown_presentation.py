"""Leitura e previa inline de habilidades na pagina de classe."""

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

from .models import TbClasse, TbClassehabilidade


class ClassMarkdownPresentationTests(StaticLiveServerTestCase):
    def test_feature_and_editor_preview_sanitize_markdown_on_mobile(self):
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

        description = (
            '**Destaque** <img src=x onerror=alert(1)> '
            '[perigo](javascript:alert(1)) [referencia](https://example.org)'
        )
        classe = TbClasse.objects.create(nome='Classe de Teste', slug='classe-de-teste')
        TbClassehabilidade.objects.create(
            id_classe=classe, nome='Habilidade Editorial', niveladquirido=1,
            descricao=description,
        )
        editor = get_user_model().objects.create_superuser(
            'class-editor', 'class-editor@example.invalid', 'test-pass',
        )
        self.client.force_login(editor)

        with tempfile.TemporaryDirectory(prefix='bonfire-class-md-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists(), 'Chrome nao iniciou.')
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
                    self.fail(f'Tempo esgotado: {expression}')

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                url = self.live_server_url + reverse('classe_detail', args=[classe.slug])
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-feature-card] [data-markdown] strong") !== null')
                self.assertEqual(js('document.querySelectorAll("[data-markdown] img[onerror], [data-markdown] a[href^=javascript], [data-markdown] script").length'), 0)
                self.assertEqual(js('document.querySelectorAll("[data-markdown] a[href=\\"https://example.org\\"]").length'), 1)

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-feature-edit]") !== null')
                js('document.querySelector("[data-feature-edit]").click()')
                js('''(() => {
                    const textarea = document.querySelector('[data-feature-form] textarea[name=descricao]');
                    textarea.value = %s;
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                })()''' % json.dumps(description))
                self.assertEqual(js('document.querySelectorAll("[data-markdown] img[onerror], [data-markdown] a[href^=javascript], [data-markdown] script").length'), 0)
                self.assertEqual(js('document.querySelectorAll("[data-markdown] strong, [data-markdown] a[href=\\"https://example.org\\"]").length'), 2)
                js('window.renderBonfireMarkdown = undefined; document.querySelector("[data-feature-form] textarea[name=descricao]").dispatchEvent(new Event("input", {bubbles:true}))')
                self.assertEqual(js('document.querySelectorAll("[data-markdown] img, [data-markdown] a, [data-markdown] script").length'), 0)
                self.assertTrue(js('document.querySelector("[data-markdown]").textContent.includes("<img src=x")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
