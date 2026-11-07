"""Leitura e previa inline de habilidades na pagina de classe."""

import json
import math
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

from .models import TbClasse, TbClassehabilidade, TbSubclasse


class ClassMarkdownPresentationTests(StaticLiveServerTestCase):
    def test_feature_and_editor_preview_sanitize_markdown_on_mobile(self):
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

        description = (
            '**Destaque** <img src=x onerror=alert(1)> '
            '[perigo](javascript:alert(1)) [referencia](https://example.org)'
        )
        classe = TbClasse.objects.create(nome='Classe de Teste', slug='classe-de-teste')
        TbSubclasse.objects.create(id_classe=classe, nome='Trilha do Fogo', slug='trilha-do-fogo')
        feature = TbClassehabilidade.objects.create(
            id_classe=classe, nome='Habilidade Editorial', niveladquirido=1,
            descricao=description,
        )
        editor = get_user_model().objects.create_superuser(
            'class-editor', 'class-editor@example.invalid', 'test-pass',
        )
        self.client.force_login(editor)

        with tempfile.TemporaryDirectory(prefix='bonfire-class-md-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({
                'partition': {'default_zoom_level': {'x': math.log(2) / math.log(1.2)}}
            }), encoding='utf-8')
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=800,900', 'about:blank',
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
                url = self.live_server_url + reverse('classe_detail', args=[classe.slug])
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-feature-card] [data-markdown] strong") !== null')
                self.assertEqual(js('document.querySelectorAll("[data-markdown] img[onerror], [data-markdown] a[href^=javascript], [data-markdown] script").length'), 0)
                self.assertEqual(js('document.querySelectorAll("[data-markdown] a[href=\\"https://example.org\\"]").length'), 1)

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-feature-edit]") !== null')
                js('document.querySelector("[data-feature-edit]").click()')
                js('''(() => {
                    const textarea = document.querySelector('[data-feature-form] textarea[name=descricao]');
                    textarea.value = %s;
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                })()''' % json.dumps(description))
                self.assertEqual(js('document.querySelectorAll("[data-markdown] img[onerror], [data-markdown] a[href^=javascript], [data-markdown] script").length'), 0)
                self.assertEqual(js('document.querySelectorAll("[data-markdown] strong, [data-markdown] a[href=\\"https://example.org\\"]").length'), 2)
                js('window.renderBonfireMarkdown = undefined; document.querySelector("[data-feature-form] textarea[name=descricao]").dispatchEvent(new Event("input", {bubbles:true}))')
                self.assertEqual(js('document.querySelectorAll("[data-markdown] img, [data-markdown] a, [data-markdown] script").length'), 0)
                self.assertTrue(js('document.querySelector("[data-markdown]").textContent.includes("<img src=x")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                call('Emulation.clearDeviceMetricsOverride')
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-feature-card]") !== null')
                self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                self.assertEqual(js('visualViewport.scale'), 1)
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                self.assertTrue(js('document.querySelector("[data-progression-table]") !== null'))
                js('''window.qaForm=document.querySelector('[data-feature-form]');
                    window.qaEdit=document.querySelector('[data-feature-edit]');
                    window.qaEdit.click();
                    window.qaForm.elements.descricao.value='Rascunho nao salvo';
                    window.qaForm.elements.descricao.dispatchEvent(new Event('input'));
                    window.qaForm.elements.descricao.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));''')
                self.assertFalse(js('window.qaForm.classList.contains("is-open")'))
                self.assertEqual(js('window.qaForm.elements.descricao.value'), description)
                self.assertTrue(js('document.querySelector("[data-markdown]").textContent.includes("Destaque")'))
                self.assertTrue(js('document.activeElement===window.qaEdit'))
                js('''window.qaEdit.click();
                    window.qaForm.elements.descricao.value='Outro rascunho';
                    window.qaForm.elements.descricao.dispatchEvent(new Event('input'));
                    window.qaForm.querySelector('[data-feature-cancel]').click();''')
                self.assertEqual(js('window.qaForm.elements.descricao.value'), description)
                self.assertTrue(js('document.activeElement===window.qaEdit'))
                js('''window.qaEdit.click();
                    window.qaForm.elements.descricao.value='Rascunho para nova tentativa';
                    window.qaForm.elements.descricao.dispatchEvent(new Event('input'));
                    window.qaFetch=window.fetch;window.qaCalls=0;
                    window.fetch=()=>{window.qaCalls++;return new Promise(resolve=>window.qaResolve=resolve)};
                    window.qaForm.requestSubmit();''')
                wait_for('window.qaForm.getAttribute("aria-busy") === "true"')
                js('window.qaForm.dispatchEvent(new Event("submit",{cancelable:true}))')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertTrue(js('window.qaForm.querySelector("[data-feature-cancel]").disabled'))
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}),{status:503,headers:{"Content-Type":"application/json"}}))')
                wait_for('window.qaForm.getAttribute("aria-busy") !== "true"')
                self.assertIn('Falha temporaria', js('window.qaForm.querySelector(".wiki-inline-error").textContent'))
                self.assertTrue(js('document.activeElement===window.qaForm.querySelector(".wiki-inline-error")'))
                self.assertEqual(js('window.qaForm.elements.descricao.value'), 'Rascunho para nova tentativa')
                feature.refresh_from_db()
                self.assertEqual(feature.descricao, description)
                js('window.fetch=window.qaFetch;window.qaForm.querySelector("[data-feature-cancel]").click()')
                self.assertEqual(js('window.qaForm.elements.descricao.value'), description)
                call('Emulation.setEmulatedMedia', {
                    'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}],
                })
                self.assertTrue(js('matchMedia("(prefers-reduced-motion: reduce)").matches'))
                self.assertEqual(js('document.querySelectorAll("[data-subclass-toggle]")[0].getAttribute("aria-pressed")'), 'true')
                self.assertEqual(js('document.querySelector("[data-subclass-toggle=trilha-do-fogo]").getAttribute("aria-pressed")'), 'false')
                js('document.querySelectorAll("[data-subclass-toggle]")[0].focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                self.assertEqual(js('document.activeElement?.dataset.subclassToggle'), 'trilha-do-fogo')
                self.assertNotEqual(js('getComputedStyle(document.activeElement).outlineStyle'), 'none')
                self.assertEqual(js('getComputedStyle(document.activeElement).transitionDuration'), '0s')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                wait_for('new URLSearchParams(location.search).get("subclasse") === "trilha-do-fogo"')
                self.assertEqual(js('document.querySelector("[data-subclass-toggle=trilha-do-fogo]").getAttribute("aria-pressed")'), 'true')
                self.assertEqual(js('document.querySelectorAll("[data-subclass-toggle]")[0].getAttribute("aria-pressed")'), 'false')
                self.assertTrue(js('document.querySelector("[data-subclass-anchor]") !== null'))
                self.assertEqual(js('getComputedStyle(document.querySelector("[data-subclass-anchor]")).animationName'), 'none')
                js('document.querySelector("[data-feature-edit]").click()')
                self.assertTrue(js('document.querySelector("[data-feature-form]").getBoundingClientRect().right <= document.documentElement.clientWidth'))
                js('''(() => {
                    const form = document.querySelector('[data-feature-form]');
                    form.elements.descricao.value = '## Revisao em zoom\\nConteudo salvo.';
                    form.elements.descricao.dispatchEvent(new Event('input', { bubbles: true }));
                    form.requestSubmit();
                })()''')
                wait_for('!document.querySelector("[data-feature-form]").classList.contains("is-open")')
                self.assertTrue(js('document.querySelector("[data-markdown]").textContent.includes("Conteudo salvo.")'))
                feature.refresh_from_db()
                self.assertEqual(feature.descricao, '## Revisao em zoom\nConteudo salvo.')
                js('''document.querySelector('[data-feature-edit]').click();
                    const form=document.querySelector('[data-feature-form]');
                    form.elements.descricao.value='Rascunho posterior';
                    form.elements.descricao.dispatchEvent(new Event('input'));
                    form.querySelector('[data-feature-cancel]').click();''')
                self.assertEqual(js('document.querySelector("[data-feature-form]").elements.descricao.value'), '## Revisao em zoom\nConteudo salvo.')
                self.assertTrue(js('document.querySelector("[data-markdown]").textContent.includes("Conteudo salvo.")'))
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-feature-card] [data-markdown] h4") !== null')
                self.assertTrue(js('document.querySelector("[data-feature-card] [data-markdown]").textContent.includes("Conteudo salvo.")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
