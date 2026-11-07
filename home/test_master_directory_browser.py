"""Public master directory with a listed profile at common viewport widths."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbPerfilMestre


class MasterDirectoryBrowserTests(StaticLiveServerTestCase):
    def test_listed_master_search_and_profile_link_fit_viewports(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.is_file()), None)
        if not browser:
            self.skipTest('Chrome or Edge unavailable.')

        user = get_user_model().objects.create_user('mestre-da-comunidade')
        TbPerfilMestre.objects.create(
            user=user, modo='mestre', status_mestre='aprovado', listado=True,
            estilo='Narrativas de exploração e descoberta ' * 3,
            apresentacao='Uma apresentação pública com texto longo. ' * 12,
        )
        hidden = get_user_model().objects.create_user('mestre-oculto')
        TbPerfilMestre.objects.create(user=hidden, modo='mestre', status_mestre='aprovado', listado=False)

        with tempfile.TemporaryDirectory(prefix='bonfire-master-directory-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                for _ in range(80):
                    if port_file.is_file():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.is_file(), 'Browser did not start.')
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=10, origin='http://localhost')
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        message = json.loads(ws.recv())
                        if message.get('id') == sequence:
                            self.assertNotIn('error', message, method)
                            return message['result']

                def js(expression):
                    value = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', value, expression)
                    return value['result'].get('value')

                def until(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Timed out: {expression}')

                call('Page.enable')
                directory = self.live_server_url + reverse('masters_directory')
                for width in (360, 390, 768, 1024, 1440):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 900, 'deviceScaleFactor': 1,
                        'mobile': width <= 768,
                    })
                    call('Page.navigate', {'url': directory + '?' + urlencode({'q': 'exploração'})})
                    until('document.readyState === "complete" && !!document.querySelector(".md-card")')
                    metrics = json.loads(js('''JSON.stringify((() => {
                        const card = document.querySelector('.md-card');
                        const link = card.querySelector('.md-card-actions a');
                        const search = document.querySelector('#master-search');
                        const button = document.querySelector('.mh-filter button');
                        return {
                            width: innerWidth, scroll: document.documentElement.scrollWidth,
                            client: document.documentElement.clientWidth,
                            cards: document.querySelectorAll('.md-card').length,
                            name: card.querySelector('h2').textContent,
                            href: link.getAttribute('href'),
                            search: search.value, inputHeight: search.getBoundingClientRect().height,
                            buttonHeight: button.getBoundingClientRect().height,
                            linkHeight: link.getBoundingClientRect().height,
                        };
                    })())'''))
                    self.assertEqual(metrics['cards'], 1, metrics)
                    self.assertIn(user.username, metrics['name'], metrics)
                    self.assertIn(user.username, metrics['href'], metrics)
                    self.assertEqual(metrics['search'], 'exploração', metrics)
                    self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                    self.assertGreaterEqual(metrics['inputHeight'], 44, metrics)
                    self.assertGreaterEqual(metrics['buttonHeight'], 44, metrics)
                    self.assertGreaterEqual(metrics['linkHeight'], 44, metrics)
                call('Page.navigate', {'url': self.live_server_url + metrics['href']})
                until('document.readyState === "complete" && document.body.innerText.includes("mestre-da-comunidade")')
                self.assertIn(user.username, js('document.body.innerText'))
            finally:
                if ws is not None:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
