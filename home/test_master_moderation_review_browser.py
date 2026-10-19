"""Staff moderation reviews the chosen action before the native POST."""

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
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from .models import (TbAutorizacaoVitrine, TbAventuraMestre, TbMesaAnuncio,
                     TbPerfilMestre, TbTrabalhoMestre, TbVerificacaoMesa)


class MasterModerationReviewBrowserTests(StaticLiveServerTestCase):
    def test_staff_reviews_listing_and_portfolio_actions_on_mobile(self):
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

        users = get_user_model()
        master = users.objects.create_user('reviewed-master')
        applicant = users.objects.create_user('applicant-master')
        staff = users.objects.create_superuser('moderation-review-staff', 'moderation@example.test', 'test')
        TbPerfilMestre.objects.create(user=master, modo='mestre', status_mestre='aprovado', listado=True)
        applicant_profile = TbPerfilMestre.objects.create(
            user=applicant, modo='mestre', status_mestre='pendente')
        adventure = TbAventuraMestre.objects.create(
            mestre=master, nome='Mesa concluída', data=timezone.localdate()-timedelta(days=1),
            jogadores=4, recompensa_mm=0)
        table = TbMesaAnuncio.objects.create(
            mestre=master, titulo='A torre das cinzas', descricao='Aventura de teste.',
            agenda_combinar=True, rank='Obsidiana', ranks=['Obsidiana'],
            estado='pendente', revisao=1,
        )
        work = TbTrabalhoMestre.objects.create(
            mestre=master, titulo='Mapa do vale', categoria='mapa', texto='Rotas seguras',
            estado='pendente', revisao=1,
        )
        self.client.force_login(staff)

        with tempfile.TemporaryDirectory(prefix='bonfire-moderation-review-', ignore_cleanup_errors=True) as directory:
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
                        'expression': expression, 'returnByValue': True,
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

                def navigate(name, kind):
                    call('Page.navigate', {'url': self.live_server_url + reverse(name)})
                    expression = f'document.readyState === "complete" && !!document.querySelector("form[data-master-moderation={kind}]")'
                    for _ in range(100):
                        if js(expression):
                            break
                        time.sleep(.1)
                    self.assertTrue(js(expression), name)

                navigate('master_dashboard', 'mesa')
                js('''(() => {
                    const form = document.querySelector('form[data-master-moderation="mesa"]');
                    form.elements.namedItem('nota').value = 'Mesa aprovada';
                    form.querySelector('button[value="aprovar"]').click();
                })()''')
                state = json.loads(js('''JSON.stringify((() => {
                    const dialog = document.querySelector('[data-master-moderation-dialog]');
                    return {open:dialog.open, text:dialog.textContent,
                        width:dialog.getBoundingClientRect().width, viewport:innerWidth,
                        link:dialog.querySelector('[data-master-moderation-detail]').pathname};
                })())'''))
                self.assertTrue(state['open'], state)
                self.assertIn(table.titulo, state['text'])
                self.assertIn('Mesa aprovada', state['text'])
                self.assertLessEqual(state['width'], state['viewport'])
                self.assertEqual(state['link'], reverse('master_table_detail', args=[table.pk]))
                js('document.querySelector("[data-master-moderation-cancel]").click()')
                table.refresh_from_db()
                self.assertEqual(table.estado, 'pendente')
                js('document.querySelector("form[data-master-moderation=mesa] button[value=aprovar]").click()')
                js('document.querySelector("[data-master-moderation-confirm]").click()')
                for _ in range(100):
                    table.refresh_from_db()
                    if table.estado == 'publicado':
                        break
                    time.sleep(.1)
                self.assertEqual((table.estado, table.nota_revisao, table.revisor_id),
                                 ('publicado', 'Mesa aprovada', staff.pk))
                self.assertEqual(Client().get(reverse('master_table_detail', args=[table.pk])).status_code, 200)

                navigate('master_gallery_review', 'trabalho')
                js('''(() => {
                    const form = document.querySelector('form[data-master-moderation="trabalho"]');
                    form.elements.namedItem('nota').value = 'Ajustar legenda';
                    form.querySelector('button[value="ajustes"]').click();
                })()''')
                state = json.loads(js('''JSON.stringify((() => {
                    const dialog = document.querySelector('[data-master-moderation-dialog]');
                    return {open:dialog.open, text:dialog.textContent,
                        link:dialog.querySelector('[data-master-moderation-detail]').pathname};
                })())'''))
                self.assertTrue(state['open'], state)
                self.assertIn(work.titulo, state['text'])
                self.assertIn('Ajustar legenda', state['text'])
                self.assertEqual(state['link'], reverse('master_work_detail', args=[work.pk]))
                js('document.querySelector("[data-master-moderation-cancel]").click()')
                work.refresh_from_db()
                self.assertEqual(work.estado, 'pendente')
                js('document.querySelector("form[data-master-moderation=trabalho] button[value=ajustes]").click()')
                js('document.querySelector("[data-master-moderation-confirm]").click()')
                for _ in range(100):
                    work.refresh_from_db()
                    if work.estado == 'ajustes':
                        break
                    time.sleep(.1)
                self.assertEqual((work.estado, work.nota_revisao, work.revisor_id),
                                 ('ajustes', 'Ajustar legenda', staff.pk))
                self.assertEqual(Client().get(reverse('master_work_detail', args=[work.pk])).status_code, 404)

                navigate('master_dashboard', 'permissao')
                js('''(() => {
                    const form = [...document.querySelectorAll('form[data-master-moderation="permissao"]')]
                        .find(item => item.querySelector('button[value="recusar"]'));
                    form.elements.namedItem('nota').value = 'Precisa atualizar o perfil';
                    form.elements.namedItem('confirmar').checked = true;
                    form.querySelector('button[value="recusar"]').click();
                })()''')
                state = json.loads(js('''JSON.stringify((() => {
                    const dialog = document.querySelector('[data-master-moderation-dialog]');
                    return {open:dialog.open, text:dialog.textContent};
                })())'''))
                self.assertTrue(state['open'], state)
                self.assertIn(applicant.username, state['text'])
                self.assertIn('Precisa atualizar o perfil', state['text'])
                self.assertIn('solicitação será recusada', state['text'])
                js('document.querySelector("[data-master-moderation-cancel]").click()')
                applicant_profile.refresh_from_db()
                self.assertEqual(applicant_profile.status_mestre, 'pendente')
                js('[...document.querySelectorAll("form[data-master-moderation=permissao]")].find(item => item.querySelector("button[value=recusar]")).querySelector("button[value=recusar]").click()')
                js('document.querySelector("[data-master-moderation-confirm]").click()')
                for _ in range(100):
                    applicant_profile.refresh_from_db()
                    if applicant_profile.status_mestre == 'recusado':
                        break
                    time.sleep(.1)
                self.assertEqual((applicant_profile.status_mestre, applicant_profile.nota_avaliacao),
                                 ('recusado', 'Precisa atualizar o perfil'))

                navigate('master_dashboard', 'verificacao')
                js('''(() => {
                    const form = document.querySelector('form[data-master-moderation="verificacao"]');
                    form.elements.namedItem('observacao').value = 'Registro público conferido';
                    form.elements.namedItem('aberta').checked = true;
                    form.elements.namedItem('confirmar').checked = true;
                    form.querySelector('button[value="validar"]').click();
                })()''')
                state = json.loads(js('''JSON.stringify((() => {
                    const dialog = document.querySelector('[data-master-moderation-dialog]');
                    return {open:dialog.open, text:dialog.textContent};
                })())'''))
                self.assertTrue(state['open'], state)
                self.assertIn(adventure.nome, state['text'])
                self.assertIn('Registro público conferido', state['text'])
                self.assertIn('Divulgação aberta: sim', state['text'])
                js('document.querySelector("[data-master-moderation-cancel]").click()')
                self.assertFalse(TbVerificacaoMesa.objects.filter(aventura=adventure).exists())
                js('document.querySelector("form[data-master-moderation=verificacao] button[value=validar]").click()')
                js('document.querySelector("[data-master-moderation-confirm]").click()')
                for _ in range(100):
                    if TbVerificacaoMesa.objects.filter(aventura=adventure, validada=True).exists():
                        break
                    time.sleep(.1)
                verification = TbVerificacaoMesa.objects.get(aventura=adventure)
                self.assertEqual((verification.validada, verification.aberta, verification.observacao),
                                 (True, True, 'Registro público conferido'))

                navigate('master_dashboard', 'vitrine')
                js('''(() => {
                    const form = document.querySelector('form[data-master-moderation="vitrine"]');
                    form.elements.namedItem('observacao').value = 'Piloto demonstrativo autorizado';
                    form.elements.namedItem('confirmar').checked = true;
                    form.querySelector('button[value="autorizar"]').click();
                })()''')
                state = json.loads(js('''JSON.stringify((() => {
                    const dialog = document.querySelector('[data-master-moderation-dialog]');
                    return {open:dialog.open, text:dialog.textContent};
                })())'''))
                self.assertTrue(state['open'], state)
                self.assertIn(master.username, state['text'])
                self.assertIn('Piloto demonstrativo autorizado', state['text'])
                self.assertIn('não libera cobrança', state['text'])
                js('document.querySelector("[data-master-moderation-cancel]").click()')
                self.assertFalse(TbAutorizacaoVitrine.objects.filter(user=master).exists())
                js('document.querySelector("form[data-master-moderation=vitrine] button[value=autorizar]").click()')
                js('document.querySelector("[data-master-moderation-confirm]").click()')
                for _ in range(100):
                    if TbAutorizacaoVitrine.objects.filter(user=master, autorizada=True).exists():
                        break
                    time.sleep(.1)
                listing = TbAutorizacaoVitrine.objects.get(user=master)
                self.assertEqual((listing.autorizada, listing.observacao),
                                 (True, 'Piloto demonstrativo autorizado'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
