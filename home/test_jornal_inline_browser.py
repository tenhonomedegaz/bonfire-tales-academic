"""Real browser coverage for the Jornal's inline layout and publication editor."""

import base64
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone

from home.models import TbJornal


class JornalInlineBrowserTests(StaticLiveServerTestCase):
    def test_layout_and_date_save_and_stale_form_keeps_edits(self):
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponivel')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponivel')

        editor = get_user_model().objects.create_user('jornal-inline-browser', password='test', is_staff=True)
        editor.user_permissions.add(Permission.objects.get(
            codename='change_tbjornal', content_type__app_label='home',
        ))
        original_date = timezone.make_aware(datetime(2024, 4, 15, 10, 30, 47))
        article = TbJornal.objects.create(
            titulo='Jornal no navegador', slug='jornal-no-navegador',
            layout='padrao', conteudo_markdown='Texto publicado', data_publicacao=original_date,
        )
        self.client.force_login(editor)

        with tempfile.TemporaryDirectory(prefix='bonfire-jornal-inline-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-first-run', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=1280,900', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
                for _ in range(80):
                    if port_file.is_file():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.is_file())
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
                        'expression': expression, 'returnByValue': True, 'awaitPromise': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def until(expression):
                    for _ in range(100):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Tempo esgotado: {expression}')

                def open_editor():
                    js("document.querySelector('#btnEditArticle').click()")
                    until("document.querySelector('#articleForm').classList.contains('is-open')")

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.enable')
                detail_url = self.live_server_url + reverse('jornal_detail', args=[article.slug])
                call('Page.navigate', {'url': detail_url})
                until("document.readyState === 'complete' && !!document.querySelector('#articleForm')")
                self.assertTrue(js("document.querySelector('.artigo-hero').classList.contains('artigo-hero--text')"))
                self.assertLess(js("document.querySelector('.artigo-hero').getBoundingClientRect().height"), 250)
                self.assertNotIn('Editado em', js("document.querySelector('.artigo-meta').textContent"))
                open_editor()
                self.assertEqual(js("document.querySelector('[name=layout]').value"), 'padrao')
                self.assertEqual(js("document.querySelector('[name=data_publicacao]').value"), '')
                self.assertEqual(js("getComputedStyle(document.querySelector('[name=layout]')).colorScheme"), 'dark')

                # Capture both widths while the new controls are open for visual QA.
                screenshots = Path(settings.BASE_DIR) / 'scratch' / 'jornal-inline-qa'
                screenshots.mkdir(parents=True, exist_ok=True)
                for width in (1280, 360):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False,
                    })
                    data = call('Page.captureScreenshot', {'captureBeyondViewport': True})['data']
                    (screenshots / f'editor-{width}.png').write_bytes(base64.b64decode(data))
                    self.assertTrue(js("document.querySelector('[name=layout]').getBoundingClientRect().width > 0"))
                    self.assertTrue(js("document.querySelector('[name=data_publicacao]').getBoundingClientRect().width > 0"))
                    self.assertTrue(js("document.querySelector('[name=data_publicacao]').getBoundingClientRect().right <= innerWidth"))

                js("document.querySelector('[name=layout]').value = 'colunas'; document.querySelector('#articleForm').requestSubmit()")
                until("document.querySelector('[data-artigo-layout]')?.dataset.artigoLayout === 'colunas'")
                article.refresh_from_db()
                self.assertEqual(article.layout, 'colunas')
                self.assertEqual(article.data_publicacao, original_date)
                self.assertIn('Editado em', js("document.querySelector('.artigo-meta').textContent"))

                open_editor()
                js("document.querySelector('[name=layout]').value = 'atlas'; document.querySelector('[name=data_publicacao]').value = '2024-05-20T12:00'; document.querySelector('#articleForm').requestSubmit()")
                until("document.querySelector('[data-artigo-layout]')?.dataset.artigoLayout === 'atlas'")
                article.refresh_from_db()
                self.assertEqual(article.layout, 'atlas')
                self.assertEqual(timezone.localtime(article.data_publicacao).replace(tzinfo=None),
                                 datetime(2024, 5, 20, 12, 0))
                self.assertIn('Texto publicado', js("document.querySelector('[data-jornal-markdown]').textContent"))

                call('Page.navigate', {'url': self.live_server_url + reverse('mundo_jornal')})
                until("document.readyState === 'complete' && !!document.querySelector('a[href*=jornal-no-navegador]')")
                self.assertIn('2024', js("document.querySelector('a[href*=jornal-no-navegador]').textContent"))
                call('Page.navigate', {'url': detail_url})
                until("document.readyState === 'complete' && !!document.querySelector('#articleForm')")

                open_editor()
                article.layout = 'colunas'
                article.save(update_fields=['layout', 'data_edicao'])
                js("document.querySelector('[name=layout]').value = 'padrao'; document.querySelector('[name=data_publicacao]').value = '2024-06-01T09:00'; document.querySelector('#articleForm').requestSubmit()")
                until("!document.querySelector('#articleSaveError').hidden")
                self.assertEqual(js("document.querySelector('[name=layout]').value"), 'padrao')
                self.assertEqual(js("document.querySelector('[name=data_publicacao]').value"), '2024-06-01T09:00')
                article.refresh_from_db()
                self.assertEqual(article.layout, 'colunas')
                self.assertEqual(timezone.localtime(article.data_publicacao).replace(tzinfo=None),
                                 datetime(2024, 5, 20, 12, 0))

                article.imagem_url = '/static/assets/logo.png'
                article.save(update_fields=['imagem_url'])
                call('Page.navigate', {'url': detail_url})
                until("document.readyState === 'complete' && !!document.querySelector('.artigo-hero')")
                self.assertFalse(js("document.querySelector('.artigo-hero').classList.contains('artigo-hero--text')"))
                until("document.querySelector('.journal-article-figure img')?.naturalWidth > 0")
                self.assertIn(article.titulo, js("document.querySelector('.journal-article-figure img').alt"))
                self.assertLessEqual(js("document.querySelector('.journal-article-figure').getBoundingClientRect().right"),
                                     js('document.documentElement.clientWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
