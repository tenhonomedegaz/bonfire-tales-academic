"""Browser QA for the inline Talents editor and its public detail."""

import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import TbTalento
from home.views import SiteDataUnavailable


class TalentInlineEditorTests(StaticLiveServerTestCase):
    def test_cancel_failure_retry_and_public_detail_at_real_zoom(self):
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

        talent = TbTalento.objects.create(
            nome='Talento Editorial', slug='talento-editorial', tipo='geral',
            etiqueta='combate', descricao='Texto publicado',
        )
        editor = get_user_model().objects.create_superuser('talent-editor', 'talent@example.invalid', 'pass')
        self.client.force_login(editor)
        with patch('home.views._site_docs', side_effect=SiteDataUnavailable):
            # The live server thread uses the same test DB; the fallback route is exercised there too.
            with tempfile.TemporaryDirectory(prefix='bonfire-talent-editor-', ignore_cleanup_errors=True) as scratch:
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
                        if port_file.is_file():
                            break
                        time.sleep(.1)
                    self.assertTrue(port_file.is_file())
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
                    call('Page.navigate', {'url': self.live_server_url + reverse('jogador_talentos')})
                    until('document.readyState === "complete" && !!document.querySelector(".wiki-edit-button")')
                    metrics = json.loads(js('JSON.stringify({dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                    self.assertAlmostEqual(metrics['dpr'], 2, delta=.05, msg=metrics)
                    self.assertEqual(metrics['scale'], 1, metrics)
                    self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                    self.assertIn('Texto publicado', js('document.querySelector("[data-talent-preview]").textContent'))

                    js('document.querySelector(".wiki-edit-button").click()')
                    self.assertEqual(js('document.activeElement.name'), 'nome')
                    js('''{let field=document.querySelector('[name=descricao]');field.value='Rascunho';field.dispatchEvent(new Event('input'));field.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));}''')
                    self.assertFalse(js('!!document.querySelector("[data-talent-edit-form]")'))
                    self.assertIn('Texto publicado', js('document.querySelector("[data-talent-preview]").textContent'))
                    self.assertEqual(js('document.activeElement.className'), 'wiki-edit-button')
                    js('''{document.querySelector('.wiki-edit-button').click();
                        let field=document.querySelector('[name=descricao]');field.value='Outro rascunho';
                        field.dispatchEvent(new Event('input'));
                        document.querySelector('.wiki-cancel').click();}''')
                    self.assertFalse(js('!!document.querySelector("[data-talent-edit-form]")'))
                    self.assertIn('Texto publicado', js('document.querySelector("[data-talent-preview]").textContent'))
                    self.assertEqual(js('document.activeElement.className'), 'wiki-edit-button')

                    js('''{document.querySelector('.wiki-edit-button').click();
                        let field=document.querySelector('[name=descricao]');field.value='Texto revisado';field.dispatchEvent(new Event('input'));
                        document.querySelector('[name=atrib_forca]').checked=true;
                        window.qaFetch=window.fetch;window.qaCalls=0;
                        window.fetch=()=>{window.qaCalls++;return new Promise(resolve=>window.qaResolve=resolve)};
                        document.querySelector('[data-talent-edit-form]').requestSubmit();}''')
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                    until('document.querySelector(".wiki-save").disabled')
                    js('document.querySelector("[data-talent-edit-form]").dispatchEvent(new Event("submit",{cancelable:true}))')
                    self.assertEqual(js('window.qaCalls'), 1)
                    self.assertEqual(js('document.querySelector("[data-talent-edit-form]").getAttribute("aria-busy")'), 'true')
                    js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}),{status:503,headers:{"Content-Type":"application/json"}}))')
                    until('!document.querySelector(".wiki-save").disabled')
                    self.assertIn('Falha temporaria', js('document.querySelector(".wiki-save-error").textContent'))
                    self.assertEqual(js('document.activeElement.className'), 'wiki-save-error')
                    self.assertEqual(js('document.querySelector("[name=descricao]").value'), 'Texto revisado')
                    self.assertTrue(js('document.querySelector("[name=atrib_forca]").checked'))
                    talent.refresh_from_db()
                    self.assertEqual(talent.descricao, 'Texto publicado')
                    self.assertFalse(talent.atrib_forca)

                    js('window.fetch=window.qaFetch;document.querySelector("[data-talent-edit-form]").requestSubmit()')
                    until('!document.querySelector("[data-talent-edit-form]") && document.querySelector("[data-talent-preview]")?.textContent.includes("Texto revisado")')
                    talent.refresh_from_db()
                    self.assertEqual(talent.descricao, 'Texto revisado')
                    self.assertTrue(talent.atrib_forca)
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                    call('Page.reload')
                    until('document.readyState === "complete" && document.querySelector("[data-talent-preview]")?.textContent.includes("Texto revisado")')
                finally:
                    if ws:
                        ws.close()
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
