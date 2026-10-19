"""Master announcement and portfolio previews follow their upload/removal contracts."""

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

from .models import TbMesaAnuncio, TbPerfilMestre, TbTrabalhoMestre


class MasterBannerPreviewBrowserTests(StaticLiveServerTestCase):
    def test_edit_preview_matches_upload_and_removal_on_mobile(self):
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

        master = get_user_model().objects.create_user('banner-preview-master')
        TbPerfilMestre.objects.create(user=master, status_mestre='aprovado', modo='mestre')
        table = TbMesaAnuncio.objects.create(
            mestre=master, titulo='A torre das cinzas', descricao='Aventura de teste.',
            agenda_combinar=True, rank='Obsidiana', ranks=['Obsidiana'],
            estado='rascunho', revisao=1, banner_url='/static/assets/logo.png',
        )
        work = TbTrabalhoMestre.objects.create(
            mestre=master, titulo='Mapa do vale', categoria='mapa', texto='Rotas seguras',
            imagem_url='/static/assets/logo.png', estado='rascunho', revisao=1,
        )
        self.client.force_login(master)

        with tempfile.TemporaryDirectory(prefix='bonfire-banner-preview-', ignore_cleanup_errors=True) as directory:
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
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
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
                call('Page.navigate', {'url': self.live_server_url + reverse('master_table_edit', args=[table.pk])})
                for _ in range(100):
                    if js('document.querySelector("[data-mission-banner-preview] img")?.src.includes("logo.png")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('document.querySelector("[data-mission-banner-preview] img")?.src.includes("logo.png")'))
                self.assertTrue(js('document.querySelector("[data-mission-banner-preview]").getAttribute("aria-live") === "polite"'))

                js('''(() => { const checkbox = document.querySelector('[name=remover_banner]');
                    checkbox.checked = true; checkbox.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertIn('será removido', js('document.querySelector("[data-mission-banner-preview]").textContent'))
                self.assertFalse(js('!!document.querySelector("[data-mission-banner-preview] img")'))
                js('''(() => { const checkbox = document.querySelector('[name=remover_banner]');
                    checkbox.checked = false; checkbox.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertTrue(js('document.querySelector("[data-mission-banner-preview] img")?.src.includes("logo.png")'))

                js('''(() => { const input = document.querySelector('[data-mission-banner]');
                    const files = new DataTransfer();
                    files.items.add(new File(['new image'], 'nova.png', {type:'image/png'}));
                    input.files = files.files; input.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertTrue(js('document.querySelector("[data-mission-banner-preview] img")?.src.startsWith("blob:")'))
                self.assertFalse(js('document.querySelector("[name=remover_banner]").checked'))
                js('''(() => { const checkbox = document.querySelector('[name=remover_banner]');
                    checkbox.checked = true; checkbox.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertEqual(js('document.querySelector("[data-mission-banner]").files.length'), 0)
                self.assertIn('será removido', js('document.querySelector("[data-mission-banner-preview]").textContent'))

                js('''(() => { const input = document.querySelector('[data-mission-banner]');
                    const files = new DataTransfer();
                    files.items.add(new File(['invalid'], 'texto.txt', {type:'text/plain'}));
                    input.files = files.files; input.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertFalse(js('document.querySelector("[data-mission-banner]").checkValidity()'))
                self.assertIn('Arquivo inválido', js('document.querySelector("[data-mission-banner-preview]").textContent'))
                js('''(() => { const checkbox = document.querySelector('[name=remover_banner]');
                    checkbox.checked = true; checkbox.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertTrue(js('document.querySelector("[data-mission-banner]").checkValidity()'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), 360)
                table.refresh_from_db()
                self.assertEqual(table.banner_url, '/static/assets/logo.png')

                call('Page.navigate', {'url': self.live_server_url + reverse('master_work_edit', args=[work.pk])})
                for _ in range(100):
                    if js('document.querySelector("[data-master-work-image-preview] img")?.src.includes("logo.png")'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('document.querySelector("[data-master-work-image-preview] img")?.src.includes("logo.png")'))
                self.assertEqual(js('getComputedStyle(document.querySelector("[data-master-work-image-preview] img")).objectFit'), 'contain')
                js('''(() => { const checkbox = document.querySelector('[name=remover_imagem]');
                    checkbox.checked = true; checkbox.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertIn('imagem atual será removida', js('document.querySelector("[data-master-work-image-preview]").textContent'))
                self.assertFalse(js('!!document.querySelector("[data-master-work-image-preview] img")'))
                js('''(() => { const input = document.querySelector('[name=imagem]');
                    const files = new DataTransfer();
                    files.items.add(new File(['new image'], 'mapa.png', {type:'image/png'}));
                    input.files = files.files; input.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertTrue(js('document.querySelector("[data-master-work-image-preview] img")?.src.startsWith("blob:")'))
                self.assertFalse(js('document.querySelector("[name=remover_imagem]").checked'))
                js('''(() => { const checkbox = document.querySelector('[name=remover_imagem]');
                    checkbox.checked = true; checkbox.dispatchEvent(new Event('change', {bubbles:true})); })()''')
                self.assertEqual(js('document.querySelector("[name=imagem]").files.length'), 0)
                self.assertIn('imagem atual será removida', js('document.querySelector("[data-master-work-image-preview]").textContent'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), 360)
                work.refresh_from_db()
                self.assertEqual(work.imagem_url, '/static/assets/logo.png')

                call('Page.navigate', {'url': self.live_server_url + reverse('participation_edit')})
                for _ in range(100):
                    if js('document.querySelector("[data-master-preview-state]")?.textContent'):
                        break
                    time.sleep(.1)
                self.assertEqual(js('document.querySelector("[data-master-preview-state]").textContent'), 'Fora da vitrine')
                self.assertTrue(js('document.querySelector("[data-master-preview-group=experiencia]").hidden'))
                js('''(() => {
                    const form = document.querySelector('[data-master-profile-form]');
                    const values = {apresentacao:'Histórias novas\\nCom mistério', estilo:'Investigação',
                        disponibilidade:'Sábados', experiencia:'Três campanhas',
                        combinados:'Respeito à mesa'};
                    for (const [name, value] of Object.entries(values)) {
                        form.elements.namedItem(name).value = value;
                        form.elements.namedItem(name).dispatchEvent(new Event('input', {bubbles:true}));
                    }
                    form.elements.namedItem('listado').checked = true;
                    form.elements.namedItem('listado').dispatchEvent(new Event('change', {bubbles:true}));
                })()''')
                self.assertEqual(js('document.querySelector("[data-master-preview-state]").textContent'), 'Visível após salvar')
                self.assertEqual(js('document.querySelector("[data-master-preview-field=estilo]").textContent'), 'Investigação')
                self.assertEqual(js('document.querySelector("[data-master-preview-field=experiencia]").textContent'), 'Três campanhas')
                self.assertFalse(js('document.querySelector("[data-master-preview-group=experiencia]").hidden'))
                js('''(() => { const field = document.querySelector('[name=estilo]');
                    field.value = '<img src=x onerror=alert(1)>';
                    field.dispatchEvent(new Event('input', {bubbles:true})); })()''')
                self.assertFalse(js('!!document.querySelector("[data-master-preview-field=estilo] img")'))
                js('''(() => { const field = document.querySelector('[name=estilo]');
                    field.value = 'Investigação';
                    field.dispatchEvent(new Event('input', {bubbles:true})); })()''')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), 360)
                master_profile = TbPerfilMestre.objects.get(user=master)
                self.assertFalse(master_profile.listado)
                js('document.querySelector("[data-master-profile-form] button[type=submit]").click()')
                for _ in range(100):
                    master_profile.refresh_from_db()
                    if master_profile.listado:
                        break
                    time.sleep(.1)
                self.assertTrue(master_profile.listado)
                self.assertEqual(master_profile.apresentacao.replace('\r\n', '\n'), 'Histórias novas\nCom mistério')
                self.assertEqual(master_profile.estilo, 'Investigação')
                self.assertEqual(master_profile.experiencia, 'Três campanhas')
                self.assertContains(self.client.get(reverse('masters_directory')), 'Investigação')
                self.assertContains(self.client.get(reverse('public_profile', args=[master.username]) + '?aba=mestre'), 'Três campanhas')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        response = self.client.post(reverse('master_table_edit', args=[table.pk]), {
            'titulo': table.titulo, 'descricao': table.descricao,
            'agenda_combinar': 'on', 'duracao_minutos': '180', 'vagas': '5',
            'ranks': ['Obsidiana'], 'formato': 'oneshot', 'plataforma': 'Roll20',
            'modalidade': 'gratuita', 'cobranca': 'sessao', 'preco_unidade': 'pessoa',
            'sessoes': '1', 'cortesias': '0', 'revisao': str(table.revisao),
            'remover_banner': 'on', 'acao': 'rascunho',
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        table.refresh_from_db()
        self.assertEqual(table.banner_url, '')
        response = self.client.post(reverse('master_work_edit', args=[work.pk]), {
            'titulo': work.titulo, 'categoria': work.categoria, 'texto': work.texto,
            'revisao': str(work.revisao), 'remover_imagem': 'on', 'acao': 'rascunho',
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        work.refresh_from_db()
        self.assertEqual(work.imagem_url, '')
