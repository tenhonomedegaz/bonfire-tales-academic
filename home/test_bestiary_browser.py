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

from .models import TbBestiario


class BestiarySelectionBrowserTests(StaticLiveServerTestCase):
    def test_art_to_unillustrated_creature_opens_sheet_on_mobile(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome ou Edge indisponível.')

        illustrated = TbBestiario.objects.create(
            slug='corcel-ilustrado', nome='Corcel Ilustrado', tipo='Besta',
            tamanho='M', nd='2', imagem_url='/media/bestiario/corcel.png',
            statblock_json={'hp': 20},
        )
        plain = TbBestiario.objects.create(
            slug='corcel-cinzento', nome='Corcel Cinzento', tipo='Besta',
            tamanho='M', nd='3', statblock_json={'hp': 24},
        )
        with tempfile.TemporaryDirectory(prefix='bonfire-bestiary-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=360,800', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
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

                def cdp(method, params):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('id') == sequence:
                            self.assertNotIn('error', result, method)
                            return result.get('result', {})

                def js(expression):
                    result = cdp('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                cdp('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                cdp('Page.navigate', {'url': self.live_server_url + reverse('bestiario') + '?q=Corcel'})
                wait_for(f'document.querySelector("#monster-{illustrated.pk} .be-view-switch")?.hidden === false')
                js(f'document.querySelector("#monster-{illustrated.pk} [data-creature-view=art]").click()')
                self.assertTrue(js(f'!document.querySelector("#monster-{illustrated.pk}-art").hidden'))
                js(f'document.querySelector(".bz-item[data-target=monster-{plain.pk}]").click()')
                wait_for(f'!document.querySelector("#monster-{plain.pk}").classList.contains("hidden")')
                self.assertFalse(js(f'document.querySelector("#monster-{plain.pk}-sheet").hidden'))
                self.assertTrue(js(f'document.querySelector("#monster-{plain.pk}-art").hidden'))
                self.assertFalse(js(f'!!document.querySelector("#monster-{plain.pk} .be-view-switch")'))
                self.assertTrue(js(f'location.search.includes("q=Corcel") && location.search.includes("active={plain.pk}")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                cdp('Page.reload', {'ignoreCache': True})
                wait_for(f'document.querySelector("#monster-{plain.pk}")?.classList.contains("hidden") === false')
                self.assertFalse(js(f'document.querySelector("#monster-{plain.pk}-sheet").hidden'))
                js(f'location.hash = "monster-{plain.pk}-art"')
                wait_for(f'!document.querySelector("#monster-{plain.pk}-sheet").hidden')
                self.assertTrue(js(f'document.querySelector("#monster-{plain.pk}-art").hidden'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
