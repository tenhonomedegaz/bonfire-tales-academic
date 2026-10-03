import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbClasse, TbMagia, TbOpcaojogo, TbTalento


class TalentCatalogPresentationTests(StaticLiveServerTestCase):
    def test_editorial_text_is_literal_and_catalog_still_selects_on_mobile(self):
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

        injected = '<img src=x onerror="window.__talentInjected=1">'
        TbTalento.objects.create(
            nome=f'Arcano {injected}', slug='arcano-literal',
            etiquetas_adicionais=f'Magia, magia., MAGIA, COMBATE, {injected}', pre_requisito=injected,
            descricao=(
                '**Benefício editorial**\n\n'
                '<svg onload="window.__talentInjected=1"></svg>\n\n'
                '<a href="javascript:window.__talentInjected=1">Inseguro</a>'
            ),
        )
        TbTalento.objects.create(nome='Seguro', slug='seguro', etiquetas_adicionais='mágia!', descricao='Texto seguro')
        TbTalento.objects.create(nome='Coração sombrio', slug='coracao-sombrio', descricao='Texto sombrio')
        TbOpcaojogo.objects.create(
            nome='Opcao segura', slug='opcao-segura', tipo='Teste',
            etiquetas_adicionais='Ritmo, ritmo., RITMO',
            descricao=(
                '**Beneficio da opcao**\n\n'
                '<svg onload="window.__optionInjected=1"></svg>\n\n'
                '<a href="javascript:window.__optionInjected=1">Inseguro</a>'
            ),
        )
        TbOpcaojogo.objects.create(
            nome='Zelo seguro', slug='zelo-seguro', tipo='Teste',
            etiquetas_adicionais='rítmo!', descricao='Outra opção segura',
        )
        TbClasse.objects.create(nome='Mago', slug='mago')
        TbClasse.objects.create(nome='Bardo', slug='bardo')
        TbMagia.objects.create(
            nome='Luz arcana', slug='luz-arcana', nivel=1,
            escola='Evocacao', classes='Mago', ritual=True,
            descricao='**Brilho seguro**\n\n<svg onload="window.__spellInjected=1"></svg>',
            em_niveis_superiores='**Brilho maior**\n\n<a href="javascript:window.__spellInjected=1">Inseguro</a>',
        )
        TbMagia.objects.create(nome='Nevoa arcana', slug='nevoa-arcana', nivel=2,
                               escola='Ilusao', classes='Bardo', concentracao=True,
                               descricao='Bruma segura')

        with tempfile.TemporaryDirectory(prefix='bonfire-talent-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists())
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
                call('Page.navigate', {'url': self.live_server_url + reverse('jogador_talentos') + '#talento-arcano-literal'})
                wait_for('document.querySelector("[data-talent-title]")?.textContent.includes("Arcano")')
                self.assertTrue(js('document.querySelector("#talentosList").inert'))
                self.assertEqual(js('document.querySelector("#talentosList").getAttribute("aria-hidden")'), 'true')
                js('document.querySelector("#talentMobileMenuButton").focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                self.assertEqual(js('document.querySelector("#talentMobileMenuButton").getAttribute("aria-expanded")'), 'true')
                self.assertEqual(js('document.activeElement?.id'), 'searchInput')
                self.assertFalse(js('document.querySelector("#talentosList").inert'))
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
                self.assertTrue(js('document.querySelector("#talentosList").inert'))
                self.assertEqual(js('document.activeElement?.id'), 'talentMobileMenuButton')
                call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
                self.assertTrue(js('matchMedia("(prefers-reduced-motion: reduce)").matches'))
                self.assertEqual(js('getComputedStyle(document.querySelector("#talentosList")).transitionDuration'), '0s')
                self.assertEqual(js('getComputedStyle(document.querySelector("#talentoDetail")).animationName'), 'none')
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 1280, 'height': 800, 'deviceScaleFactor': 1, 'mobile': False,
                })
                wait_for('!document.querySelector("#talentosList").inert')
                self.assertIsNone(js('document.querySelector("#talentosList").getAttribute("aria-hidden")'))
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                wait_for('document.querySelector("#talentosList").inert')
                self.assertEqual(js('document.querySelector("[data-talent-title]").textContent'), f'Arcano {injected}')
                self.assertEqual(js('document.querySelectorAll("#talentosListItems img, #talentoDetail img").length'), 0)
                self.assertFalse(js('window.__talentInjected === 1'))
                self.assertTrue(js('document.querySelector("#talentoDetail").textContent.includes(' + json.dumps(injected) + ')'))
                self.assertEqual(js('document.querySelector("[data-talent-preview] strong")?.textContent'), 'Benefício editorial')
                self.assertEqual(js('document.querySelectorAll("[data-talent-preview] svg, [data-talent-preview] a[href^=javascript]").length'), 0)
                self.assertTrue(js('document.querySelector("#talentosListItems").textContent.includes(' + json.dumps(injected) + ')'))
                self.assertEqual(js('Array.from(document.querySelectorAll("#tagFilterOptions button")).filter(button => canonicalTag(button.textContent) === "magia").length'), 1)
                self.assertEqual(js('Array.from(document.querySelectorAll("#tagFilterOptions button")).filter(button => canonicalTag(button.textContent) === "combate").length'), 0)
                self.assertEqual(js('Array.from(document.querySelectorAll("#talentosListItems [data-talent-slug=arcano-literal] span")).filter(badge => canonicalTag(badge.textContent) === "magia").length'), 1)
                js('document.querySelector("#filterToggle").click()')
                js('Array.from(document.querySelectorAll("#tagFilterOptions button")).find(button => canonicalTag(button.textContent) === "magia").click()')
                js('document.querySelector("#applyFilterModal").click()')
                wait_for('document.querySelectorAll("#talentosListItems > a").length === 2')
                self.assertFalse(js('document.querySelector("#talentosListItems").textContent.includes("sombrio")'))
                self.assertEqual(js('document.querySelector("#filterCount").textContent'), '1')
                js('document.querySelector("#filterToggle").click()')
                js('document.querySelector("#clearFilters").click()')
                js('document.querySelector("#applyFilterModal").click()')
                wait_for('document.querySelectorAll("#talentosListItems > a").length === 3')

                unsafe_html = (
                    '<img src=x onerror="window.__talentInjected=1">'
                    '<a href="javascript:alert(1)" onclick="alert(1)">Inseguro</a>'
                    '<a href="https://example.org">Guia</a>'
                    '<a href="#" class="bonfire-card-trigger" data-table="tbTalento" data-args="seguro">Carta</a>'
                )
                sanitized = js('sanitizeBonfireMarkdownHtml(' + json.dumps(unsafe_html) + ')')
                self.assertNotIn('onerror', sanitized)
                self.assertNotIn('onclick', sanitized)
                self.assertNotIn('javascript:', sanitized)
                self.assertIn('href="https://example.org"', sanitized)
                self.assertIn('data-table="tbTalento"', sanitized)
                widget = js('sanitizeBonfireMarkdownHtml(renderBonfireMarkdown(' + json.dumps('::options=Bailados de Combate; classe=Guerreiro; nivel=3') + '))')
                self.assertIn('data-tipo="Bailados de Combate"', widget)
                self.assertIn('data-classe="Guerreiro"', widget)
                self.assertIn('data-nivel="3"', widget)

                self.assertEqual(js('location.hash'), '#talento-arcano-literal')
                js('searchInput.value = "coracao"; searchInput.dispatchEvent(new Event("input", {bubbles: true}))')
                wait_for('document.querySelector("[data-talent-title]")?.textContent === "Coração sombrio"')
                self.assertEqual(js('location.hash'), '#talento-coracao-sombrio')
                self.assertEqual(js('document.querySelectorAll("#talentosListItems > a").length'), 1)
                js('searchInput.value = "inexistente"; searchInput.dispatchEvent(new Event("input", {bubbles: true}))')
                wait_for('document.querySelector("#talentoDetail")?.textContent === "Nenhum talento com esses filtros."')
                self.assertEqual(js('location.hash'), '')
                js('searchInput.value = ""; searchInput.dispatchEvent(new Event("input", {bubbles: true}))')
                wait_for('document.querySelector("[data-talent-title]")?.textContent.includes("Arcano")')
                self.assertTrue(js('document.querySelector("#talentosListItems [data-talent-slug=seguro]").href.endsWith("#talento-seguro")'))
                js('document.querySelector("#talentMobileMenuButton").click()')
                self.assertTrue(js('document.body.classList.contains("talent-menu-open")'))
                js('document.querySelector("#talentosListItems [data-talent-slug=seguro]").focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                wait_for('document.querySelector("[data-talent-title]")?.textContent === "Seguro"')
                self.assertEqual(js('location.hash'), '#talento-seguro')
                self.assertEqual(js('document.activeElement?.getAttribute("data-talent-title")'), '')
                self.assertFalse(js('document.body.classList.contains("talent-menu-open")'))
                js('history.back()')
                wait_for('document.querySelector("[data-talent-title]")?.textContent.includes("Arcano")')
                self.assertEqual(js('location.hash'), '#talento-arcano-literal')
                js('location.hash = "#talento-%ZZ"')
                wait_for('location.hash === "#talento-arcano-literal"')
                js('searchInput.value = "Seguro"; searchInput.dispatchEvent(new Event("input", {bubbles: true}))')
                wait_for('document.querySelector("#talentosListItems")?.textContent.includes("Seguro") && !document.querySelector("#talentosListItems")?.textContent.includes("Arcano")')
                js('document.querySelector("#talentosListItems > a").click()')
                wait_for('document.querySelector("[data-talent-title]")?.textContent === "Seguro"')
                self.assertFalse(js('window.__talentInjected === 1'))

                call('Page.navigate', {'url': self.live_server_url + reverse('jogador_opcoes') + '#opcao-opcao-segura'})
                wait_for('document.querySelector("#opcaoDetail [data-talent-title]")?.textContent === "Opcao segura"')
                self.assertEqual(js('document.querySelector("[data-option-preview] strong")?.textContent'), 'Beneficio da opcao')
                self.assertEqual(js('document.querySelectorAll("[data-option-preview] svg, [data-option-preview] a[href^=javascript]").length'), 0)
                self.assertFalse(js('window.__optionInjected === 1'))
                self.assertEqual(js('Array.from(document.querySelectorAll("#tagFilterOptions button")).filter(button => canonicalTag(button.textContent) === "ritmo").length'), 1)
                self.assertEqual(js('document.querySelectorAll("#opcaoDetail > div:first-child > div:first-child > span").length'), 2)

                js('document.querySelector("#filterToggle").click()')
                self.assertEqual(js('document.querySelector("#filterToggle").getAttribute("aria-expanded")'), 'true')
                self.assertEqual(js('document.activeElement?.id'), 'filterClose')
                self.assertEqual(js('document.querySelector(".filter-panel").getAttribute("role")'), 'dialog')
                self.assertEqual(js('document.querySelector(".filter-panel").getAttribute("aria-modal")'), 'true')
                js('document.querySelector("#applyFilterModal").focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                self.assertEqual(js('document.activeElement?.id'), 'filterClose')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
                self.assertEqual(js('document.activeElement?.id'), 'filterToggle')
                self.assertEqual(js('document.querySelector("#filterToggle").getAttribute("aria-expanded")'), 'false')
                wait_for('document.querySelector("#filterModal").classList.contains("hidden")')

                js('document.querySelector("#filterToggle").click()')
                js('document.querySelector("#typeFilterOptions button").focus()')
                self.assertEqual(js('document.activeElement?.getAttribute("aria-pressed")'), 'false')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                self.assertEqual(js('document.activeElement?.getAttribute("aria-pressed")'), 'true')
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                self.assertEqual(js('document.activeElement?.textContent'), 'Teste')
                self.assertEqual(js('document.activeElement?.getAttribute("aria-pressed")'), 'true')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                self.assertEqual(js('document.activeElement?.textContent'), 'Teste')
                self.assertEqual(js('document.activeElement?.getAttribute("aria-pressed")'), 'false')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                js('document.querySelector("#tagFilterOptions button").focus()')
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'text': '\r', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                self.assertEqual(js('document.activeElement?.textContent'), 'Ritmo')
                self.assertEqual(js('document.activeElement?.getAttribute("aria-pressed")'), 'true')
                js('document.querySelector("#applyFilterModal").click()')
                self.assertEqual(js('document.activeElement?.id'), 'filterToggle')
                self.assertEqual(js('document.querySelector("#filterCount").textContent'), '2')
                wait_for('document.querySelectorAll("#opcoesListItems > button").length === 2')
                self.assertEqual(js('document.querySelector("#opcaoDetail [data-talent-title]").textContent'), 'Opcao segura')

                call('Page.navigate', {'url': self.live_server_url + reverse('magias_listas') + '?magia=luz-arcana&busca=Luz&nivel=1'})
                wait_for('document.querySelector("#mgDetail h2")?.textContent === "Luz arcana"')
                self.assertEqual(js('document.querySelector("#mg-busca").value'), 'Luz')
                self.assertEqual(js('document.querySelector("#mg-nivel").value'), '1')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '1')
                self.assertEqual(js('document.querySelectorAll("#mgDetail strong").length'), 2)
                self.assertEqual(js('document.querySelectorAll("#mgDetail svg, #mgDetail a[href^=javascript]").length'), 0)
                self.assertFalse(js('window.__spellInjected === 1'))
                js('document.querySelector("#mg-busca").value = "Nevoa"; document.querySelector("#mg-busca").dispatchEvent(new Event("input", {bubbles: true}))')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '0')
                self.assertEqual(js('document.querySelector("#mgDetail").textContent.trim()'), 'Nenhuma magia com esses filtros.')
                js('document.querySelector("#mg-nivel").value = "2"; document.querySelector("#mg-nivel").dispatchEvent(new Event("change", {bubbles: true}))')
                wait_for('document.querySelector("#mgDetail h2")?.textContent === "Nevoa arcana"')
                self.assertEqual(js('document.querySelector("#mg-count")?.textContent'), '1')
                self.assertEqual(js('new URLSearchParams(location.search).get("magia")'), 'nevoa-arcana')
                js('history.back()')
                wait_for('document.querySelector("#mg-nivel").value === "1"')
                self.assertEqual(js('document.querySelector("#mg-busca").value'), 'Nevoa')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '0')
                js('document.querySelector("#mg-clear-filters").click()')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '2')
                self.assertFalse(js('new URLSearchParams(location.search).has("busca")'))
                js('document.querySelector("#mg-classe").value = "Bardo"; document.querySelector("#mg-classe").dispatchEvent(new Event("change", {bubbles: true}))')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '1')
                self.assertEqual(js('new URLSearchParams(location.search).get("classe")'), 'Bardo')
                js('document.querySelector("#mg-escola").value = "Ilusao"; document.querySelector("#mg-escola").dispatchEvent(new Event("change", {bubbles: true}))')
                js('document.querySelector("#mg-conc").click()')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '1')
                self.assertEqual(js('new URLSearchParams(location.search).get("concentracao")'), '1')
                js('document.querySelector("#mg-ritual").click()')
                self.assertEqual(js('document.querySelector("#mg-count").textContent'), '0')
                self.assertEqual(js('new URLSearchParams(location.search).get("ritual")'), '1')
                js('history.back()')
                wait_for('document.querySelector("#mg-count").textContent === "1"')
                self.assertFalse(js('document.querySelector("#mg-ritual").checked'))
                self.assertEqual(js('document.documentElement.scrollWidth <= window.innerWidth'), True)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
