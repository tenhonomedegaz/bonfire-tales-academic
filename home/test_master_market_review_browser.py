"""Master market review keeps native POSTs behind an accessible mobile confirmation."""

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

from .models import (TbAventuraMestre, TbPersonagem, TbRecompensaMestre,
                     TbTransacaoMestre, UserProfile)


class MasterMarketReviewBrowserTests(StaticLiveServerTestCase):
    def test_mobile_review_cancels_actions_and_confirms_joint_delivery(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not browser:
            self.skipTest('Chrome or Edge unavailable.')

        user = get_user_model().objects.create_superuser('mm-review-staff', 'mm@example.test', 'test')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.moedas_mestragem = 50
        profile.moedas_evento = 2
        profile.save(update_fields=['moedas_mestragem', 'moedas_evento'])
        TbPersonagem.objects.create(dono=user, nome='Aventureira')
        TbRecompensaMestre.objects.create(slug='review-reward', nome='Prêmio de teste',
            preco_mm=10, ativo=True, efeito='aventura_recompensa')
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-mm-review-', ignore_cleanup_errors=True) as directory:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={directory}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(directory) / 'DevToolsActivePort'
                for _ in range(100):
                    if port_file.exists():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.exists())
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    page = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=15)
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        message = json.loads(ws.recv())
                        if message.get('id') == sequence:
                            self.assertNotIn('error', message, method)
                            return message['result']

                def js(expression):
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True, 'awaitPromise': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def notice(role, message):
                    expression = '''(() => {
                        const node = document.querySelector('[data-mm-notice]');
                        return !!node && node === document.activeElement &&
                            node.getAttribute('role') === %s && node.textContent.includes(%s);
                    })()''' % (json.dumps(role), json.dumps(message))
                    for _ in range(100):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail('Result notice was not focused: %s' % message)

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mestre_mercado')})
                for _ in range(100):
                    if js('document.readyState === "complete" && !!document.querySelector("form[data-mm-review=registro]")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('!!document.querySelector("form[data-mm-review=registro]")'))
                self.assertTrue(js('''(() => {
                    const guide = document.querySelector('#mm-area-eventos .mm-guide');
                    return guide && guide.textContent.includes('não há troca isolada') &&
                        !document.querySelector('form[data-mm-review=eventos]');
                })()'''))

                for kind, expected in (
                    ('registro', ['Mesa de teste', '4', '120']),
                    ('recompensa', ['Prêmio de teste', '10', 'Aventureira', 'Moedas de Evento']),
                ):
                    state = json.loads(js('''JSON.stringify((() => {
                        const form = document.querySelector('form[data-mm-review="%s"]');
                        if (form.elements.namedItem('personagem')) {
                            const select = form.elements.namedItem('personagem');
                            select.value = select.options[1].value;
                            form.elements.namedItem('usar_moedas_evento').checked = true;
                        }
                        if (form.elements.namedItem('nome')) {
                            form.elements.namedItem('nome').value = 'Mesa de teste';
                            form.elements.namedItem('jogadores').value = '4';
                            form.elements.namedItem('recompensa_mm').value = '120';
                        }
                        form.requestSubmit();
                        const dialog = document.querySelector('#mm-review');
                        const shown = dialog.open;
                        const details = dialog.querySelector('dl').textContent;
                        document.querySelector('#mm-review-back').click();
                        return {shown, details, closed: !dialog.open,
                            path: location.pathname, width: document.documentElement.scrollWidth};
                    })())''' % kind))
                    self.assertTrue(state['shown'], state)
                    self.assertTrue(state['closed'], state)
                    self.assertEqual(state['path'], reverse('mestre_mercado'), state)
                    self.assertLessEqual(state['width'], 360, state)
                    for term in expected:
                        self.assertIn(term, state['details'])

                self.assertFalse(TbAventuraMestre.objects.filter(mestre=user).exists())
                profile.refresh_from_db()
                self.assertEqual(profile.moedas_mestragem, 50)
                self.assertEqual(profile.moedas_evento, 2)
                js('''(() => {
                    const form = document.querySelector('form[data-mm-review="registro"]');
                    form.requestSubmit();
                    document.querySelector('#mm-review-confirm').click();
                })()''')
                for _ in range(100):
                    if js('location.search.includes("m=aventura")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('location.search.includes("m=aventura")'))
                notice('status', 'Aventura registrada')
                self.assertEqual(TbAventuraMestre.objects.filter(mestre=user, nome='Mesa de teste',
                                                                jogadores=4, recompensa_mm=120).count(), 1)
                profile.refresh_from_db()
                self.assertEqual(profile.moedas_mestragem, 170)
                coins_after_table = profile.moedas_evento

                call('Page.navigate', {'url': self.live_server_url + reverse('mestre_mercado')})
                for _ in range(100):
                    if js('document.readyState === "complete" && !!document.querySelector("form[data-mm-review=recompensa]")'):
                        break
                    time.sleep(.1)
                js('''(() => {
                    const form = document.querySelector('form[data-mm-review="recompensa"]');
                    const select = form.elements.namedItem('personagem');
                    select.value = select.options[1].value;
                    form.elements.namedItem('quantidade').value = '2';
                    form.elements.namedItem('quantidade').dispatchEvent(new Event('input'));
                    form.elements.namedItem('usar_moedas_evento').checked = true;
                    form.elements.namedItem('usar_moedas_evento').dispatchEvent(new Event('change'));
                    form.requestSubmit();
                    document.querySelector('#mm-review-confirm').click();
                })()''')
                for _ in range(100):
                    if js('location.search.includes("m=entregue")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('location.search.includes("m=entregue")'))
                notice('status', 'Aventura e recompensa entregues')
                profile.refresh_from_db()
                self.assertEqual(profile.moedas_evento, coins_after_table - 2)
                character = TbPersonagem.objects.get(dono=user)
                self.assertEqual((character.aventuras, character.braseiros), (2, 4))
                receipt = TbTransacaoMestre.objects.get(personagem=character)
                self.assertEqual(receipt.detalhes_json['moedas_evento_gastas'], 2)
                self.assertEqual(profile.moedas_mestragem, 150)

                call('Page.navigate', {'url': self.live_server_url + reverse('mestre_mercado') + '?m=sem_evento'})
                notice('alert', 'Moedas de Evento insuficientes')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
