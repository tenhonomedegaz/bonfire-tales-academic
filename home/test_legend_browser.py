"""Visual check of the public Legend memorial with a local Edge browser."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class LegendBrowserTests(unittest.TestCase):
    def test_memorial_reads_and_opens_sheet_at_mobile_and_desktop_widths(self):
        import django
        from django.conf import settings

        if not settings.configured:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
            os.environ.setdefault('DJANGO_DEBUG', '1')
            os.environ.setdefault('DB_ENGINE', 'postgresql')
            django.setup()

        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponivel')

        edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
        if not edge.is_file():
            self.skipTest('Edge indisponivel')

        from django.template.loader import render_to_string
        from django.urls import reverse

        sheet_path = reverse('ficha_publica', args=[42])
        memorial_path = reverse('personagem_lenda', args=[42])
        page = render_to_string('home/pages/lenda.html', {
            'character': {
                'pk': 42, 'nome': 'A Guardiã da Aurora', 'dono': 'aventureira',
                'raca': 'Humana', 'classe': 'Guerreira', 'foto_url': '',
                'descricao': 'Sua história atravessou muitos invernos.',
            },
            'rank': {'nome': 'Diamante', 'titulo': 'Lenda', 'is_lenda': True,
                     'icone_url': '/static/brand/icon.png'},
            'feitos': [{
                'titulo': 'A travessia da ponte de cristal',
                'descricao': 'Salvou a cidade e reuniu seus aliados diante da tempestade.',
                'data': date(2026, 10, 1),
            }],
        })

        class Handler(SimpleHTTPRequestHandler):
            def handle(self):
                try:
                    super().handle()
                except ConnectionResetError:
                    pass

            def do_GET(self):
                if self.path == memorial_path:
                    body = page.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == sheet_path:
                    body = b'<html><body><h1>Ficha publica</h1></body></html>'
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path.startswith('/static/'):
                    self.path = '/home/static/' + self.path.removeprefix('/static/')
                    super().do_GET()
                else:
                    self.send_error(404)

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with tempfile.TemporaryDirectory(prefix='bonfire-legend-', ignore_cleanup_errors=True) as scratch:
                profile = Path(scratch) / 'profile'
                process = subprocess.Popen([
                    str(edge), '--headless=new', '--no-first-run', '--no-sandbox',
                    '--disable-gpu', '--remote-debugging-port=0',
                    '--remote-allow-origins=*', f'--user-data-dir={profile}',
                    'about:blank',
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ws = None
                try:
                    port_file = profile / 'DevToolsActivePort'
                    for _ in range(80):
                        if port_file.is_file():
                            break
                        time.sleep(.1)
                    self.assertTrue(port_file.is_file(), 'Edge nao iniciou')
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
                    for width in (360, 1280):
                        call('Emulation.setDeviceMetricsOverride', {
                            'width': width, 'height': 900,
                            'deviceScaleFactor': 1, 'mobile': False,
                        })
                        call('Page.navigate', {'url': origin + memorial_path})
                        until('document.readyState === "complete" && !!document.querySelector(".bf-legacy-feats li")')
                        metrics = js('''(() => {
                          const hero = document.querySelector('.bf-legacy-hero').getBoundingClientRect();
                          const layout = document.querySelector('.bf-legacy-layout');
                          const feat = document.querySelector('.bf-legacy-feats li').getBoundingClientRect();
                          const featBody = document.querySelector('.bf-legacy-feats li p');
                          const bodyBox = featBody.getBoundingClientRect();
                          const link = document.querySelector('.bf-legacy-story .bf-legacy-link');
                          return {
                            width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                            heroRight: hero.right, featRight: feat.right,
                            bodyRight: bodyBox.right, bodyHeight: bodyBox.height,
                            bodyFontSize: parseFloat(getComputedStyle(featBody).fontSize),
                            heroDisplay: getComputedStyle(document.querySelector('.bf-legacy-hero')).display,
                            layoutColumns: getComputedStyle(layout).gridTemplateColumns.split(' ').length,
                            featText: document.querySelector('.bf-legacy-feats').innerText,
                            linkVisible: link.getBoundingClientRect().width > 0,
                            linkHref: link.getAttribute('href'),
                          };
                        })()''')
                        self.assertEqual(metrics['width'], width, metrics)
                        self.assertLessEqual(metrics['scrollWidth'], width, metrics)
                        self.assertLessEqual(metrics['heroRight'], width, metrics)
                        self.assertLessEqual(metrics['featRight'], width, metrics)
                        self.assertLessEqual(metrics['bodyRight'], width, metrics)
                        self.assertGreater(metrics['bodyHeight'], 0, metrics)
                        self.assertGreaterEqual(metrics['bodyFontSize'], 13, metrics)
                        self.assertEqual(metrics['heroDisplay'], 'grid', metrics)
                        self.assertEqual(metrics['layoutColumns'], 1 if width == 360 else 2, metrics)
                        self.assertIn('A travessia da ponte de cristal', metrics['featText'])
                        self.assertIn('Salvou a cidade', metrics['featText'])
                        self.assertTrue(metrics['linkVisible'], metrics)
                        self.assertEqual(metrics['linkHref'], sheet_path)
                        js("document.querySelector('.bf-legacy-story .bf-legacy-link').click()")
                        until(f'location.pathname === {json.dumps(sheet_path)}')
                finally:
                    if ws:
                        ws.close()
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
