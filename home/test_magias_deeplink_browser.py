"""A global search spell result opens its readable card on a narrow screen."""

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

from home.models import TbMagia


class MagiasDeepLinkBrowserTests(StaticLiveServerTestCase):
    def test_global_search_opens_the_selected_spell_on_mobile(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires an isolated PostgreSQL test database.')
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
        TbMagia.objects.get_or_create(
            slug='luz-de-teste',
            defaults={'nome': 'Luz de Teste', 'nivel': 0, 'escola': 'Evocação'},
        )

        with tempfile.TemporaryDirectory(prefix='bonfire-magias-link-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                for _ in range(150):
                    if port_file.exists() or process.poll() is not None:
                        break
                    time.sleep(.2)
                self.assertTrue(port_file.exists(), 'Browser did not start.')
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=10) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=30)
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(200):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Timed out waiting for {expression}')

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {
                    'url': self.live_server_url + reverse('busca') + '?q=Luz%20de%20Teste',
                })
                wait_for("document.querySelector('.cp-results a[href*=magia]') !== null")
                self.assertIn('magia=luz-de-teste', js(
                    "document.querySelector('.cp-results a[href*=magia]').getAttribute('href')"
                ))
                js("document.querySelector('.cp-results a[href*=magia]').click()")
                wait_for('document.activeElement?.id === "magia-luz-de-teste"')
                self.assertEqual(js('new URLSearchParams(location.search).get("magia")'), 'luz-de-teste')
                self.assertTrue(js('''(() => {
                    const rect=document.querySelector('#magia-luz-de-teste').getBoundingClientRect();
                    return rect.top >= 0 && rect.bottom <= innerHeight;
                })()'''))
                self.assertTrue(js('document.querySelector("#mgList").inert'))
                call('Page.reload')
                wait_for('document.activeElement?.id === "magia-luz-de-teste"')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
