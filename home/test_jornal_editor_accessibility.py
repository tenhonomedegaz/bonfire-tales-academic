"""Focused browser QA for the Jornal editor at real 200% zoom."""

import json
import math
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

from home.models import TbJornal


class JornalEditorAccessibilityTests(StaticLiveServerTestCase):
    def test_zoom_keyboard_failure_retry_and_public_article(self):
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
            'jornal-accessibility-editor', 'editor@example.invalid', 'test-pass',
        )
        self.client.force_login(editor)
        with tempfile.TemporaryDirectory(prefix='bonfire-jornal-a11y-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({'partition': {
                'default_zoom_level': {'x': math.log(2) / math.log(1.2)},
            }}), encoding='utf-8')
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-first-run', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=800,900', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
                for _ in range(80):
                    try:
                        port = port_file.read_text(encoding='utf-8').splitlines()[0]
                        break
                    except (FileNotFoundError, PermissionError, IndexError):
                        pass
                    time.sleep(.1)
                else:
                    self.fail('Chrome nao iniciou.')
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True, 'awaitPromise': True,
                    })
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
                call('Page.navigate', {'url': self.live_server_url + reverse('jornal_create')})
                until('document.readyState === "complete" && !!document.querySelector("#edMarkdown")')
                metrics = json.loads(js('JSON.stringify({outer:outerWidth,dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                self.assertEqual(metrics['outer'], 800, metrics)
                self.assertAlmostEqual(metrics['dpr'], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics['scale'], 1, metrics)
                self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                self.assertTrue(js('document.querySelector("label[for=edMarkdown]").control === document.querySelector("#edMarkdown")'))
                self.assertEqual(js('document.querySelector("[data-wrap=bold]").getAttribute("aria-label")'), 'Negrito')
                js('document.querySelector(".editor-toolbar [data-prefix]:last-of-type").focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                self.assertEqual(js('document.activeElement.id'), 'edMarkdown')
                self.assertEqual(js('getComputedStyle(document.querySelector("#edMarkdown")).outlineStyle'), 'solid')
                call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
                self.assertEqual(js('getComputedStyle(document.querySelector(".editor-submit")).transitionDuration'), '0s')

                js('''document.querySelector('#edTitulo').value = 'Jornal Acessivel';
                    document.querySelector('#edMarkdown').value = '**Texto** de QA';
                    document.querySelector('#edMarkdown').dispatchEvent(new Event('input', {bubbles:true}));
                    window.qaFetch = window.fetch; window.qaCalls = 0;
                    window.fetch = () => { window.qaCalls++; return new Promise(resolve => { window.qaResolve = resolve; }); };
                    document.querySelector('#jornalEditorForm').requestSubmit();''')
                until('document.querySelector(".editor-submit").disabled')
                js('document.querySelector("#jornalEditorForm").dispatchEvent(new Event("submit", {cancelable:true}))')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertEqual(js('document.querySelector("#jornalEditorForm").getAttribute("aria-busy")'), 'true')
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}), {status:503,headers:{"Content-Type":"application/json"}}))')
                until('!document.querySelector(".editor-submit").disabled')
                self.assertIn('Falha temporaria', js('document.querySelector("#editorSaveError").textContent'))
                self.assertEqual(js('document.activeElement.id'), 'editorSaveError')
                self.assertEqual(js('document.querySelector("#edMarkdown").value'), '**Texto** de QA')
                self.assertFalse(TbJornal.objects.filter(slug='jornal-acessivel').exists())

                js('window.fetch = window.qaFetch; document.querySelector("#jornalEditorForm").requestSubmit()')
                until('location.pathname === "/mundo/jornal/jornal-acessivel/" && document.querySelector(".artigo-title")?.textContent === "Jornal Acessivel"')
                article = TbJornal.objects.get(slug='jornal-acessivel')
                self.assertEqual(article.conteudo_markdown, '**Texto** de QA')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
