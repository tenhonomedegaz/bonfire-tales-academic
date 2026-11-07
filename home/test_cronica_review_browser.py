"""Browser QA for Chronicle review feedback and request recovery."""

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
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from home.models import TbCronica


class ChronicleReviewBrowserTests(StaticLiveServerTestCase):
    def test_review_retry_at_real_200_percent_zoom(self):
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

        author = get_user_model().objects.create_user('chronicle-qa-author', password='test-pass')
        staff = get_user_model().objects.create_user('chronicle-qa-reviewer', password='test-pass', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home',
        ))
        staff.user_permissions.add(Permission.objects.get(
            codename='triage_tbcronica', content_type__app_label='home',
        ))
        story = TbCronica.objects.create(
            titulo='Revisao de QA', slug='revisao-de-qa',
            conteudo_markdown='Texto para revisao', autor=author, status='pendente',
        )
        self.client.force_login(staff)
        with tempfile.TemporaryDirectory(prefix='bonfire-chronicle-review-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({'partition': {
                'default_zoom_level': {'x': math.log(2) / math.log(1.2)},
            }}), encoding='utf-8')
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-first-run', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=800,900', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
                port = None
                for _ in range(80):
                    try:
                        port = port_file.read_text(encoding='utf-8').splitlines()[0]
                        break
                    except (FileNotFoundError, PermissionError, IndexError):
                        time.sleep(.1)
                self.assertIsNotNone(port, 'Browser debugging port unavailable.')
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
                        'expression': expression, 'returnByValue': True, 'awaitPromise': True,
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
                call('Page.navigate', {'url': self.live_server_url + reverse('cronicas_review')})
                until('document.readyState === "complete" && !!document.querySelector(".review-item-actions")')
                metrics = json.loads(js('JSON.stringify({outer:outerWidth,dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                self.assertEqual(metrics['outer'], 800, metrics)
                self.assertAlmostEqual(metrics['dpr'], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics['scale'], 1, metrics)
                self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                for width in (360, 768, 1280, 1920):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width * 2, 'height': 800,
                        'deviceScaleFactor': 1, 'mobile': False,
                    })
                    viewport = json.loads(js('JSON.stringify({width:innerWidth,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                    self.assertEqual(viewport['width'], width, viewport)
                    self.assertLessEqual(viewport['scroll'], viewport['client'], viewport)
                call('Emulation.clearDeviceMetricsOverride')
                self.assertTrue(js('document.querySelector(".review-feedback-label").control === document.querySelector(".review-feedback-input")'))
                self.assertTrue(js('document.querySelector(".review-item-actions").textContent.includes("Encaminhar ao Loremaster")'))

                js(f'reviewAction({story.pk}, "reprovar")')
                self.assertTrue(js('!document.querySelector(".review-item-error").hidden'))
                self.assertTrue(js('document.activeElement.classList.contains("review-feedback-input")'))
                story.refresh_from_db()
                self.assertEqual(story.status, 'pendente')

                js('''window.qaFetch = window.fetch; window.qaCalls = 0;
                    window.fetch = () => { window.qaCalls++; return new Promise(resolve => { window.qaResolve = resolve; }); };
                    document.querySelector('.review-feedback-input').value = '  Corrija o texto.  ';
                    document.querySelector('.review-btn-reject').click();''')
                until('document.querySelector(".review-btn-reject").disabled')
                js(f'reviewAction({story.pk}, "reprovar")')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertEqual(js('document.querySelector(".review-item").getAttribute("aria-busy")'), 'true')
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}), {status:503,headers:{"Content-Type":"application/json"}}))')
                until('!document.querySelector(".review-btn-reject").disabled')
                self.assertIn('Falha temporaria', js('document.querySelector(".review-item-error").textContent'))
                self.assertEqual(js('document.querySelector(".review-feedback-input").value'), '  Corrija o texto.  ')
                story.refresh_from_db()
                self.assertEqual(story.status, 'pendente')

                js('window.fetch = window.qaFetch; document.querySelector(".review-btn-reject").click()')
                until('document.querySelector(".review-item").classList.contains("is-resolved")')
                self.assertEqual(js('document.querySelector("#reviewPendingSummary").dataset.count'), '0')
                story.refresh_from_db()
                self.assertEqual(story.status, 'reprovada')
                self.assertEqual(story.feedback_staff, 'Corrija o texto.')

                forwarded = TbCronica.objects.create(
                    titulo='Lore para conferir', slug='lore-para-conferir',
                    conteudo_markdown='Texto da lore', autor=author, status='pendente',
                )
                call('Page.navigate', {'url': self.live_server_url + reverse('cronicas_review')})
                until('document.readyState === "complete" && !!document.querySelector(".review-item-actions")')
                js('''document.querySelector('.review-feedback-input').value = 'Verificar a cronologia';
                    Array.from(document.querySelectorAll('.review-item-actions button'))
                      .find(button => button.textContent.includes('Encaminhar ao Loremaster')).click();''')
                until('!!document.body && document.body.textContent.includes("Encaminhada ao Loremaster: Verificar a cronologia")')
                forwarded.refresh_from_db()
                self.assertEqual(forwarded.status, 'pendente')
                self.assertEqual(forwarded.revisao_edicao['triagem_lore']['motivo'], 'Verificar a cronologia')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 720, 'height': 800, 'deviceScaleFactor': 1, 'mobile': False,
                })
                forwarded_view = json.loads(js('JSON.stringify({width:innerWidth,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                self.assertEqual(forwarded_view['width'], 360, forwarded_view)
                self.assertLessEqual(forwarded_view['scroll'], forwarded_view['client'], forwarded_view)
                call('Emulation.clearDeviceMetricsOverride')
                self.client.logout()
                self.assertEqual(self.client.get(reverse('cronica_detail', args=[story.slug])).status_code, 404)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
