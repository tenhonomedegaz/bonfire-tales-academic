"""Integrated mobile capacity page: long legacy names and actionable controls."""

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

from home.models import TbPersonagem


class CharacterSlotsBrowserTests(StaticLiveServerTestCase):
    def test_long_preserved_sheet_and_actions_fit_mobile_widths(self):
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

        user = get_user_model().objects.create_user('slots-mobile-owner')
        character = TbPersonagem.objects.create(
            dono=user, nome='Personagem de campanha com nome extenso ' * 3,
            nivel=13, arquivado=False)
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-slots-mobile-', ignore_cleanup_errors=True) as profile:
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                for width in (360, 390, 768):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 800,
                        'deviceScaleFactor': 1, 'mobile': True,
                    })
                    call('Page.navigate', {
                        'url': self.live_server_url + reverse('character_slots'),
                    })
                    for _ in range(80):
                        if js('document.readyState === "complete" && !!document.querySelector(".bs-character-row button")'):
                            break
                        time.sleep(.1)
                    metrics = js('JSON.stringify({title:document.querySelector("#slots-title")?.textContent,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,button:document.querySelector(".bs-character-row button")?.getBoundingClientRect().height,characters:document.querySelectorAll(".bs-character-row").length})')
                    metrics = json.loads(metrics)
                    self.assertIn('slots', metrics['title'].lower(), metrics)
                    self.assertEqual(metrics['characters'], 1, metrics)
                    self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                    self.assertGreaterEqual(metrics['button'], 44, metrics)
                js('document.querySelector(".bs-character-row button").click()')
                review = json.loads(js('JSON.stringify({open:document.querySelector("[data-character-archive-review]").open,title:document.querySelector("[data-character-archive-title]").textContent,description:document.querySelector("[data-character-archive-description]").textContent})'))
                self.assertTrue(review['open'], review)
                self.assertIn('Arquivar', review['title'])
                self.assertIn(character.nome, review['description'])
                self.assertIn('preservada', review['description'])
                character.refresh_from_db()
                self.assertFalse(character.arquivado)
                js('document.querySelector("[data-character-archive-cancel]").click()')
                self.assertFalse(js('document.querySelector("[data-character-archive-review]").open'))
                character.refresh_from_db()
                self.assertFalse(character.arquivado)
                js('document.querySelector(".bs-character-row button").click()')
                js('document.querySelector("[data-character-archive-confirm]").click()')
                destination = reverse('personagens')
                for _ in range(80):
                    if js('location.pathname === ' + json.dumps(destination)
                          + ' && document.readyState === "complete"'):
                        break
                    time.sleep(.1)
                self.assertEqual(js('location.pathname'), destination)
                character.refresh_from_db()
                self.assertTrue(character.arquivado)
                self.assertFalse(character.publico)
                for _ in range(80):
                    if js('!!document.querySelector(".cw-character-card.is-vault [data-character-archive-action=restore]")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('!!document.querySelector(".cw-character-card.is-vault [data-character-archive-action=restore]")'))
                js('document.querySelector(".cw-character-card.is-vault summary").click()')
                js('document.querySelector(".cw-character-card.is-vault [data-character-archive-action=restore] button").click()')
                review = json.loads(js('JSON.stringify({open:document.querySelector("[data-character-archive-review]").open,title:document.querySelector("[data-character-archive-title]").textContent,description:document.querySelector("[data-character-archive-description]").textContent})'))
                self.assertTrue(review['open'], review)
                self.assertIn('Restaurar', review['title'])
                self.assertIn(character.nome, review['description'])
                character.refresh_from_db()
                self.assertTrue(character.arquivado)
                js('document.querySelector("[data-character-archive-confirm]").click()')
                for _ in range(80):
                    character.refresh_from_db()
                    if not character.arquivado:
                        break
                    time.sleep(.1)
                self.assertFalse(character.arquivado)
                self.assertFalse(character.publico)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
