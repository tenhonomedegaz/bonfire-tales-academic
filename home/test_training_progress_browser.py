"""S09: active training shows elapsed time without granting proficiency early."""

import json
import shutil
import subprocess
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from .models import TbPersonagem, TbPersonagemProficiencia, TbPersonagemTreinamento


class TrainingProgressBrowserTests(StaticLiveServerTestCase):
    def test_elapsed_training_is_visible_on_mobile_and_desktop(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requires isolated PostgreSQL test database.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client unavailable.')
        browser = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.is_file()), None)
        if not browser:
            self.skipTest('Chrome or Edge unavailable.')

        user = get_user_model().objects.create_user('training-progress-browser')
        character = TbPersonagem.objects.create(dono=user, nome='Ficha de treinamento', carteira_pc=10000)
        now = timezone.now()
        training = TbPersonagemTreinamento.objects.create(
            id_personagem=character, tipo='idioma', nome='Idioma de teste',
            conclui_em=now + timedelta(days=15), status='ativo',
        )
        TbPersonagemTreinamento.objects.filter(pk=training.pk).update(iniciado_em=now - timedelta(days=15))
        self.client.force_login(user)

        with tempfile.TemporaryDirectory(prefix='bonfire-training-progress-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                for _ in range(100):
                    if port_file.is_file() or process.poll() is not None:
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.is_file(), 'Browser did not start.')
                port = port_file.read_text(encoding='utf-8').splitlines()[0]
                with urlopen(f'http://127.0.0.1:{port}/json', timeout=5) as response:
                    target = next(item for item in json.load(response) if item['type'] == 'page')
                ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=15, origin='http://localhost')
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
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                call('Network.enable')
                call('Page.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                url = self.live_server_url + reverse('mercado_servicos') + f'?personagem={character.pk}'
                for width in (360, 1440):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 900, 'deviceScaleFactor': 1,
                        'mobile': width == 360,
                    })
                    call('Page.navigate', {'url': url})
                    for _ in range(100):
                        if js('document.readyState === "complete" && !!document.querySelector("[data-training-progress]")'):
                            break
                        time.sleep(.1)
                    else:
                        self.fail('Active training did not render.')
                    progress = js('Number(document.querySelector("[data-training-progress]").getAttribute("aria-valuenow"))')
                    self.assertGreaterEqual(progress, 49)
                    self.assertLessEqual(progress, 51)
                    self.assertEqual(js('document.querySelector("[data-training-progress-text]").textContent'), f'{progress}% do prazo')
                    self.assertGreater(js('document.querySelector("[data-training-progress] span").getBoundingClientRect().width'), 0)
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), width)
                training.refresh_from_db()
                self.assertEqual(training.status, 'ativo')
                self.assertFalse(TbPersonagemProficiencia.objects.filter(id_personagem=character, nome='Idioma de teste').exists())
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
