"""The class catalogue remains readable and navigable on a narrow screen."""

import base64
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import TbClasse, TbClassehabilidade


class ClassCatalogReadabilityBrowserTests(StaticLiveServerTestCase):
    def test_mobile_class_search_ajax_detail_and_progression_at_200_percent(self):
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

        classe = TbClasse.objects.create(
            nome='Arcanista do QA', slug='arcanista-do-qa',
            tagline='Classe para leitura móvel.', atributo_principal='Inteligência',
            dado_vida='d8',
        )
        TbClasse.objects.create(nome='Guardião do QA', slug='guardiao-do-qa')
        TbClassehabilidade.objects.create(
            id_classe=classe, nome='Luz da Leitura',
            descricao='Texto de habilidade legível no celular.', niveladquirido=1,
        )
        mystic_fixture = json.loads((Path(__file__).parent / 'fixtures' / 'conteudo.json').read_text(encoding='utf-8'))
        mystic_description = next(item['fields']['descricao'] for item in mystic_fixture
                                  if item['model'] == 'home.tbclassehabilidade' and item['pk'] == 1428)
        TbClassehabilidade.objects.create(
            id_classe=classe, nome='Feitiçaria Mística',
            descricao=mystic_description, niveladquirido=1,
        )
        detail_url = reverse('classe_detail', kwargs={'slug': classe.slug})
        full_detail = self.client.get(detail_url)
        self.assertEqual(full_detail.status_code, 200)
        self.assertContains(full_detail, 'Texto de habilidade legível no celular.')
        self.assertContains(full_detail, 'text-[14px] leading-[1.4]')
        partial = self.client.get(detail_url + '?ajax=1')
        self.assertEqual(partial.status_code, 200)
        self.assertContains(partial, 'Texto de habilidade legível no celular.')
        self.assertContains(partial, 'text-[14px] leading-[1.4]')

        with tempfile.TemporaryDirectory(prefix='bonfire-class-readability-', ignore_cleanup_errors=True) as scratch:
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

                call('Page.navigate', {'url': self.live_server_url + reverse('classes')})
                wait_for('document.readyState === "complete" && !!document.querySelector("[data-class-menu-toggle]")')
                self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 2, 'mobile': True,
                })
                js('document.querySelector("[data-class-menu-toggle]").click()')
                self.assertEqual(js('document.querySelector("[data-class-menu-toggle]").getAttribute("aria-expanded")'), 'true')
                self.assertEqual(js('document.activeElement.id'), 'classSearch')
                layout = js('''({width:innerWidth,scroll:document.documentElement.scrollWidth,
                    client:document.documentElement.clientWidth,
                    sidebar:document.querySelector('#classSidebar').getBoundingClientRect().toJSON(),
                    toggle:document.querySelector('[data-class-menu-toggle]').getBoundingClientRect().toJSON(),
                    navFont:parseFloat(getComputedStyle(document.querySelector('.class-nav-item')).fontSize)})''')
                self.assertEqual(layout['width'], 360, layout)
                self.assertLessEqual(layout['scroll'], layout['client'], layout)
                self.assertGreaterEqual(layout['sidebar']['width'], 280, layout)
                self.assertLessEqual(layout['toggle']['right'], layout['client'], layout)
                self.assertGreaterEqual(layout['navFont'], 12, layout)

                js('''(() => { const input=document.querySelector('#classSearch');
                    input.value='Arcanista do QA'; input.dispatchEvent(new Event('input', {bubbles:true}));
                    input.focus(); })()''')
                self.assertEqual(js('document.querySelectorAll(".class-nav-item:not(.hidden)").length'), 1)
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                wait_for('location.pathname === ' + json.dumps(detail_url) +
                         ' && !!document.querySelector("[data-feature-list] [data-markdown]")')
                self.assertFalse(js('document.body.classList.contains("class-menu-open")'))
                self.assertLessEqual(js('document.querySelector("[data-class-menu-toggle]").getBoundingClientRect().bottom'),
                                     js('document.querySelector(".class-detail-layout h1").getBoundingClientRect().top'))
                detail = js('''({scroll:document.documentElement.scrollWidth,
                    client:document.documentElement.clientWidth,
                    feature:parseFloat(getComputedStyle(document.querySelector('[data-feature-list] [data-markdown]')).fontSize),
                    table:parseFloat(getComputedStyle(document.querySelector('.class-progression-scroll table')).fontSize),
                    tableScroll:document.querySelector('.class-progression-scroll').scrollWidth,
                    tableClient:document.querySelector('.class-progression-scroll').clientWidth})''')
                self.assertLessEqual(detail['scroll'], detail['client'], detail)
                self.assertGreaterEqual(detail['feature'], 14, detail)
                self.assertGreaterEqual(detail['table'], 12, detail)
                self.assertGreater(detail['tableScroll'], detail['tableClient'], detail)
                contrast = js('''(() => {
                    const title = document.querySelector('[data-feature-title]');
                    const card = title.closest('[data-feature-card]');
                    const rgb = value => value.match(/\\d+/g).slice(0, 3).map(Number);
                    const luminance = channels => channels.map(channel => {
                        const c = channel / 255;
                        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
                    }).reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
                    const foreground = luminance(rgb(getComputedStyle(title).color));
                    const background = luminance(rgb(getComputedStyle(card).backgroundColor));
                    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
                })()''')
                self.assertGreaterEqual(contrast, 4.5)
                mystic_layout = js('''(() => {
                    const card = [...document.querySelectorAll('[data-feature-card]')]
                        .find(item => item.querySelector('[data-feature-title]')?.textContent.includes('Feitiçaria Mística'));
                    const body = card?.querySelector('[data-markdown]');
                    return {paragraphs: body?.querySelectorAll('p').length || 0,
                        headings: body?.querySelectorAll('h5').length || 0,
                        tables: body?.querySelectorAll('table').length || 0};
                })()''')
                self.assertGreaterEqual(mystic_layout['paragraphs'], 5, mystic_layout)
                self.assertGreaterEqual(mystic_layout['headings'], 5, mystic_layout)
                self.assertEqual(mystic_layout['tables'], 1, mystic_layout)
                mystic_heading = js('''(() => {
                    const heading = [...document.querySelectorAll('[data-markdown] h5')]
                        .find(item => item.textContent.includes('Truques'));
                    return {weight: parseInt(getComputedStyle(heading).fontWeight, 10),
                        size: parseFloat(getComputedStyle(heading).fontSize)};
                })()''')
                self.assertGreaterEqual(mystic_heading['size'], 14, mystic_heading)
                self.assertGreaterEqual(mystic_heading['weight'], 700, mystic_heading)
                screenshot_path = os.environ.get('BONFIRE_QA_CLASS_SCREENSHOT')
                if screenshot_path:
                    screenshot = call('Page.captureScreenshot', {'captureBeyondViewport': True})
                    Path(screenshot_path).write_bytes(base64.b64decode(screenshot['data']))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
