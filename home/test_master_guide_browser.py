"""The guide leads to the existing in-site master request flow."""

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

from .models import TbPerfilMestre


class MasterGuideBrowserTests(StaticLiveServerTestCase):
    def test_guide_navigation_and_request_flow(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')

        guide_url = reverse('guia_mestres')
        profile_url = reverse('profile') + '?aba=mestre'
        guide = self.client.get(guide_url)
        self.assertEqual(guide.status_code, 200)
        self.assertGreaterEqual(guide.content.count(f'href="{profile_url}"'.encode()), 2)
        self.assertNotContains(guide, 'docs.google.com/forms')
        self.assertContains(guide, 'Como solicitar a avaliação')
        for anchor in ('boas-vindas', 'requisitos', 'fluxo-de-aprovacao', 'ferramentas',
                       'publicacao', 'divisao', 'hierarquia', 'penalidades'):
            self.assertContains(guide, f'href="#{anchor}"')
            self.assertContains(guide, f'id="{anchor}"')

        user = get_user_model().objects.create_user('guide-master-candidate')
        self.client.force_login(user)
        profile = self.client.get(profile_url)
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, 'Solicitar participação')
        self.assertContains(profile, f'action="{reverse("master_request")}"')
        response = self.client.post(reverse('master_request'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], profile_url + '#perfil-mestre')
        self.assertEqual(TbPerfilMestre.objects.get(user=user).status_mestre, 'pendente')
        self.assertContains(self.client.get(profile_url), 'Solicitação enviada')

        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable for browser viewport check.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.is_file()), None)
        if not browser:
            self.skipTest('Chrome or Edge unavailable for browser viewport check.')

        with tempfile.TemporaryDirectory(prefix='bonfire-master-guide-', ignore_cleanup_errors=True) as browser_profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={browser_profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(browser_profile) / 'DevToolsActivePort'
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
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Page.enable')
                for width in (360, 1440):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 900, 'deviceScaleFactor': 1, 'mobile': width == 360,
                    })
                    call('Page.navigate', {'url': self.live_server_url + guide_url})
                    for _ in range(80):
                        if js('document.readyState === "complete" && !!document.querySelector(".mh-guide-index")'):
                            break
                        time.sleep(.1)
                    else:
                        self.fail('Guide did not load in browser.')
                    metrics = json.loads(js('''JSON.stringify({
                        scroll: document.documentElement.scrollWidth,
                        client: document.documentElement.clientWidth,
                        anchors: document.querySelectorAll('.mh-guide-index > a').length,
                        href: document.querySelector('.mh-guide section a[href*="aba=mestre"]').getAttribute('href')
                    })'''))
                    self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                    self.assertEqual(metrics['anchors'], 8, metrics)
                    self.assertEqual(metrics['href'], profile_url, metrics)
            finally:
                if ws is not None:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
