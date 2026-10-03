"""Browser QA for the mundane and magic item catalogue editors."""

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

from home.models import TbItemMagico, TbItemMundano


class ItemEditorRecoveryTests(StaticLiveServerTestCase):
    def test_both_catalogues_cancel_recover_and_publish_at_real_zoom(self):
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

        mundane = TbItemMundano.objects.create(
            nome='Corda Editorial', slug='corda-editorial',
            categoria='equipamento_aventura', descricao_markdown='Texto publicado',
        )
        magic = TbItemMagico.objects.create(
            nome='Anel Editorial', slug='anel-editorial',
            raridade='incomum', slot='aneis', descricao_markdown='Texto publicado',
        )
        editor = get_user_model().objects.create_superuser(
            'item-editor', 'item-editor@example.invalid', 'test-pass',
        )
        self.client.force_login(editor)
        with tempfile.TemporaryDirectory(prefix='bonfire-item-editor-', ignore_cleanup_errors=True) as scratch:
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
                port_file = profile / 'DevToolsActivePort'
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
                        response = json.loads(ws.recv())
                        if response.get('id') == sequence:
                            self.assertNotIn('error', response, method)
                            return response['result']

                def js(expression):
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def until(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.enable')

                for item, route, revised in (
                    (mundane, 'mercado_itens_mundanos', 'Corda Revisada'),
                    (magic, 'mercado_itens_magicos', 'Anel Revisado'),
                ):
                    with self.subTest(route=route):
                        url = self.live_server_url + reverse(route)
                        call('Page.navigate', {'url': url})
                        until('document.readyState==="complete" && !!document.querySelector("[data-shop-detail] [data-item-editor]")')
                        self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                        self.assertEqual(js('visualViewport.scale'), 1)
                        self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                        js('document.querySelector("[data-mkt-row]").click()')
                        self.assertTrue(js('document.querySelector("[data-shop-root]").classList.contains("is-sheet-open")'))
                        js('''window.qaDetails=document.querySelector('[data-shop-detail] .mkt-inline-editor');
                            window.qaForm=window.qaDetails.querySelector('[data-item-editor]');
                            window.qaDetails.querySelector('summary').click();
                            window.qaForm.elements.descricao_markdown.value='Rascunho cancelado';
                            window.qaForm.elements.descricao_markdown.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));''')
                        self.assertFalse(js('window.qaDetails.open'))
                        self.assertEqual(js('window.qaForm.elements.descricao_markdown.value'), 'Texto publicado')
                        self.assertTrue(js('document.activeElement===window.qaDetails.querySelector("summary")'))
                        js('''window.qaDetails.querySelector('summary').click();
                            window.qaForm.elements.descricao_markdown.value='Outro rascunho';
                            window.qaForm.querySelector('[data-item-editor-cancel]').click();''')
                        self.assertEqual(js('window.qaForm.elements.descricao_markdown.value'), 'Texto publicado')

                        js('''window.qaDetails.querySelector('summary').click();
                            window.qaForm.elements.nome.value='Nome revisado';
                            window.qaForm.elements.descricao_markdown.value='Texto revisado';
                            window.qaFetch=window.fetch;window.qaCalls=0;
                            window.fetch=()=>{window.qaCalls++;return new Promise(resolve=>window.qaResolve=resolve)};
                            window.qaForm.requestSubmit();''')
                        until('window.qaForm.getAttribute("aria-busy")==="true"')
                        js('window.qaForm.dispatchEvent(new Event("submit",{cancelable:true,bubbles:true}))')
                        self.assertEqual(js('window.qaCalls'), 1)
                        self.assertTrue(js('window.qaForm.querySelector("[data-item-editor-cancel]").disabled'))
                        js('window.qaDetails.querySelector("summary").click()')
                        self.assertTrue(js('window.qaDetails.open'))
                        js('window.qaResolve(new Response("Falha temporaria",{status:503}))')
                        until('window.qaForm.getAttribute("aria-busy")!=="true"')
                        self.assertIn('Falha temporaria', js('window.qaForm.querySelector("[data-item-editor-status]").textContent'))
                        self.assertTrue(js('document.activeElement===window.qaForm.querySelector("[data-item-editor-status]")'))
                        self.assertEqual(js('window.qaForm.elements.descricao_markdown.value'), 'Texto revisado')
                        item.refresh_from_db()
                        self.assertEqual(item.descricao_markdown, 'Texto publicado')

                        js('''window.fetch=window.qaFetch;
                            window.qaForm.elements.slug.value='Slug invalido';
                            window.qaForm.requestSubmit();''')
                        until('window.qaForm.querySelector("[data-item-editor-status]").textContent.includes("slug")')
                        self.assertEqual(js('window.qaForm.querySelector("[data-item-editor-status]").getAttribute("role")'), 'alert')
                        self.assertEqual(js('window.qaForm.elements.descricao_markdown.value'), 'Texto revisado')
                        item.refresh_from_db()
                        self.assertEqual(item.descricao_markdown, 'Texto publicado')
                        js('window.qaForm.elements.slug.value=%s;window.qaForm.elements.nome.value=%s;window.qaForm.requestSubmit()' % (
                            json.dumps(item.slug), json.dumps(revised),
                        ))
                        until('new URLSearchParams(location.search).get("editado")===%s' % json.dumps(item.slug))
                        item.refresh_from_db()
                        self.assertEqual(item.nome, revised)
                        self.assertEqual(item.descricao_markdown, 'Texto revisado')
                        until('document.querySelector("[data-shop-detail]")?.textContent.includes("Texto revisado")')
                        self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))

                        # A descrição editorial é clonada do template ao selecionar o item.
                        # O HTML gerado deve passar pelo mesmo sanitizador da leitura comum.
                        item.descricao_markdown = (
                            '**Seguro** <img src="x" onerror="window.__marketInjected=1"> '
                            '<svg onload="window.__marketInjected=1"></svg> '
                            '[ruim](javascript:alert(1)) [bom](https://example.org)'
                        )
                        item.save(update_fields=['descricao_markdown'])
                        call('Page.navigate', {'url': url})
                        until('document.readyState==="complete" && !!document.querySelector("[data-shop-detail] .mkt-desc")')
                        self.assertTrue(js('!!document.querySelector("[data-shop-detail] .mkt-desc strong")'))
                        self.assertTrue(js('!!Array.from(document.querySelectorAll("[data-shop-detail] .mkt-desc a")).find(a=>a.href==="https://example.org/")'))
                        self.assertFalse(js('!!document.querySelector("[data-shop-detail] .mkt-desc [onerror], [data-shop-detail] .mkt-desc svg, [data-shop-detail] .mkt-desc a[href^=javascript]")'))
                        self.assertFalse(js('window.__marketInjected===1'))
                        js('''window.renderBonfireMarkdownElement=undefined;
                            document.querySelector('[data-mkt-row]').click();''')
                        self.assertTrue(js('document.querySelector("[data-shop-detail] .mkt-desc").textContent.includes("**Seguro**")'))
                        self.assertFalse(js('!!document.querySelector("[data-shop-detail] .mkt-desc strong, [data-shop-detail] .mkt-desc img")'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
