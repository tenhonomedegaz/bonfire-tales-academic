"""A paginação parcial do diretório usa URLs compartilháveis e banco de teste."""

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


class PlayersPaginationBrowserTests(StaticLiveServerTestCase):
    def test_second_page_keeps_filters_and_history_without_reload(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível para o navegador de teste.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponível para o navegador de teste.')

        user_model = get_user_model()
        for index in range(22):
            user_model.objects.create_user(username=f'pageuser{index:02}', is_staff=True)

        with tempfile.TemporaryDirectory(prefix='bonfire-players-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists(), 'Chrome não abriu a porta de depuração.')
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })['result']
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
                call('Page.navigate', {'url': (
                    f'{self.live_server_url}/jogadores/'
                    '?filtro=equipe&ordem=nome&q=pageuser'
                )})
                wait_for('document.querySelectorAll(".player-card").length === 18')
                js('window.__paginationMarker = 42')
                self.assertEqual(js('document.querySelector(".players-search input[name=q]").getAttribute("aria-label")'), 'Buscar jogador ou personagem público')
                self.assertEqual(js('document.querySelectorAll(".players-tabs [aria-current=page]").length'), 1)
                js('document.querySelector(".players-search input[name=q]").focus()')
                self.assertEqual(js('getComputedStyle(document.querySelector(".players-search")).outlineStyle'), 'solid')

                js('document.querySelector(".players-pagination a[href*=page]").click()')
                wait_for('location.search.includes("page=2") && document.querySelectorAll(".player-card").length === 4')
                self.assertEqual(js('window.__paginationMarker'), 42)
                self.assertTrue(js('document.activeElement.classList.contains("players-meta")'))
                self.assertTrue(js('location.search.includes("filtro=equipe") && location.search.includes("ordem=nome") && location.search.includes("q=pageuser")'))

                js('document.querySelector(".players-pagination a[href*=page]").click()')
                wait_for('location.search.includes("page=1") && document.querySelectorAll(".player-card").length === 18')
                self.assertEqual(js('window.__paginationMarker'), 42)
                self.assertTrue(js('document.activeElement.classList.contains("players-meta")'))

                js('history.back()')
                wait_for('location.search.includes("page=2") && document.querySelectorAll(".player-card").length === 4')
                self.assertEqual(js('window.__paginationMarker'), 42)
                self.assertTrue(js('document.activeElement.classList.contains("players-meta")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))

                js('document.querySelector(".players-search input[name=q]").value = "nao-encontrado-xyz"; document.querySelector(".players-search button").click()')
                wait_for('location.search.includes("nao-encontrado-xyz") && document.querySelectorAll(".player-card").length === 0')
                self.assertEqual(js('document.querySelector(".players-meta [role=status]").getAttribute("aria-live")'), 'polite')
                self.assertTrue(js('document.querySelector(".players-meta").textContent.includes("0 perfis")'))
                self.assertEqual(js('window.__paginationMarker'), 42)
                js('history.back()')
                wait_for('location.search.includes("page=2") && document.querySelectorAll(".player-card").length === 4')
                self.assertEqual(js('window.__paginationMarker'), 42)
                self.assertEqual(js('document.querySelector(".players-search input[name=q]").value'), 'pageuser')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
