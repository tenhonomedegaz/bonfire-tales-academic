"""QA de contraste dos selects editoriais no Admin real."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse


class AdminSelectPresentationTests(StaticLiveServerTestCase):
    def test_editorial_select_states_are_readable_in_chrome(self):
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível')
        chrome = os.environ.get('BONFIRE_QA_BROWSER') or shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome or not Path(chrome).exists():
            self.skipTest('Chrome ou Edge indisponível')

        editor = get_user_model().objects.create_superuser(
            username='select-editor', email='select-editor@example.invalid', password='test-only',
        )
        self.client.force_login(editor)
        session_key = self.client.cookies['sessionid'].value

        with tempfile.TemporaryDirectory(prefix='bonfire-admin-select-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists(), 'Chrome não iniciou')
                for _ in range(40):
                    try:
                        port = port_file.read_text(encoding='utf-8').splitlines()[0]
                        break
                    except (PermissionError, IndexError):
                        time.sleep(.1)
                else:
                    self.fail('Porta do Chrome indisponível')
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
                            return result

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result']
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': 'sessionid', 'value': session_key, 'url': self.live_server_url,
                })
                for width in (1280, 360):
                    with self.subTest(width=width):
                        call('Emulation.setDeviceMetricsOverride', {
                            'width': width, 'height': 800, 'deviceScaleFactor': 1,
                            'mobile': width == 360,
                        })
                        call('Page.navigate', {
                            'url': self.live_server_url + reverse('admin:home_tbconquista_add'),
                        })
                        for _ in range(80):
                            if js('Boolean(document.querySelector("#id_criterio option"))'):
                                break
                            time.sleep(.2)
                        self.assertTrue(js('Boolean(document.querySelector("#id_criterio option"))'))
                        self.assertTrue(js('[...document.styleSheets].some(s => s.href?.includes("bonfire_admin.css?v=7"))'))
                        call('Page.bringToFront')
                        js('document.querySelector("#id_criterio").focus()')
                        colors = js('''(() => {
                            const select = document.querySelector('#id_criterio');
                            const option = select.options[1];
                            const disabled = document.createElement('option');
                            disabled.disabled = true;
                            disabled.textContent = 'Indisponível';
                            select.append(disabled);
                            const style = node => getComputedStyle(node);
                            return {
                                scheme: style(select).colorScheme,
                                text: style(option).color,
                                background: style(option).backgroundColor,
                                selectedBackground: style(select.selectedOptions[0]).backgroundColor,
                                disabled: style(disabled).color,
                                focused: document.activeElement === select,
                                focusOutline: style(select).outlineStyle,
                            };
                        })()''')
                        self.assertEqual(colors['scheme'], 'dark')
                        self.assertEqual(colors['text'], 'rgb(242, 242, 243)')
                        self.assertEqual(colors['background'], 'rgb(10, 10, 11)')
                        self.assertEqual(colors['selectedBackground'], 'rgb(35, 35, 41)')
                        self.assertEqual(colors['disabled'], 'rgb(168, 168, 178)')
                        self.assertTrue(colors['focused'])
                        self.assertEqual(colors['focusOutline'], 'solid', colors)
                        self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                        for theme in ('light', 'dark'):
                            js('document.documentElement.dataset.theme = ' + json.dumps(theme))
                            themed = js('''(() => {
                                const select = document.querySelector('#id_criterio');
                                return [getComputedStyle(select).colorScheme,
                                        getComputedStyle(select.options[1]).color,
                                        getComputedStyle(select.options[1]).backgroundColor];
                            })()''')
                            self.assertEqual(themed, ['dark', 'rgb(242, 242, 243)', 'rgb(10, 10, 11)'])
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
