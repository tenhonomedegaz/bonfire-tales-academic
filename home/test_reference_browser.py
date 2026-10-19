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
                     TbItemMagico, TbItemMundano, TbOpcaojogo, TbRegra, TbTalento)


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
        condition = TbCondicao.objects.create(slug='amedrontado', nome='Amedrontado',
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
        TbRegra.objects.create(slug='antigo-chamado-das-brumas', nome='Antigo Chamado das Brumas')
        TbRegra.objects.create(slug='eco-do-vale', nome='Eco do Vale')
        talent = TbTalento.objects.create(
            slug='guarda-das-brumas', nome='Guarda das Brumas', descricao='Protege a vigília.')
        TbTalento.objects.create(slug='antiga-guarda-das-brumas', nome='Antiga Guarda das Brumas', descricao='Protege a estrada.')
        language = TbIdioma.objects.create(slug='fala-das-brumas', nome='Fala das Brumas')
        TbIdioma.objects.create(slug='antiga-fala-das-brumas', nome='Antiga Fala das Brumas')
        option = TbOpcaojogo.objects.create(
            slug='sinal-das-brumas', nome='Sinal das Brumas', tipo='Exploração')
        TbOpcaojogo.objects.create(slug='antigo-sinal-das-brumas', nome='Antigo Sinal das Brumas', tipo='Exploração')
        mundane = TbItemMundano.objects.create(slug='corda-das-brumas', nome='Corda das Brumas', preco='1 PO')
        TbItemMundano.objects.create(slug='antiga-corda-das-brumas', nome='A Corda das Brumas', preco='1 PO')
        magic = TbItemMagico.objects.create(slug='anel-das-brumas', nome='Anel das Brumas', preco=0)
        TbItemMagico.objects.create(slug='antigo-anel-das-brumas', nome='A Anel das Brumas', preco=0)
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
                cdp('Emulation.setFocusEmulationEnabled', {'enabled': True})
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

                cdp('Page.navigate', {'url': self.live_server_url + reverse('busca') + '?q=' + quote(condition.nome)})
                condition_link = 'Array.from(document.querySelectorAll(".cp-result-group a")).find(a => a.querySelector(".cp-result-name")?.firstChild?.textContent.trim() === %s)' % json.dumps(condition.nome)
                wait_for(condition_link + ' !== undefined')
                js(condition_link + '.click()')
                condition_open = 'location.hash === "#cond-amedrontado" && document.querySelector("#cond-amedrontado")?.hidden === false && document.activeElement?.id === "co-reader"'
                wait_for('location.pathname === %s && %s' % (json.dumps(reverse('mestre_condicoes')), condition_open))
                self.assertTrue(js('''(() => {
                    const rect = document.querySelector('#co-reader').getBoundingClientRect();
                    return rect.top < innerHeight && rect.bottom > 0;
                })()'''))
                cdp('Page.reload', {'ignoreCache': True})
                wait_for(condition_open)

                for entry, route, selected, count in (
                    (background, 'jogador_antecedentes',
                     'document.querySelector("[data-background=vigia-das-brumas]")?.hidden === false',
                     'document.querySelector("#backgroundResultCount")?.textContent.startsWith("2 ")'),
                    (trap, 'mestre_armadilhas',
                     'document.querySelector("#armadilha-%s")?.hidden === false' % trap.pk,
                     'document.querySelector("#ar-count")?.textContent === "2"'),
                    (rule, 'sistemas_glossario',
                     'location.hash === "#regra-chamado-das-brumas" && document.activeElement?.id === "regra-chamado-das-brumas"',
                     'document.querySelector("#glo-count")?.textContent === "2"'),
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
                    if route in ('jogador_talentos', 'jogador_idiomas', 'jogador_opcoes'):
                        heading = {
                            'jogador_talentos': '[data-talent-title]',
                            'jogador_idiomas': '[data-language-detail]:not([hidden]) h2',
                            'jogador_opcoes': '[data-option-title]',
                        }[route]
                        wait_for('document.activeElement === document.querySelector(%s)' % json.dumps(heading))
                        state = js('''(() => {
                            const heading = document.querySelector(%s);
                            const box = heading.getBoundingClientRect();
                            return {focused: document.activeElement === heading,
                                top: box.top, bottom: box.bottom, height: innerHeight,
                                outline: getComputedStyle(heading).outlineStyle};
                        })()''' % json.dumps(heading))
                        self.assertTrue(state['focused'] and state['top'] < state['height'] and
                                        state['bottom'] > 0 and state['outline'] != 'none',
                                        f'{route}: {state}')
                    if route == 'sistemas_glossario':
                        self.assertTrue(js('''(() => {
                            const box = document.querySelector('#regra-chamado-das-brumas').getBoundingClientRect();
                            return box.top < innerHeight && box.bottom > 0;
                        })()'''))
                    self.assertEqual(js('new URLSearchParams(location.search).get("q")'), entry.nome)
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                    cdp('Page.reload', {'ignoreCache': True})
                    wait_for('location.pathname === %s && %s && %s' % (json.dumps(reverse(route)), selected, count))
                    if route in ('jogador_talentos', 'jogador_idiomas', 'jogador_opcoes'):
                        wait_for('document.activeElement === document.querySelector(%s)' % json.dumps(heading))
                        self.assertTrue(js('''(() => {
                            const heading = document.querySelector(%s);
                            const box = heading.getBoundingClientRect();
                            return document.activeElement === heading && box.top < innerHeight && box.bottom > 0;
                        })()''' % json.dumps(heading)), route)
                for entry, route in ((mundane, 'mercado_itens_mundanos'),
                                     (magic, 'mercado_itens_magicos')):
                    cdp('Page.navigate', {'url': self.live_server_url + reverse('busca') + '?q=' + quote(entry.nome)})
                    result_link = 'Array.from(document.querySelectorAll(".cp-result-group a")).find(a => a.querySelector(".cp-result-name")?.firstChild?.textContent.trim() === %s)' % json.dumps(entry.nome)
                    wait_for(result_link + ' !== undefined')
                    js(result_link + '.click()')
                    selected = 'document.querySelector("[data-shop-pane=comprar] [data-mkt-row].is-selected")?.dataset.name === %s' % json.dumps(entry.nome)
                    wait_for('location.pathname === %s && %s' % (json.dumps(reverse(route)), selected))
                    self.assertEqual(js('new URLSearchParams(location.search).get("busca")'), entry.nome)
                    cdp('Page.reload', {'ignoreCache': True})
                    wait_for('location.pathname === %s && %s' % (json.dumps(reverse(route)), selected))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
