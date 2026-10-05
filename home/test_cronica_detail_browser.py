"""Browser QA for public Chronicle comments and reply deep links."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from home.models import TbCronica, TbCronicaComentario


class ChronicleDetailBrowserTests(StaticLiveServerTestCase):
    def test_comment_pages_and_old_reply_link_fit_mobile_and_desktop(self):
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

        author = get_user_model().objects.create_user('chronicle-detail-browser')
        story = TbCronica.objects.create(
            titulo='Crônica navegável', slug='cronica-navegavel-browser',
            conteudo_markdown='Texto da crônica', autor=author, status='aprovada',
        )
        old = TbCronicaComentario.objects.create(
            cronica=story, autor=author, texto='Primeiro comentário', chave_operacao=uuid4(),
        )
        reply = TbCronicaComentario.objects.create(
            cronica=story, autor=author, resposta_a=old,
            texto='Resposta antiga', chave_operacao=uuid4(),
        )
        TbCronicaComentario.objects.bulk_create([
            TbCronicaComentario(
                cronica=story, autor=author, texto=f'Comentário recente {number}',
                chave_operacao=uuid4(),
            ) for number in range(22)
        ])
        detail = self.live_server_url + reverse('cronica_detail', args=[story.slug])
        with tempfile.TemporaryDirectory(prefix='bonfire-chronicle-detail-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-first-run', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=390,900', 'about:blank',
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

                call('Page.enable')
                for width in (390, 1280):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 900,
                        'deviceScaleFactor': 1, 'mobile': False,
                    })
                    call('Page.navigate', {'url': detail})
                    until('document.readyState === "complete" && !!document.querySelector(".cronica-comments-pages")')
                    metrics = json.loads(js('JSON.stringify({width:innerWidth,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                    self.assertEqual(metrics['width'], width, metrics)
                    self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                    self.assertTrue(js('document.querySelector(".cronica-comments-pages a[href*=" + JSON.stringify("comentarios_page=2") + "]") !== null'))
                    call('Page.navigate', {'url': detail + f'?comentario={reply.pk}#comentario-{reply.pk}'})
                    until(f'document.readyState === "complete" && !!document.getElementById("comentario-{reply.pk}")')
                    self.assertTrue(js(f'document.getElementById("comentario-{reply.pk}").getBoundingClientRect().width > 0'))
                    self.assertTrue(js('document.querySelector(".cronica-comments-pages").textContent.includes("Página 2")'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
