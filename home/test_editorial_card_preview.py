"""Previa de cartoes editoriais a partir da API real."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection

from .models import TbBestiario, TbClasse, TbClassehabilidade


class EditorialCardPreviewTests(StaticLiveServerTestCase):
    def test_card_description_statblock_and_link_are_safe_on_mobile(self):
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

        description = '**Destaque** <img src=x onerror=alert(1)> [perigo](javascript:alert(1)) [referencia](https://example.org)'
        classe = TbClasse.objects.create(nome='Classe da Carta', slug='classe-da-carta')
        TbClassehabilidade.objects.create(id_classe=classe, nome='Carta Segura', niveladquirido=1, descricao=description)
        TbBestiario.objects.create(slug='criatura-da-carta', nome='Criatura da Carta', tipo='Besta', tamanho='M', nd='1', statblock_json={'ac': 14, 'hp': 20})

        with tempfile.TemporaryDirectory(prefix='bonfire-editorial-card-', ignore_cleanup_errors=True) as profile:
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

                def open_card(table, args):
                    js('document.querySelector(".bonfire-preview-card-close")?.click()')
                    js('''(() => {
                        const trigger = document.querySelector('#cardTrigger');
                        trigger.dataset.table = %s;
                        trigger.dataset.args = %s;
                        trigger.click();
                    })()''' % (json.dumps(table), json.dumps(args)))
                    wait_for('document.querySelector(".bonfire-preview-card-body") !== null')

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + '/'})
                wait_for('typeof window.bonfireOptionsWidget?.hydrate === "function"')
                js('''(() => {
                    const trigger = document.createElement('a');
                    trigger.id = 'cardTrigger';
                    trigger.href = '#';
                    trigger.className = 'bonfire-card-trigger';
                    trigger.textContent = 'Abrir carta';
                    document.querySelector('main').appendChild(trigger);
                })()''')
                open_card('tbClasseHabilidade', 'classe-da-carta,carta-segura')
                self.assertTrue(js('document.querySelector(".bonfire-preview-card-body strong") !== null'))
                self.assertEqual(js('document.querySelectorAll(".bonfire-preview-card-body img[onerror], .bonfire-preview-card-body a[href^=javascript], .bonfire-preview-card-body script").length'), 0)
                self.assertEqual(js('document.querySelectorAll(".bonfire-preview-card-body a[href=\\"https://example.org\\"]").length'), 1)
                self.assertTrue(js('document.querySelector(".bonfire-preview-card-more").href.startsWith(location.origin + "/jogador/classes/")'))

                open_card('tbBestiario', 'criatura-da-carta')
                self.assertTrue(js('document.querySelector(".bonfire-preview-card-body .bonfire-creature-card-sheet b") !== null'))
                self.assertEqual(js('document.querySelectorAll(".bonfire-preview-card-body script, .bonfire-preview-card-body img[onerror]").length'), 0)
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))

                js('window.renderBonfireMarkdown = undefined')
                open_card('tbClasseHabilidade', 'classe-da-carta,carta-segura')
                self.assertEqual(js('document.querySelectorAll(".bonfire-preview-card-body img, .bonfire-preview-card-body a").length'), 0)
                self.assertTrue(js('document.querySelector(".bonfire-preview-card-body").textContent.includes("<img src=x")'))

                js('''window.fetch = async () => ({ ok: true, json: async () => ({
                    success: true, title: 'Carta externa', description: 'Texto', url: 'javascript:alert(1)'
                }) })''')
                open_card('tbClasseHabilidade', 'classe-da-carta,carta-segura')
                self.assertTrue(js('document.querySelector(".bonfire-preview-card-more") === null'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
