"""Browser QA for recovering an editorial spell save."""

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

from home.models import TbMagia


class SpellEditorRecoveryTests(StaticLiveServerTestCase):
    def test_cancel_failure_retry_and_public_read_at_real_zoom(self):
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

        spell = TbMagia.objects.create(
            nome='Luz Editorial', slug='luz-editorial', nivel=0,
            descricao='Texto publicado',
        )
        editor = get_user_model().objects.create_superuser(
            'spell-editor', 'spell-editor@example.invalid', 'test-pass',
        )
        self.client.force_login(editor)
        with tempfile.TemporaryDirectory(prefix='bonfire-spell-editor-', ignore_cleanup_errors=True) as scratch:
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
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
                url = self.live_server_url + reverse('magias_listas')
                call('Page.navigate', {'url': url + '?magia=luz-editorial'})
                until('document.readyState==="complete" && !!document.querySelector("[data-spell-editor]")')
                self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                self.assertEqual(js('visualViewport.scale'), 1)
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))

                js('''window.qaDetails=document.querySelector('[data-spell-editor-container]');
                    window.qaForm=document.querySelector('[data-spell-editor]');
                    window.qaDetails.querySelector('summary').click();
                    window.qaForm.elements.descricao.value='Rascunho cancelado';
                    window.qaForm.elements.descricao.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));''')
                self.assertFalse(js('window.qaDetails.open'))
                self.assertEqual(js('window.qaForm.elements.descricao.value'), 'Texto publicado')
                self.assertTrue(js('document.activeElement===window.qaDetails.querySelector("summary")'))
                js('''window.qaDetails.querySelector('summary').click();
                    window.qaForm.elements.descricao.value='Outro rascunho';
                    window.qaForm.querySelector('[data-editor-cancel]').click();''')
                self.assertEqual(js('window.qaForm.elements.descricao.value'), 'Texto publicado')

                js('''window.qaDetails.querySelector('summary').click();
                    window.qaForm.elements.descricao.value='Texto revisado';
                    window.qaForm.elements.nome.value='Luz Revisada';
                    window.qaFetch=window.fetch;window.qaCalls=0;
                    window.fetch=()=>{window.qaCalls++;return new Promise(resolve=>window.qaResolve=resolve)};
                    window.qaForm.requestSubmit();''')
                until('window.qaForm.getAttribute("aria-busy")==="true"')
                js('window.qaForm.dispatchEvent(new Event("submit",{cancelable:true}))')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertTrue(js('window.qaForm.querySelector("[data-editor-cancel]").disabled'))
                js('window.qaDetails.querySelector("summary").click()')
                self.assertTrue(js('window.qaDetails.open'))
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}),{status:503,headers:{"Content-Type":"application/json"}}))')
                until('window.qaForm.getAttribute("aria-busy")!=="true"')
                self.assertIn('Falha temporaria', js('window.qaForm.querySelector("[data-editor-status]").textContent'))
                self.assertTrue(js('document.activeElement===window.qaForm.querySelector("[data-editor-status]")'))
                self.assertEqual(js('window.qaForm.elements.descricao.value'), 'Texto revisado')
                spell.refresh_from_db()
                self.assertEqual(spell.descricao, 'Texto publicado')
                js('''window.fetch=window.qaFetch;
                    window.qaForm.elements.slug.value='Slug invalido';
                    window.qaForm.requestSubmit();''')
                until('window.qaForm.querySelector("[data-editor-status]").textContent.includes("slug")')
                self.assertEqual(js('window.qaForm.querySelector("[data-editor-status]").getAttribute("role")'), 'alert')
                self.assertEqual(js('window.qaForm.elements.descricao.value'), 'Texto revisado')
                spell.refresh_from_db()
                self.assertEqual(spell.slug, 'luz-editorial')
                js('window.qaForm.elements.slug.value="luz-editorial";window.qaForm.requestSubmit()')
                until('new URLSearchParams(location.search).get("editado")==="1"')
                spell.refresh_from_db()
                self.assertEqual(spell.nome, 'Luz Revisada')
                self.assertEqual(spell.descricao, 'Texto revisado')
                until('document.querySelector("#mgDetail")?.textContent.includes("Texto revisado")')
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
