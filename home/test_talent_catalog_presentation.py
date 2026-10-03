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

from .models import TbTalento


class TalentCatalogPresentationTests(StaticLiveServerTestCase):
    def test_editorial_text_is_literal_and_catalog_still_selects_on_mobile(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponível.')

        injected = '<img src=x onerror="window.__talentInjected=1">'
        TbTalento.objects.create(
            nome=f'Arcano {injected}', slug='arcano-literal',
            etiquetas_adicionais=f'Magia, {injected}', pre_requisito=injected,
            descricao='**Benefício editorial**',
        )
        TbTalento.objects.create(nome='Seguro', slug='seguro', descricao='Texto seguro')

        with tempfile.TemporaryDirectory(prefix='bonfire-talent-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
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
                            return result

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result']
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('jogador_talentos') + '#talento-arcano-literal'})
                wait_for('document.querySelector("[data-talent-title]")?.textContent.includes("Arcano")')
                self.assertEqual(js('document.querySelector("[data-talent-title]").textContent'), f'Arcano {injected}')
                self.assertEqual(js('document.querySelectorAll("#talentosListItems img, #talentoDetail img").length'), 0)
                self.assertFalse(js('window.__talentInjected === 1'))
                self.assertTrue(js('document.querySelector("#talentoDetail").textContent.includes(' + json.dumps(injected) + ')'))
                self.assertEqual(js('document.querySelector("[data-talent-preview] strong")?.textContent'), 'Benefício editorial')
                self.assertTrue(js('document.querySelector("#talentosListItems").textContent.includes(' + json.dumps(injected) + ')'))

                js('searchInput.value = "Seguro"; searchInput.dispatchEvent(new Event("input", {bubbles: true}))')
                wait_for('document.querySelector("#talentosListItems")?.textContent.includes("Seguro") && !document.querySelector("#talentosListItems")?.textContent.includes("Arcano")')
                js('document.querySelector("#talentosListItems > div").click()')
                wait_for('document.querySelector("[data-talent-title]")?.textContent === "Seguro"')
                self.assertFalse(js('window.__talentInjected === 1'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
