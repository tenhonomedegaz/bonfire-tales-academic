"""Browser QA for author submission and retry of Chronicle drafts."""

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

from home.models import TbCronica


class ChronicleAuthorSubmissionTests(StaticLiveServerTestCase):
    def test_create_and_edit_recover_without_duplicate_pending_submission(self):
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

        author = get_user_model().objects.create_user('chronicle-author-qa', password='test-pass')
        published = TbCronica.objects.create(
            titulo='Publicada', slug='publicada-autor-qa', conteudo_markdown='Texto público',
            autor=author, status='aprovada',
        )
        self.client.force_login(author)
        with tempfile.TemporaryDirectory(prefix='bonfire-author-submit-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({
                'partition': {'default_zoom_level': {'x': math.log(2) / math.log(1.2)}}
            }), encoding='utf-8')
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
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

                for route, title, content, failure in (
                    (reverse('cronica_create'), 'Nova Crônica QA', 'Texto inicial QA', 'network'),
                    (reverse('cronica_edit', args=[published.slug]), 'Revisão QA', 'Texto revisto QA', 'server'),
                ):
                    with self.subTest(route=route):
                        call('Page.navigate', {'url': self.live_server_url + route})
                        until('document.readyState==="complete" && !!document.querySelector("#cronicaEditorForm [name=csrfmiddlewaretoken]")')
                        self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                        self.assertEqual(js('visualViewport.scale'), 1)
                        self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                        self.assertTrue(js('!!document.querySelector("#cronicaEditorForm [name=csrfmiddlewaretoken]").value'))
                        js('''(() => {
                            document.querySelector('#edTitulo').value=%s;
                            document.querySelector('#edMarkdown').value=%s;
                            window.qaFetch=window.fetch;
                            window.qaCalls=0;
                            window.fetch=()=>{window.qaCalls++;return new Promise((resolve,reject)=>{window.qaResolve=resolve;window.qaReject=reject})};
                            document.querySelector('#cronicaEditorForm').requestSubmit();
                        })()''' % (json.dumps(title), json.dumps(content)))
                        until('document.querySelector("#cronicaEditorForm").getAttribute("aria-busy")==="true"')
                        js('document.querySelector("#cronicaEditorForm").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))')
                        self.assertEqual(js('window.qaCalls'), 1)
                        self.assertTrue(js('document.querySelector(".editor-submit").disabled'))
                        if failure == 'network':
                            js('window.qaReject(new Error("Falha temporaria"))')
                        else:
                            js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}),{status:503,headers:{"Content-Type":"application/json"}}))')
                        until('document.querySelector("#edSubmitStatus").getAttribute("role")==="alert"')
                        self.assertIn('Falha temporaria', js('document.querySelector("#edSubmitStatus").textContent'))
                        self.assertTrue(js('document.activeElement===document.querySelector("#edSubmitStatus")'))
                        self.assertEqual(js('document.querySelector("#edMarkdown").value'), content)
                        self.assertFalse(js('document.querySelector(".editor-submit").disabled'))
                        self.assertFalse(js('document.querySelector("#cronicaEditorForm").getAttribute("aria-busy")==="true"'))
                        if failure == 'network':
                            self.assertFalse(TbCronica.objects.filter(titulo=title).exists())
                        else:
                            published.refresh_from_db()
                            self.assertEqual(published.conteudo_markdown, 'Texto público')
                            self.assertFalse(published.revisao_edicao)
                        js('window.fetch=window.qaFetch;document.querySelector("#cronicaEditorForm").requestSubmit()')
                        until('location.pathname==="%s"' % reverse('mundo_cronicas'))
                        if failure == 'network':
                            self.assertEqual(TbCronica.objects.filter(titulo=title, status='pendente').count(), 1)
                        else:
                            published.refresh_from_db()
                            self.assertEqual(published.conteudo_markdown, 'Texto público')
                            self.assertEqual(published.revisao_edicao['conteudo_markdown'], content)
                            self.assertEqual(published.revisao_edicao['estado'], 'pendente')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
