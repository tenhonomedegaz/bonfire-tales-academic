"""The free mission form omits paid-only inputs in a real mobile browser."""

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

from .models import TbMesaAnuncio, TbPerfilMestre


class MasterOfferBrowserTests(StaticLiveServerTestCase):
    def test_free_mission_ignores_hidden_paid_values_and_saves_draft(self):
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

        owner = get_user_model().objects.create_user('mobile_mission_owner')
        TbPerfilMestre.objects.create(user=owner, status_mestre='aprovado', modo='mestre')
        self.client.force_login(owner)
        with tempfile.TemporaryDirectory(prefix='bonfire-master-offer-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
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
                            self.assertNotIn('error', result, method)
                            return result['result']

                def js(expression):
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True, 'awaitPromise': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('master_table_create')})
                for _ in range(80):
                    if js('document.readyState === "complete" && !!document.querySelector(".mh-mission-form")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('!!document.querySelector(".mh-mission-form")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), 360)
                state = json.loads(js('''JSON.stringify((() => {
                    const kind = document.querySelector('#id_modalidade');
                    const price = document.querySelector('#id_preco');
                    kind.value = 'paga';
                    kind.dispatchEvent(new Event('change', {bubbles: true}));
                    const enabledWhenPaid = !price.disabled && !price.closest('[data-offer-field]').hidden;
                    price.value = '9999';
                    kind.value = 'gratuita';
                    kind.dispatchEvent(new Event('change', {bubbles: true}));
                    const form = document.querySelector('.mh-mission-form');
                    const paidControls = [...form.querySelectorAll('[data-offer-field] input, [data-offer-field] select, [data-offer-field] textarea')];
                    const data = new FormData(form);
                    const allDisabledWhenFree = paidControls.every(el => el.disabled);
                    const priceSubmitted = data.has('preco');
                    kind.value = 'paga';
                    kind.dispatchEvent(new Event('change', {bubbles: true}));
                    const restoredWhenPaid = !price.disabled && price.value === '9999';
                    kind.value = 'gratuita';
                    kind.dispatchEvent(new Event('change', {bubbles: true}));
                    return {enabledWhenPaid, allDisabledWhenFree,
                        priceSubmitted, priceValue: price.value, restoredWhenPaid,
                        scroll: document.documentElement.scrollWidth};
                })())'''))
                self.assertTrue(state['enabledWhenPaid'], state)
                self.assertTrue(state['allDisabledWhenFree'], state)
                self.assertFalse(state['priceSubmitted'], state)
                self.assertEqual(state['priceValue'], '9999', state)
                self.assertTrue(state['restoredWhenPaid'], state)
                self.assertLessEqual(state['scroll'], 360, state)

                # Submit an actual free draft; no paid offer can be persisted.
                result = json.loads(js('''JSON.stringify((() => {
                    const form = document.querySelector('.mh-mission-form');
                    form.querySelector('#id_titulo').value = 'Missão gratuita móvel';
                    form.querySelector('#id_descricao').value = 'Uma aventura de teste.';
                    form.querySelector('#id_duracao_minutos').value = '180';
                    form.querySelector('#id_vagas').value = '5';
                    form.querySelector('#id_agenda_combinar').checked = true;
                    form.querySelector('input[name="ranks"]').checked = true;
                    form.querySelector('#id_formato').value = 'oneshot';
                    form.querySelector('#id_plataforma').value = 'Roll20';
                    const data = new FormData(form);
                    data.set('acao', 'rascunho');
                    return {valid: form.checkValidity(), fields: [...data.keys()]};
                })())'''))
                self.assertTrue(result['valid'], result)
                self.assertNotIn('preco', result['fields'])
                response = json.loads(js('''(async () => {
                    const form = document.querySelector('.mh-mission-form');
                    const data = new FormData(form);
                    data.set('acao', 'rascunho');
                    const response = await fetch(form.action || location.href, {
                        method: 'POST', body: data, credentials: 'same-origin',
                    });
                    return JSON.stringify({status: response.status, url: response.url});
                })()'''))
                self.assertEqual(response['status'], 200, response)
                self.assertIn('salvo=1', response['url'])
                table = TbMesaAnuncio.objects.get(mestre=owner)
                self.assertEqual(table.estado, 'rascunho')
                self.assertEqual(table.modalidade, 'gratuita')
                self.assertIsNone(table.preco)
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
