import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import TbClasse, TbMagia


class MagiasClassFilterTests(TestCase):
    def test_catalog_exposes_exact_spell_class_membership(self):
        TbClasse.objects.create(nome='Bardo', slug='bardo')
        TbClasse.objects.create(nome='Mago', slug='mago')
        TbMagia.objects.create(
            nome='Luz de Teste',
            slug='luz-de-teste',
            nivel=0,
            escola='Evocação',
            classes='Bardo, Mago',
        )

        response = self.client.get(reverse('magias_listas'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['classes_magia'], ['Bardo', 'Mago'])
        self.assertEqual(response.context['magias'][0]['classes_lista'], ['Bardo', 'Mago'])
        self.assertContains(response, 'id="mg-classe"')
        self.assertContains(response, '<option value="Bardo">Bardo</option>', html=True)
        self.assertContains(response, "(m.classes_lista||[]).indexOf(classe)===-1")


class MagiasMobileAccessibilityTests(StaticLiveServerTestCase):
    def test_drawer_keyboard_zoom_and_reduced_motion(self):
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

        TbMagia.objects.create(nome='Luz de Teste', slug='luz-de-teste', nivel=0, escola='Evocação')
        TbMagia.objects.create(nome='Brasa de Teste', slug='brasa-de-teste', nivel=1, escola='Evocação')
        with tempfile.TemporaryDirectory(prefix='bonfire-magias-a11y-', ignore_cleanup_errors=True) as scratch:
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
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                def key(name, virtual_key, text=None):
                    for event_type in ('keyDown', 'keyUp'):
                        params = {'type': event_type, 'key': name, 'code': name,
                                  'windowsVirtualKeyCode': virtual_key}
                        if text and event_type == 'keyDown':
                            params['text'] = text
                        call('Input.dispatchKeyEvent', params)

                call('Page.navigate', {'url': self.live_server_url + reverse('magias_listas')})
                wait_for('document.querySelector("#mgResults [data-slug]") !== null')
                self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                self.assertEqual(js('visualViewport.scale'), 1)
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                self.assertTrue(js('document.querySelector("#mgList").inert'))
                self.assertEqual(js('document.querySelector("#mgList").getAttribute("aria-hidden")'), 'true')
                js('document.querySelector("#mgMobileMenuButton").focus()')
                key('Enter', 13, '\r')
                self.assertEqual(js('document.querySelector("#mgMobileMenuButton").getAttribute("aria-expanded")'), 'true')
                self.assertEqual(js('document.activeElement?.id'), 'mg-busca')
                self.assertFalse(js('document.querySelector("#mgList").inert'))
                self.assertNotEqual(js('getComputedStyle(document.activeElement).outlineStyle'), 'none')
                key('Escape', 27)
                self.assertTrue(js('document.querySelector("#mgList").inert'))
                self.assertEqual(js('document.activeElement?.id'), 'mgMobileMenuButton')
                js('document.querySelector("#mgMobileMenuButton").click()')
                js('document.querySelector("#mgResults [data-slug=brasa-de-teste]").click()')
                wait_for('new URLSearchParams(location.search).get("magia") === "brasa-de-teste"')
                self.assertEqual(js('document.querySelector("#mgDetail h2")?.textContent'), 'Brasa de Teste')
                self.assertTrue(js('document.querySelector("#mgList").inert'))
                call('Emulation.setEmulatedMedia', {
                    'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}],
                })
                self.assertEqual(js('getComputedStyle(document.querySelector("#mgResults [data-slug]")).transitionDuration'), '0s')
                self.assertEqual(js('getComputedStyle(document.querySelector("#mgList")).transitionDuration'), '0s')
                self.assertEqual(js('getComputedStyle(document.querySelector("#mgDetail")).animationName'), 'none')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 2560, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False,
                })
                wait_for('!document.querySelector("#mgList").inert')
                self.assertIsNone(js('document.querySelector("#mgList").getAttribute("aria-hidden")'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
