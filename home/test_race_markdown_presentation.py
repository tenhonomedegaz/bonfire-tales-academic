"""Leitura e previa editorial de Markdown no detalhe de Racas."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbEssencia, TbLinhagem, TbRaca, TbTracoracial


class RaceMarkdownPresentationTests(StaticLiveServerTestCase):
    def test_lore_and_inline_preview_are_safe_on_mobile(self):
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

        description = '**Destaque** <img src=x onerror=alert(1)> [perigo](javascript:alert(1)) [referencia](https://example.org)'
        race = TbRaca.objects.create(
            nome='Raca Editorial', slug='raca-editorial', lore_presentation=description,
            permite_essencia=True,
            imagem_url="https://example.org/race.png');color:red;--evil:'",
        )
        TbRaca.objects.create(nome='Coração de Brasa', slug='coracao-brasa', tagline='Chama antiga')
        TbLinhagem.objects.create(
            id_raca=race, nome='Linhagem Legada', slug='linhagem-legada',
            imagem_url='javascript:alert(1)', imagem_foco_x=19, imagem_foco_y=72,
        )
        elf = TbRaca.objects.create(nome='Elfo', slug='elfo')
        for slug, name in (
            ('aetherin', 'Aetherin'), ('lunareth', 'Lunareth'),
            ('noctelar', 'Noctelar'), ('solariin', 'Solariin'),
            ('sylvanar', 'Sylvanar'),
        ):
            TbLinhagem.objects.create(id_raca=elf, nome=name, slug=slug)
        TbEssencia.objects.create(
            nome='Essencia Visual', slug='essencia-visual',
            imagem_url='https://example.org/essence.png',
            imagem_foco_x=81, imagem_foco_y=14,
        )
        TbTracoracial.objects.create(id_raca=race, nome='Traco Editorial', descricao=description)
        editor = get_user_model().objects.create_superuser('race-editor-md', 'race-editor@example.invalid', 'test-pass')
        self.client.force_login(editor)

        with tempfile.TemporaryDirectory(prefix='bonfire-race-md-', ignore_cleanup_errors=True) as profile:
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
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result']
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
                url = self.live_server_url + reverse('raca_detail', args=[race.slug])
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-race-trait-card] [data-markdown-source] strong") !== null')
                js('document.querySelector("#raceNav details").open = false')
                js('''(() => {
                    const input = document.querySelector('#raceSearch');
                    input.value = 'coracao';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                })()''')
                self.assertEqual(js('Array.from(document.querySelectorAll("#raceNav .race-nav-item:not(.hidden)")).map(item => item.textContent.trim())'), ['Coração de Brasa'])
                self.assertTrue(js('document.querySelector("#raceNav details").open'))
                js('''(() => {
                    const input = document.querySelector('#raceSearch');
                    input.value = 'inexistente';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                })()''')
                self.assertEqual(js('document.querySelectorAll("#raceNav .race-nav-item:not(.hidden)").length'), 0)
                self.assertFalse(js('document.querySelector("#raceSearchEmpty").classList.contains("hidden")'))
                js('''(() => {
                    const input = document.querySelector('#raceSearch');
                    input.value = 'chama';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    document.querySelector('#raceNav .race-nav-item:not(.hidden)').click();
                })()''')
                wait_for('location.pathname.endsWith("/coracao-brasa/") && document.querySelector("[data-race-title]")?.textContent === "Coração de Brasa"')
                js('history.back()')
                wait_for('location.pathname.endsWith("/raca-editorial/") && document.querySelector("[data-race-title]")?.textContent === "Raca Editorial"')
                self.assertEqual(js('document.querySelector("#raceSearch").value'), '')
                self.assertTrue(js('document.querySelector("#raceSearchEmpty").classList.contains("hidden")'))
                call('Page.navigate', {'url': self.live_server_url + reverse('racas')})
                wait_for('document.querySelector("#ajax-content-inner h1")?.textContent === "Povos de Cinéria"')
                js('document.querySelector("#raceNav .race-nav-item").click()')
                wait_for('location.pathname.endsWith("/coracao-brasa/") && document.querySelector("[data-race-title]")?.textContent === "Coração de Brasa"')
                js('history.back()')
                wait_for('location.pathname === "/jogador/raca/" && document.querySelector("#ajax-content-inner h1")?.textContent === "Povos de Cinéria"')
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-race-title]")?.textContent === "Raca Editorial"')
                self.assertTrue(js('document.querySelector("#baseRaceLore [data-markdown-source] strong") !== null'))
                self.assertEqual(js('document.querySelectorAll("[data-markdown-source] img[onerror], [data-markdown-source] a[href^=javascript], [data-markdown-source] script").length'), 0)
                self.assertEqual(js('document.querySelectorAll("[data-markdown-source] a[href=\\"https://example.org\\"]").length'), 2)
                self.assertTrue(js('document.querySelector("[data-markdown-source]").dataset.markdownManual === "true"'))
                self.assertTrue(js('document.querySelector("#racePreviewImage").style.backgroundImage.includes("%27")'))
                self.assertEqual(js('document.querySelector("#racePreviewImage").style.getPropertyValue("color")'), '')
                self.assertEqual(js('document.querySelector("#racePreviewImage").style.getPropertyValue("--evil")'), '')
                js('''(() => {
                    const select = document.querySelector('#linhagemSelect');
                    select.value = 'linhagem-legada';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                })()''')
                self.assertTrue(js('document.querySelector("#racePreviewImage").style.backgroundImage.includes("race.png")'))
                self.assertEqual(js('document.querySelector("#racePreviewImage").style.backgroundPosition'), '50% 50%')
                js('''(() => {
                    const select = document.querySelector('#essenciaSelect');
                    select.value = 'essencia-visual';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                })()''')
                self.assertTrue(js('document.querySelector("#racePreviewImage").style.backgroundImage.includes("essence.png")'))
                self.assertEqual(js('document.querySelector("#racePreviewImage").style.backgroundPosition'), '81% 14%')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': url})
                wait_for('document.querySelector("[data-trait-edit]") !== null')
                js('document.querySelector("[data-trait-edit]").click()')
                js('''(() => {
                    const textarea = document.querySelector('[data-trait-form] textarea[name=descricao]');
                    textarea.value = %s;
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                })()''' % json.dumps(description))
                self.assertEqual(js('document.querySelectorAll("[data-trait-preview] img[onerror], [data-trait-preview] a[href^=javascript]").length'), 0)
                self.assertTrue(js('document.querySelector("[data-trait-preview] strong") !== null'))
                js('window.renderBonfireMarkdown = undefined; document.querySelector("[data-trait-form] textarea[name=descricao]").dispatchEvent(new Event("input", {bubbles:true}))')
                self.assertEqual(js('document.querySelectorAll("[data-trait-preview] img, [data-trait-preview] a").length'), 0)
                self.assertTrue(js('document.querySelector("[data-trait-preview] [data-markdown-source]").textContent.includes("<img src=x")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                with patch('home.views._criador_hunter_catalog_args', return_value={}):
                    call('Page.navigate', {'url': self.live_server_url + reverse('criacao_ficha')})
                    wait_for('document.querySelector("#cf-raca option[value=elfo]") !== null')
                js('''(() => { const select = document.querySelector('#cf-raca');
                    select.value = 'elfo'; select.dispatchEvent(new Event('change', {bubbles: true})); })()''')
                elf_options = js('''({hidden:document.querySelector('#cf-linhagem-wrap').hidden,
                    slugs:[...document.querySelectorAll('#cf-linhagem option')].map(option => option.value).filter(Boolean)})''')
                self.assertFalse(elf_options['hidden'], elf_options)
                self.assertEqual(elf_options['slugs'],
                                 ['aetherin', 'lunareth', 'noctelar', 'solariin', 'sylvanar'])
                call('Page.navigate', {'url': self.live_server_url + reverse('pathbuilder')})
                wait_for('document.querySelector("#cf-raca option[value=elfo]") !== null')
                js('''(() => { const select = document.querySelector('#cf-raca');
                    select.value = 'elfo'; select.dispatchEvent(new Event('change', {bubbles: true})); })()''')
                self.assertEqual(js('''[...document.querySelectorAll('#cf-linhagem option')]
                    .map(option => option.value).filter(Boolean)'''), elf_options['slugs'])
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
