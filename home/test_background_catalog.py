from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from .models import TbAntecedente


class BackgroundCatalogTests(TestCase):
    def test_rule_summary_is_collapsed_and_repeated_quote_is_shown_once(self):
        quote = 'Uma longa citação que acompanha a história deste antecedente.'
        TbAntecedente.objects.create(
            nome='Viajante', slug='viajante', resumo=quote,
            descricao=f'*"{quote}"*\n\nUma habilidade própria para viajar.',
        )

        response = self.client.get(reverse('jogador_antecedente'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<details class="catalog-intro-box">')
        self.assertNotContains(response, '<details class="catalog-intro-box" open')
        markup = response.content.decode('utf-8')
        self.assertLess(markup.index('</details>'), markup.index('</header>'))
        self.assertLess(markup.index('</details>'), markup.index('class="catalog-grid"'))
        self.assertContains(response, 'Regras básicas dos antecedentes')
        self.assertContains(response, 'catalog-title--backgrounds')
        self.assertEqual(response.context['items'][0]['resumo'], '')
        self.assertContains(response, 'Uma habilidade própria para viajar.')

    def test_distinct_summary_is_preserved(self):
        TbAntecedente.objects.create(
            nome='Artesão', slug='artesao',
            resumo='Conhece as tradições de sua guilda.',
            descricao='Seu ofício abre portas na cidade.',
        )

        response = self.client.get(reverse('jogador_antecedente'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['items'][0]['resumo'], 'Conhece as tradições de sua guilda.')
        self.assertContains(response, 'Conhece as tradições de sua guilda.')


class BackgroundCatalogBrowserTests(StaticLiveServerTestCase):
    def test_direct_link_selection_search_and_history_on_mobile(self):
        import json
        import math
        import shutil
        import subprocess
        import tempfile
        import time
        from pathlib import Path
        from urllib.request import urlopen
        from django.db import connection

        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponível.')

        for name, slug, kind in [('Artesão', 'artesao', 'Ofício'), ('Eremita', 'eremita', 'Retiro'), ('Viajante', 'viajante', 'Ofício')]:
            TbAntecedente.objects.create(nome=name, slug=slug, tipo=kind, descricao=f'História de {name}.')

        with tempfile.TemporaryDirectory(prefix='bonfire-backgrounds-', ignore_cleanup_errors=True) as scratch:
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
                self.assertTrue(port_file.exists())
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=10)
                sequence = 0

                def js(expression):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': 'Runtime.evaluate', 'params': {
                        'expression': expression, 'returnByValue': True,
                    }}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('id') == sequence:
                            self.assertNotIn('exceptionDetails', result['result'], expression)
                            return result['result']['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                sequence += 1
                ws.send(json.dumps({'id': sequence, 'method': 'Emulation.setDeviceMetricsOverride', 'params': {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                }}))
                while json.loads(ws.recv()).get('id') != sequence:
                    pass
                sequence += 1
                ws.send(json.dumps({'id': sequence, 'method': 'Page.navigate', 'params': {
                    'url': self.live_server_url + reverse('jogador_antecedente') + '#artesao',
                }}))
                while json.loads(ws.recv()).get('id') != sequence:
                    pass
                wait_for('document.querySelector(".catalog-detail .detail-title")?.textContent === "Artesão"')
                self.assertEqual(js('document.querySelectorAll(".catalog-card[aria-pressed=true]").length'), 1)
                js('document.querySelector("#catalogMobileMenuButton").click()')
                self.assertTrue(js('document.body.classList.contains("catalog-menu-open")'))
                js('document.querySelector(".catalog-card[data-slug=viajante]").click()')
                wait_for('location.hash === "#viajante" && document.querySelector(".catalog-detail .detail-title")?.textContent === "Viajante"')
                self.assertFalse(js('document.body.classList.contains("catalog-menu-open")'))
                self.assertTrue(js('document.activeElement.classList.contains("detail-title")'))
                js('document.querySelector("#catalogSearch").value = "Eremita"; document.querySelector("#catalogSearch").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelectorAll(".catalog-card").length === 1 && document.querySelector(".detail-title")?.textContent === "Eremita"')
                self.assertTrue(js('location.search.includes("q=Eremita") && location.hash === "#eremita"'))
                js('history.back()')
                wait_for('location.hash === "#artesao" && document.querySelector(".detail-title")?.textContent === "Artesão"')
                self.assertEqual(js('document.querySelector("#catalogSearch").value'), '')
                self.assertEqual(js('location.search'), '')
                js('document.querySelector("#catalogType").value = "Retiro"; document.querySelector("#catalogType").dispatchEvent(new Event("change", {bubbles:true}))')
                wait_for('location.search.includes("tipo=Retiro") && location.hash === "#eremita" && document.querySelector(".detail-title")?.textContent === "Eremita"')
                js('history.back()')
                wait_for('location.hash === "#artesao" && document.querySelector(".detail-title")?.textContent === "Artesão"')
                self.assertEqual(js('document.querySelector("#catalogType").value'), '')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                js('location.assign("?tipo=Retiro#eremita")')
                wait_for('document.querySelector("#catalogType")?.value === "Retiro" && document.querySelector(".detail-title")?.textContent === "Eremita"')
                sequence += 1
                ws.send(json.dumps({'id': sequence, 'method': 'Emulation.clearDeviceMetricsOverride'}))
                while json.loads(ws.recv()).get('id') != sequence:
                    pass
                js('location.assign("' + reverse('jogador_antecedente') + '#artesao")')
                wait_for('document.querySelector(".detail-title")?.textContent === "Artesão"')
                self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                self.assertEqual(js('visualViewport.scale'), 1)
                self.assertFalse(js('document.querySelector(".catalog-intro-box").open'))
                self.assertLess(js('document.querySelector(".catalog-grid").getBoundingClientRect().top'), js('innerHeight'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                js('document.querySelector(".catalog-intro-box summary").click()')
                self.assertTrue(js('document.querySelector(".catalog-intro-box").open'))
                self.assertTrue(js('document.querySelector(".catalog-intro-content").getBoundingClientRect().height > 0'))
                js('document.querySelector(".catalog-intro-box summary").click()')
                self.assertFalse(js('document.querySelector(".catalog-intro-box").open'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
