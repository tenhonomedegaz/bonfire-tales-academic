"""Existing trap records remain readable in the redesigned catalogue."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbArmadilha


class TrapCatalogBrowserTests(StaticLiveServerTestCase):
    def test_real_records_search_selection_and_origin_on_mobile(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome or Edge unavailable.')

        author = get_user_model().objects.create_user('trap_catalog_author')
        official = TbArmadilha.objects.create(
            nome='Ponte de Cinzas', slug='ponte-de-cinzas', tipo='mecanica',
            nd='2', gatilho='Peso na ponte', efeito='Piso cede', comunidade=False,
        )
        community = TbArmadilha.objects.create(
            nome='Véu da Névoa', slug='veu-da-nevoa', tipo='magica',
            nd='3', gatilho='Fumaça arcana', efeito='Visão obscurecida',
            comunidade=True, autor=author,
        )
        response = self.client.get(reverse('mestre_armadilhas'))
        self.assertContains(response, official.nome)
        self.assertContains(response, community.nome)
        self.assertContains(response, f'id="armadilha-{official.pk}"', html=False)
        self.assertContains(response, f'id="armadilha-{community.pk}"', html=False)

        with tempfile.TemporaryDirectory(prefix='bonfire-traps-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
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
                self.assertTrue(port_file.exists())
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
                            self.assertNotIn('error', result, method)
                            return result['result']

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mestre_armadilhas')})
                for _ in range(80):
                    if js('document.readyState === "complete" && document.querySelectorAll(".ar-item").length === 2'):
                        break
                    time.sleep(.1)
                self.assertEqual(js('document.querySelectorAll(".ar-item").length'), 2)
                self.assertLessEqual(js('document.documentElement.scrollWidth'), 360)
                self.assertEqual(js('document.querySelectorAll(".ar-panel:not([hidden])").length'), 1)

                state = json.loads(js('''JSON.stringify((() => {
                    const input = document.querySelector('#ar-busca');
                    input.value = 'fumaca';
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    return {count: document.querySelector('#ar-count').textContent,
                        visible: [...document.querySelectorAll('.ar-item:not([hidden])')].map(el => el.textContent.trim()),
                        panel: document.querySelector('.ar-panel:not([hidden]) h2')?.textContent,
                        query: new URL(location.href).searchParams.get('q')};
                })())'''))
                self.assertEqual(state['count'], '1', state)
                self.assertEqual(state['panel'], community.nome, state)
                self.assertEqual(state['query'], 'fumaca', state)
                self.assertEqual(len(state['visible']), 1, state)

                js('''(() => {const input=document.querySelector('#ar-busca');
                    input.value='sem resultado';input.dispatchEvent(new Event('input', {bubbles:true}));})()''')
                self.assertEqual(js('document.querySelectorAll(".ar-panel:not([hidden])").length'), 0)
                self.assertTrue(js('!document.querySelector("#ar-reader-empty").hidden'))
                js('''(() => {const input=document.querySelector('#ar-busca');
                    input.value='';input.dispatchEvent(new Event('input', {bubbles:true}));})()''')
                self.assertEqual(js('document.querySelectorAll(".ar-item:not([hidden])").length'), 2)

                call('Page.navigate', {'url': self.live_server_url + reverse('mestre_armadilhas') + '?f=comunidade'})
                for _ in range(80):
                    if js('document.readyState === "complete" && document.querySelectorAll(".ar-item").length === 1'):
                        break
                    time.sleep(.1)
                self.assertEqual(js('document.querySelector(".ar-panel:not([hidden]) h2")?.textContent'), community.nome)
                self.assertEqual(js('document.querySelector("#ar-origin")?.value'), 'comunidade')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
