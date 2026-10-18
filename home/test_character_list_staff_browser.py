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


class CharacterListStaffBrowserTests(StaticLiveServerTestCase):
    def test_staff_finds_other_accounts_without_exposing_them_to_players(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome ou Edge indisponível.')

        staff = get_user_model().objects.create_user('character-auditor', is_staff=True)
        owner_a = get_user_model().objects.create_user('aurora-owner')
        owner_b = get_user_model().objects.create_user('bruma-owner')
        TbPersonagem.objects.create(dono=staff, nome='Minha Ficha')
        active = TbPersonagem.objects.create(dono=owner_a, nome='Áurea', arquivado=False)
        archived = TbPersonagem.objects.create(dono=owner_b, nome='Bruma', arquivado=True)
        url = reverse('personagens')
        self.client.force_login(owner_a)
        ordinary = self.client.get(url)
        self.assertNotContains(ordinary, 'data-cw-staff-controls')
        self.assertNotContains(ordinary, 'Bruma')
        self.client.force_login(staff)

        with tempfile.TemporaryDirectory(prefix='bonfire-staff-list-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
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

                def call(method, params):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('id') == sequence:
                            self.assertNotIn('error', result, method)
                            return result.get('result', {})

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

                call('Network.enable', {})
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + url})
                wait_for('document.querySelector("[data-cw-staff-controls]")?.hidden === false')
                self.assertEqual(js('document.querySelectorAll("[data-cw-staff-card]:not([hidden])").length'), 2)
                self.assertEqual(js('document.querySelectorAll("[data-cw-card]:not([hidden])").length'), 1)
                js('document.querySelector("#cw-staff-search").value = "aurora"; document.querySelector("#cw-staff-search").dispatchEvent(new Event("input", {bubbles:true}))')
                self.assertEqual(js('document.querySelectorAll("[data-cw-staff-card]:not([hidden])").length'), 1)
                self.assertIn('Áurea', js('document.querySelector("[data-cw-staff-card]:not([hidden])").textContent'))
                self.assertTrue(js(f'document.querySelector("[data-cw-staff-card]:not([hidden])").href.endsWith("{reverse("ficha_detail", args=[active.pk])}")'))
                self.assertEqual(js('document.querySelectorAll("[data-cw-card]:not([hidden])").length'), 1)
                js('document.querySelector("#cw-staff-search").value = ""; document.querySelector("#cw-staff-group").value = "inativo"; document.querySelector("#cw-staff-group").dispatchEvent(new Event("change", {bubbles:true}))')
                self.assertEqual(js('document.querySelectorAll("[data-cw-staff-card]:not([hidden])").length'), 1)
                self.assertIn('Bruma', js('document.querySelector("[data-cw-staff-card]:not([hidden])").textContent'))
                self.assertTrue(js(f'document.querySelector("[data-cw-staff-card]:not([hidden])").href.endsWith("{reverse("ficha_detail", args=[archived.pk])}")'))
                js('document.querySelector("#cw-staff-search").value = "nada"; document.querySelector("#cw-staff-search").dispatchEvent(new Event("input", {bubbles:true}))')
                self.assertFalse(js('document.querySelector("[data-cw-staff-empty]").hidden'))
                js('document.querySelector("[data-cw-staff-clear]").click()')
                self.assertEqual(js('document.querySelectorAll("[data-cw-staff-card]:not([hidden])").length'), 2)
                self.assertTrue(js('document.querySelector("[data-cw-staff-empty]").hidden'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
