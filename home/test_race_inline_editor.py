"""Browser QA for the inline race editor, recovery and public detail."""

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

from home.models import TbRaca


class RaceInlineEditorTests(StaticLiveServerTestCase):
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

        race = TbRaca.objects.create(
            nome='Povo Editorial', slug='povo-editorial', lore_presentation='Texto publicado',
        )
        editor = get_user_model().objects.create_superuser('race-editor', 'race@example.invalid', 'pass')
        self.client.force_login(editor)
        with tempfile.TemporaryDirectory(prefix='bonfire-race-editor-', ignore_cleanup_errors=True) as scratch:
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
                call('Page.navigate', {'url': self.live_server_url + reverse('raca_detail', args=[race.slug])})
                until('document.readyState === "complete" && !!document.querySelector("[data-race-edit]")')
                metrics = json.loads(js('JSON.stringify({dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                self.assertAlmostEqual(metrics['dpr'], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics['scale'], 1, metrics)
                self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                self.assertIn('Texto publicado', js('document.querySelector("#raceDetailContainer").textContent'))

                js('document.querySelector("[data-race-edit]").click()')
                self.assertEqual(js('document.activeElement.name'), 'nome')
                js('''{let field=document.querySelector('[data-race-form] [name=nome]');field.value='Rascunho';field.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));}''')
                self.assertFalse(js('document.querySelector("[data-race-form]").classList.contains("is-open")'))
                self.assertEqual(js('document.querySelector("[data-race-form] [name=nome]").value'), 'Povo Editorial')
                self.assertTrue(js('document.activeElement.hasAttribute("data-race-edit")'))
                js('''document.querySelector('[data-race-edit]').click();
                    document.querySelector('[data-race-form] [name=nome]').value='Outro rascunho';
                    document.querySelector('[data-race-cancel]').click();''')
                self.assertFalse(js('document.querySelector("[data-race-form]").classList.contains("is-open")'))
                self.assertEqual(js('document.querySelector("[data-race-form] [name=nome]").value'), 'Povo Editorial')
                self.assertTrue(js('document.activeElement.hasAttribute("data-race-edit")'))

                js('''{document.querySelector('[data-race-edit]').click();
                    document.querySelector('[data-race-form] [name=lore_presentation]').value='Texto revisado';
                    document.querySelector('[data-race-form] [name=imagem_foco_x]').value='39';
                    window.qaFetch=window.fetch;window.qaCalls=0;
                    window.fetch=()=>{window.qaCalls++;return new Promise(resolve=>window.qaResolve=resolve)};
                    document.querySelector('[data-race-form]').requestSubmit();}''')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                until('document.querySelector("[data-race-form] .wiki-inline-save").disabled')
                js('document.querySelector("[data-race-form]").dispatchEvent(new Event("submit",{cancelable:true}))')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertEqual(js('document.querySelector("[data-race-form]").getAttribute("aria-busy")'), 'true')
                self.assertTrue(js('document.querySelector("[data-race-cancel]").disabled'))
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}),{status:503,headers:{"Content-Type":"application/json"}}))')
                until('!document.querySelector("[data-race-form] .wiki-inline-save").disabled')
                self.assertIn('Falha temporaria', js('document.querySelector("[data-race-save-error]").textContent'))
                self.assertTrue(js('document.activeElement.hasAttribute("data-race-save-error")'))
                self.assertEqual(js('document.querySelector("[data-race-form] [name=lore_presentation]").value'), 'Texto revisado')
                self.assertEqual(js('document.querySelector("[data-race-form] [name=imagem_foco_x]").value'), '39')
                race.refresh_from_db()
                self.assertEqual(race.lore_presentation, 'Texto publicado')

                js('''window.fetch=window.qaFetch;
                    document.querySelector('[data-race-form] [name=imagem_foco_x]').value='101';
                    document.querySelector('[data-race-form]').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));''')
                until('document.querySelector("[data-race-save-error]").textContent.includes("entre 0 e 100")')
                race.refresh_from_db()
                self.assertEqual(race.imagem_foco_x, 50)

                js('document.querySelector("[data-race-form] [name=imagem_foco_x]").value="39"')
                js('document.querySelector("[data-race-form]").requestSubmit()')
                until('document.querySelector("#raceDetailContainer")?.textContent.includes("Texto revisado") && !document.querySelector("[data-race-form]").classList.contains("is-open")')
                race.refresh_from_db()
                self.assertEqual(race.lore_presentation, 'Texto revisado')
                self.assertEqual(race.imagem_foco_x, 39)
                self.assertTrue(js('document.activeElement.hasAttribute("data-race-edit")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                call('Page.reload')
                until('document.readyState === "complete" && document.querySelector("#raceDetailContainer")?.textContent.includes("Texto revisado")')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
