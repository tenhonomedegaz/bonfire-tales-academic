import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import (TbAntecedente, TbArmadilha, TbCondicao, TbIdioma,
                     TbOpcaojogo, TbRegra, TbTalento)


class ReferenceCatalogBrowserTests(StaticLiveServerTestCase):
    def test_search_destinations_and_condition_link_on_mobile(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponível.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome ou Edge indisponível.')

        TbCondicao.objects.create(slug='agarrado', nome='Agarrado',
                                  efeitos_json=[{'titulo': 'Movimento', 'texto': 'Deslocamento zero.'}])
        TbCondicao.objects.create(slug='amedrontado', nome='Amedrontado',
                                  efeitos_json=[{'titulo': 'Ataque', 'texto': 'Desvantagem.'}])
        background = TbAntecedente.objects.create(
            slug='vigia-das-brumas', nome='Vigia das Brumas', descricao='Vigia as passagens.')
        TbAntecedente.objects.create(
            slug='antigo-vigia-das-brumas', nome='Antigo Vigia das Brumas', descricao='Registra as viagens.')
        trap = TbArmadilha.objects.create(
            slug='sino-das-brumas', nome='Sino das Brumas', efeito='O sino soa.')
        TbArmadilha.objects.create(
            slug='antigo-sino-das-brumas', nome='Antigo Sino das Brumas', efeito='O chão cede.')
        rule = TbRegra.objects.create(
            slug='chamado-das-brumas', nome='Chamado das Brumas')
        TbRegra.objects.create(slug='eco-do-vale', nome='Eco do Vale')
        talent = TbTalento.objects.create(
            slug='guarda-das-brumas', nome='Guarda das Brumas', descricao='Protege a vigília.')
        TbTalento.objects.create(slug='antiga-guarda-das-brumas', nome='Antiga Guarda das Brumas', descricao='Protege a estrada.')
        language = TbIdioma.objects.create(slug='fala-das-brumas', nome='Fala das Brumas')
        TbIdioma.objects.create(slug='antiga-fala-das-brumas', nome='Antiga Fala das Brumas')
        option = TbOpcaojogo.objects.create(
            slug='sinal-das-brumas', nome='Sinal das Brumas', tipo='Exploração')
        TbOpcaojogo.objects.create(slug='antigo-sinal-das-brumas', nome='Antigo Sinal das Brumas', tipo='Exploração')
        with tempfile.TemporaryDirectory(prefix='bonfire-conditions-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=360,800', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
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

                def cdp(method, params):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('id') == sequence:
                            self.assertNotIn('error', result, method)
                            return result.get('result', {})

                def js(expression):
                    result = cdp('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.2)
                    self.fail(f'Tempo esgotado: {expression}')

                cdp('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                cdp('Page.navigate', {'url': self.live_server_url + reverse('sistemas_glossario')})
                target_link = 'Array.from(document.querySelectorAll("a")).find(a => a.getAttribute("href")?.endsWith("#cond-amedrontado"))'
                wait_for(target_link + ' !== undefined')
                js(target_link + '.click()')
                wait_for('location.hash === "#cond-amedrontado" && document.querySelector("#cond-amedrontado")?.hidden === false')
                self.assertEqual(js('document.querySelector("#co-count").textContent'), '2')
                self.assertTrue(js('document.querySelector("#cond-amedrontado").textContent.includes("Desvantagem.")'))
                js('document.querySelector("#co-search").value = "Deslocamento"; document.querySelector("#co-search").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelector("#co-count").textContent === "1"')
                self.assertEqual(js('document.querySelector(".co-item:not([hidden])").dataset.target'), 'cond-agarrado')
                self.assertFalse(js('document.querySelector("#cond-agarrado").hidden'))
                self.assertTrue(js('document.querySelector("#cond-amedrontado").hidden'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))

                for entry, route, selected, count in (
                    (background, 'jogador_antecedentes',
                     'document.querySelector("[data-background=vigia-das-brumas]")?.hidden === false',
                     'document.querySelector("#backgroundResultCount")?.textContent.startsWith("2 ")'),
                    (trap, 'mestre_armadilhas',
                     'document.querySelector("#armadilha-%s")?.hidden === false' % trap.pk,
                     'document.querySelector("#ar-count")?.textContent === "2"'),
                    (rule, 'sistemas_glossario',
                     '!document.querySelector("#regra-chamado-das-brumas")?.classList.contains("hidden")',
                     'document.querySelector("#glo-count")?.textContent === "1"'),
                    (talent, 'jogador_talentos',
                     'document.querySelector("[data-talent-title]")?.textContent === "Guarda das Brumas"',
                     'document.querySelector("#talentResultCount")?.textContent.startsWith("2 de ")'),
                    (language, 'jogador_idiomas',
                     'document.querySelector("[data-language-detail=fala-das-brumas]")?.hidden === false',
                     'document.querySelector("#languageResultCount")?.textContent.startsWith("2 de ")'),
                    (option, 'jogador_opcoes',
                     'document.querySelector("[data-option-title]")?.textContent === "Sinal das Brumas"',
                     'document.querySelector("#optionResults")?.textContent.startsWith("2 opções")'),
                ):
                    cdp('Page.navigate', {'url': self.live_server_url + reverse('busca') + '?q=' + quote(entry.nome)})
                    result_link = 'Array.from(document.querySelectorAll(".cp-result-group a")).find(a => a.querySelector(".cp-result-name")?.firstChild?.textContent.trim() === %s)' % json.dumps(entry.nome)
                    wait_for(result_link + ' !== undefined')
                    js(result_link + '.click()')
                    wait_for('location.pathname === %s && %s && %s' % (json.dumps(reverse(route)), selected, count))
                    self.assertEqual(js('new URLSearchParams(location.search).get("q")'), entry.nome)
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                    cdp('Page.reload', {'ignoreCache': True})
                    wait_for('location.pathname === %s && %s && %s' % (json.dumps(reverse(route)), selected, count))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
