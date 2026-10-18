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

from .models import TbPersonagem


class WorkshopTabsBrowserTests(StaticLiveServerTestCase):
    def test_mobile_tabs_survive_character_switch_and_browser_history(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponivel.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome ou Edge indisponivel.')

        user = get_user_model().objects.create_user('workshop-tabs-user')
        first = TbPersonagem.objects.create(dono=user, nome='Primeira Ficha')
        second = TbPersonagem.objects.create(dono=user, nome='Segunda Ficha')
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-workshop-tabs-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                '--window-size=360,800', f'--user-data-dir={profile}', 'about:blank',
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

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Network.enable')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                path = reverse('oficina_magia')
                call('Page.navigate', {'url': f'{self.live_server_url}{path}?personagem={first.pk}&tab=transcription'})
                wait_for('document.querySelector("[data-workshop-tab=transcription][aria-pressed=true]") !== null')
                self.assertEqual(js('innerWidth'), 360)
                self.assertTrue(js('!document.querySelector("[data-workshop-panel=transcription]").hidden'))
                js('document.querySelector("[data-workshop-tab=components]").click()')
                self.assertTrue(js('location.search.includes("tab=components")'))
                self.assertEqual(js('document.querySelector("[data-shop-picker] [name=tab]").value'), 'components')
                js(f'document.querySelector("[data-shop-personagem]").value = "{second.pk}"; document.querySelector("[data-shop-picker]").requestSubmit()')
                wait_for('document.querySelector("[data-workshop-tab=components][aria-pressed=true]") !== null')
                wait_for(f'document.querySelector("[data-shop-personagem]").value === "{second.pk}"')
                js('document.querySelector("[data-workshop-tab=casting]").click()')
                js('history.back()')
                wait_for('document.querySelector("[data-workshop-tab=components][aria-pressed=true]") !== null')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
