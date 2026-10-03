"""Q17: contrato da rota pública com os dois catálogos persistidos."""
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from home.models import TbCondicao, TbRegra


class GlossarioIndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.terms = {}
        self.count = ""
        self.reading_count = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "article" and "glo-item" in values.get("class", "").split():
            self.terms[values["id"]] = values.get("data-busca", "")
        if values.get("id") == "glo-count":
            self.reading_count = True

    def handle_data(self, data):
        if self.reading_count:
            self.count += data

    def handle_endtag(self, tag):
        if tag == "span":
            self.reading_count = False


class GlossarioRouteTests(TestCase):
    def test_visitante_recebe_regras_condicoes_e_contagem_do_mesmo_indice(self):
        TbRegra.objects.create(slug="q17-acao", nome="Ação", nome_en="Action")
        TbCondicao.objects.create(
            slug="q17-impedido", nome="Impedido", nome_en="Restrained",
            efeitos_json=[{"titulo": "Movimento", "texto": "Deslocamento zero."}],
        )
        response = self.client.get(reverse("sistemas_glossario"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deslocamento zero.")
        index = GlossarioIndexParser()
        index.feed(response.content.decode("utf-8"))
        self.assertEqual(index.terms["regra-q17-acao"], "ação action")
        self.assertEqual(index.terms["condicao-q17-impedido"], "impedido restrained")
        self.assertEqual(int(index.count), TbRegra.objects.count() + TbCondicao.objects.count())
        self.assertEqual(len(index.terms), int(index.count))

    def test_rotulos_com_aspas_nao_criam_atributos_html(self):
        TbCondicao.objects.create(
            slug="q17-aspas", nome='Condição "especial"', nome_en='Quoted <condition>',
        )
        response = self.client.get(reverse("sistemas_glossario"))
        self.assertEqual(response.status_code, 200)
        index = GlossarioIndexParser()
        index.feed(response.content.decode("utf-8"))
        self.assertEqual(index.terms["condicao-q17-aspas"], 'condição "especial" quoted <condition>')


class ReferenceSearchBrowserTests(StaticLiveServerTestCase):
    def test_search_urls_restore_glossary_and_conditions_on_mobile(self):
        import json
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

        TbRegra.objects.create(slug='acao', nome='Ação', definicao='Uma ação por turno.')
        TbCondicao.objects.create(slug='atordoado', nome='Atordoado', definicao='Perde ações.')
        TbCondicao.objects.create(slug='paralisado', nome='Paralisado', definicao='Não pode mover.')

        with tempfile.TemporaryDirectory(prefix='bonfire-reference-', ignore_cleanup_errors=True) as profile:
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
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True,
                    })['result']
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
                call('Page.navigate', {'url': self.live_server_url + reverse('sistemas_glossario') + '?q=atordoado'})
                wait_for('document.querySelector("[data-reference-query]")?.value === "atordoado" && document.querySelectorAll("[data-reference-item]:not(.hidden)").length === 1')
                self.assertTrue(js('document.querySelector("#regra-acao").classList.contains("hidden")'))
                js('document.querySelector("[data-reference-query]").value = "ação"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('location.search.includes("q=a") && !document.querySelector("#regra-acao").classList.contains("hidden")')
                js('history.back()')
                wait_for('location.search === "?q=atordoado" && document.querySelector("[data-reference-query]")?.value === "atordoado" && document.querySelector("#regra-acao").classList.contains("hidden")')
                js('document.querySelector("[data-reference-query]").value = "turno"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelectorAll("[data-reference-item]:not(.hidden)").length === 1 && !document.querySelector("#regra-acao").classList.contains("hidden")')
                js('document.querySelector("[data-reference-query]").value = "mover"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelectorAll("[data-reference-item]:not(.hidden)").length === 1 && !document.querySelector("#condicao-paralisado").classList.contains("hidden")')
                js('document.querySelector("[data-reference-query]").value = "termo inexistente"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelector("[data-reference-count]")?.textContent === "0" && !document.querySelector("[data-reference-empty]").classList.contains("hidden")')
                self.assertTrue(js('document.querySelector("#glo-condicoes").classList.contains("hidden")'))

                call('Page.navigate', {'url': self.live_server_url + reverse('mestre_condicoes')})
                wait_for('document.querySelectorAll("[data-reference-item]").length === 2')
                js('document.querySelector("[data-reference-query]").value = "paralisado"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('location.search === "?q=paralisado" && document.querySelectorAll("[data-reference-item]:not(.hidden)").length === 1')
                self.assertTrue(js('document.querySelector("a[href=\\"#cond-atordoado\\"]").classList.contains("hidden")'))
                js('history.back()')
                wait_for('location.search === "" && document.querySelectorAll("[data-reference-item]:not(.hidden)").length === 2')
                self.assertEqual(js('document.querySelector("[data-reference-query]").value'), '')
                js('document.querySelector("[data-reference-query]").value = "mover"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelectorAll("[data-reference-item]:not(.hidden)").length === 1 && !document.querySelector("#cond-paralisado").classList.contains("hidden")')
                self.assertTrue(js('document.querySelector("a[href=\\"#cond-atordoado\\"]").classList.contains("hidden")'))
                js('document.querySelector("[data-reference-query]").value = "termo inexistente"; document.querySelector("[data-reference-query]").dispatchEvent(new Event("input", {bubbles:true}))')
                wait_for('document.querySelector("[data-reference-count]")?.textContent === "0" && !document.querySelector("[data-reference-empty]").classList.contains("hidden")')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
