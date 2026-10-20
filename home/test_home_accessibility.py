"""QA da Home com zoom real, teclado e movimento reduzido."""

import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse


class HomeAccessibilityBrowserTests(StaticLiveServerTestCase):
    def test_home_reflows_and_remains_keyboard_usable_at_200_percent(self):
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

        with tempfile.TemporaryDirectory(prefix='bonfire-home-zoom-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({
                'partition': {'default_zoom_level': {'x': math.log(2) / math.log(1.2)}}
            }), encoding='utf-8')
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-first-run', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=800,900', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
                for _ in range(80):
                    if port_file.is_file():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.is_file(), 'Chrome nao iniciou.')
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
                        time.sleep(.1)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Emulation.setEmulatedMedia', {
                    'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}],
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('home')})
                wait_for('document.readyState === "complete" && !!document.querySelector("#home-primary-action")')
                metrics = js('''({width:innerWidth,outer:outerWidth,dpr:devicePixelRatio,
                    scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,
                    client:document.documentElement.clientWidth})''')
                self.assertEqual(metrics['outer'], 800, metrics)
                self.assertAlmostEqual(metrics['dpr'], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics['scale'], 1, metrics)
                self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                self.assertTrue(js('document.querySelector("#home-primary-action").getBoundingClientRect().width > 0'))
                self.assertEqual(js('document.querySelector("main section:first-of-type img").alt'), '')
                self.assertTrue(js('document.querySelector("main section:first-of-type h1").textContent.trim().length > 0'))
                self.assertTrue(js('matchMedia("(prefers-reduced-motion: reduce)").matches'))
                self.assertEqual(js('getComputedStyle(document.querySelector(".home-atlas-preview")).transitionDuration'), '0s')

                for width in (360, 768, 1280, 1920):
                    with self.subTest(width=width):
                        call('Emulation.setDeviceMetricsOverride', {
                            'width': width * 2, 'height': 900, 'deviceScaleFactor': 1,
                            'mobile': False,
                        })
                        self.assertEqual(
                            js('innerWidth'), width,
                            js('JSON.stringify({inner:innerWidth,scroll:document.documentElement.scrollWidth,dpr:devicePixelRatio})'),
                        )
                        self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                        self.assertLessEqual(
                            js('document.documentElement.scrollWidth'),
                            js('document.documentElement.clientWidth'),
                            'Home com rolagem horizontal em %dpx' % width,
                        )
                        cta = js('''(() => {const rect=document.querySelector('#home-primary-action').getBoundingClientRect();
                            return {left:rect.left,right:rect.right,width:rect.width};})()''')
                        self.assertGreater(cta['width'], 0)
                        self.assertGreaterEqual(cta['left'], 0)
                        self.assertLessEqual(cta['right'], js('document.documentElement.clientWidth'))
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 2,
                    'mobile': True,
                })
                mobile = js('''({width:innerWidth,scroll:document.documentElement.scrollWidth,
                    client:document.documentElement.clientWidth,
                    action:document.querySelector('#home-primary-action').getBoundingClientRect().toJSON(),
                    dpr:devicePixelRatio})''')
                self.assertEqual(mobile['width'], 360, mobile)
                self.assertEqual(mobile['dpr'], 2, mobile)
                self.assertLessEqual(mobile['scroll'], mobile['client'], mobile)
                self.assertGreaterEqual(mobile['action']['left'], 0, mobile)
                self.assertLessEqual(mobile['action']['right'], mobile['client'], mobile)
                call('Emulation.clearDeviceMetricsOverride')

                js('document.querySelector("#home-primary-action").focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                self.assertEqual(js('document.activeElement?.getAttribute("href")'), '#como-jogar')
                self.assertNotEqual(js('getComputedStyle(document.activeElement).outlineStyle'), 'none')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                wait_for('location.hash === "#como-jogar"')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 2,
                    'mobile': True,
                })
                js('document.querySelector("#home-primary-action").click()')
                wait_for('location.pathname === ' + json.dumps(reverse('register')))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
