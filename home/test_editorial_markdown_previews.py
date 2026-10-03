"""Browser QA for the two editorial Markdown preview entry points."""

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


class EditorialMarkdownPreviewTests(StaticLiveServerTestCase):
    def test_admin_and_chronicle_previews_sanitize_and_fall_back_to_text(self):
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

        editor = get_user_model().objects.create_superuser(
            'editor-preview-qa', 'editor-preview-qa@example.invalid', 'test-pass',
        )
        self.client.force_login(editor)
        with tempfile.TemporaryDirectory(prefix='bonfire-editorial-preview-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
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
                        response = json.loads(ws.recv())
                        if response.get('id') == sequence:
                            self.assertNotIn('error', response, method)
                            return response['result']

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def until(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.enable')
                for route, textarea, preview in (
                    ('admin:markdown_editor', '#markdownEditor', '#markdownPreview'),
                    ('cronica_create', '#edMarkdown', '#edPreview'),
                ):
                    with self.subTest(route=route):
                        call('Page.navigate', {'url': self.live_server_url + reverse(route)})
                        until(f'document.readyState==="complete" && !!document.querySelector("{textarea}")')
                        self.assertTrue(js('typeof renderBonfireMarkdownElement==="function"'))
                        payload = (
                            '**Seguro** <img src="x" onerror="window.__previewInjected=1"> '
                            '<svg onload="window.__previewInjected=1"></svg> '
                            '[ruim](javascript:alert(1)) [bom](https://example.org)'
                        )
                        js('''(() => {
                            const input=document.querySelector(%s);
                            input.value=%s;
                            input.dispatchEvent(new Event('input',{bubbles:true}));
                        })()''' % (json.dumps(textarea), json.dumps(payload)))
                        self.assertTrue(js(f'!!document.querySelector("{preview} strong")'))
                        self.assertTrue(js(f'!!Array.from(document.querySelectorAll("{preview} a")).find(a=>a.href==="https://example.org/")'))
                        self.assertFalse(js(f'!!document.querySelector("{preview} [onerror], {preview} svg, {preview} a[href^=javascript]")'))
                        self.assertFalse(js('window.__previewInjected===1'))
                        js('''window.renderBonfireMarkdownElement=undefined;
                            document.querySelector(%s).dispatchEvent(new Event('input',{bubbles:true}));''' % json.dumps(textarea))
                        self.assertTrue(js(f'document.querySelector("{preview}").textContent.includes("**Seguro**")'))
                        self.assertFalse(js(f'!!document.querySelector("{preview} strong, {preview} img")'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
