"""S09: public redesign pages render without horizontal clipping."""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import TbConteudoEstatico, TbPerfilMestre, TbPersonagem


class PublicRoutesBrowserTests(StaticLiveServerTestCase):
    def test_public_pages_fit_mobile_and_desktop(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponivel.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome ou Edge indisponivel.')

        TbConteudoEstatico.objects.create(
            chave='sobre-s09-smoke', pagina='sobre', titulo='Sobre o Bonfire Tales',
            conteudo_markdown='Uma comunidade de histórias compartilhadas.',
        )

        routes = (
            'home', 'classes', 'racas', 'jogador_antecedentes',
            'jogador_talentos', 'jogador_idiomas', 'jogador_opcoes',
            'sistemas_glossario', 'sistemas_missoes', 'regras_punicoes',
            'bestiario', 'mestre_armadilhas', 'mestre_condicoes',
            'magias_listas', 'mercado_itens_mundanos',
            'mercado_itens_magicos', 'oficina_magia', 'guia_mestres',
            'atualizacoes', 'sobre',
        )
        with tempfile.TemporaryDirectory(prefix='bonfire-s09-public-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                for _ in range(100):
                    if port_file.exists() or process.poll() is not None:
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.exists(), 'Navegador indisponivel.')
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=20)
                sequence = 0
                missing_assets = []

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get('method') == 'Network.responseReceived':
                            response = result.get('params', {}).get('response', {})
                            if (response.get('status', 0) >= 400 and
                                    response.get('url', '').startswith(self.live_server_url)):
                                missing_assets.append((response['status'], response['url']))
                        if result.get('id') == sequence:
                            self.assertNotIn('error', result, method)
                            return result['result']

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Network.enable')

                def check_page(name, url):
                    missing_assets.clear()
                    call('Page.navigate', {'url': self.live_server_url + url})
                    for _ in range(100):
                        if js('document.readyState !== "loading" && document.styleSheets.length > 1 && !!document.querySelector("main")'):
                            break
                        time.sleep(.1)
                    self.assertTrue(
                        js('document.readyState !== "loading" && document.styleSheets.length > 1 && !!document.querySelector("main")'),
                        js('JSON.stringify({url:location.href,ready:document.readyState,main:!!document.querySelector("main"),sheets:document.styleSheets.length,title:document.title})'),
                    )
                    self.assertLessEqual(js('document.documentElement.scrollWidth - innerWidth'), 1, name)
                    self.assertEqual(missing_assets, [], name)

                for width in (360, 1280):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 800, 'deviceScaleFactor': 1,
                        'mobile': width == 360,
                    })
                    for name in routes:
                        with self.subTest(width=width, route=name):
                            check_page(name, reverse(name))

                user = get_user_model().objects.create_superuser(
                    's09-browser-owner', 's09-browser@example.test', 'test-password',
                )
                character = TbPersonagem.objects.create(dono=user, nome='Ficha de Navegacao')
                TbPerfilMestre.objects.create(user=user, status_mestre='aprovado', modo='mestre', listado=True)
                self.client.force_login(user)
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                private_routes = (
                    ('personagens', reverse('personagens')),
                    ('character_slots', reverse('character_slots')),
                    ('ficha_detail', reverse('ficha_detail', args=[character.pk])),
                    ('mestre_mercado', reverse('mestre_mercado')),
                    ('master_gallery', reverse('master_gallery')),
                    ('subscription_management', reverse('subscription_management')),
                )
                for width in (360, 1280):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 800, 'deviceScaleFactor': 1,
                        'mobile': width == 360,
                    })
                    for name, url in private_routes:
                        with self.subTest(width=width, route=name):
                            check_page(name, url)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
