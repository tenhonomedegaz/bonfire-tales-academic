import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from .admin import OrganizacaoAdminForm
from .models import TbMapLayer, TbOrganizacao, TbRegiao, TbTerritorio


class OrganizationCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_user(
            username='organization-editor', password='test-password', is_staff=True
        )

    def test_admin_normalizes_legacy_json_string_and_rejects_object(self):
        fields = {
            'nome': 'Liga do Norte', 'slug': 'liga-do-norte', 'tipo': 'Guilda',
            'regioes': '"[]"', 'territorios': '[]', 'aliados': '["Casa da Luz"]',
            'inimigos': '[]', 'tags': '[]',
        }
        form = OrganizacaoAdminForm(data=fields)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['regioes'], [])
        self.assertEqual(form.cleaned_data['aliados'], ['Casa da Luz'])

        fields['aliados'] = '{"nome":"Casa da Luz"}'
        form = OrganizacaoAdminForm(data=fields)
        self.assertFalse(form.is_valid())
        self.assertIn('aliados', form.errors)

        owner = get_user_model().objects.create_superuser(
            username='organization-owner', password='test-password', email='owner@example.invalid'
        )
        self.client.force_login(owner)
        response = self.client.post(reverse('admin:home_tborganizacao_add'), data={
            **fields, 'aliados': '["Casa da Luz"]', '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 302)
        saved = TbOrganizacao.objects.get(slug='liga-do-norte')
        self.assertEqual(saved.regioes, [])
        self.assertEqual(saved.aliados, ['Casa da Luz'])

    def test_staff_post_persists_lists_and_catalog_exposes_typed_relationships(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({
                'nome': 'Liga do Norte', 'regioes': '[]',
                'aliados': ['Casa da Luz'], 'inimigos': '["Bando"]',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        organization = TbOrganizacao.objects.get(slug='liga-do-norte')
        self.assertEqual(organization.regioes, [])
        self.assertEqual(organization.aliados, ['Casa da Luz'])
        self.assertEqual(organization.inimigos, ['Bando'])

        # Existing rows may contain a JSON string instead of a JSON array.
        TbOrganizacao.objects.create(
            nome='Guarda Antiga', slug='guarda-antiga', aliados='[]', regioes='[]'
        )
        TbOrganizacao.objects.create(
            nome='Arquivo Malformado', slug='arquivo-malformado', aliados={'nome': 'Casa'},
        )
        catalog = self.client.get(reverse('mundo_organizacoes'))
        self.assertEqual(catalog.status_code, 200)
        by_slug = {item['slug']: item for item in catalog.context['items']}
        self.assertEqual(by_slug['liga-do-norte']['meta']['Aliados'], ['Casa da Luz'])
        self.assertEqual(by_slug['liga-do-norte']['meta']['Inimigos'], ['Bando'])
        self.assertEqual(by_slug['guarda-antiga']['meta']['Aliados'], [])
        self.assertEqual(by_slug['arquivo-malformado']['meta']['Aliados'], [])
        self.assertNotIn('[]', by_slug['guarda-antiga']['tags'])

        repeated = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({'nome': 'Liga do Norte', 'aliados': ['Casa Renovada']}),
            content_type='application/json',
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(TbOrganizacao.objects.filter(slug='liga-do-norte').count(), 1)
        organization.refresh_from_db()
        self.assertEqual(organization.aliados, ['Casa Renovada'])

    def test_invalid_post_does_not_write_any_organization(self):
        anonymous = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({'nome': 'Sem Autorização'}),
            content_type='application/json',
        )
        self.assertEqual(anonymous.status_code, 404)
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse('mundo_organizacoes'),
            data=json.dumps({'nome': 'Lote Inválido', 'aliados': '[invalid'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TbOrganizacao.objects.exists())

    def test_public_references_link_only_to_visible_unique_locations(self):
        TbMapLayer.objects.create(id_layer=0, nome='Superfície', publica=True)
        TbMapLayer.objects.create(id_layer=1, nome='Oculta', publica=False)
        TbRegiao.objects.create(nome='Auralon', slug='auralon', camada=0)
        TbRegiao.objects.create(nome='Segredo', slug='segredo', camada=1)
        TbTerritorio.objects.create(nome='Reino Auraliano', slug='reino-auraliano', camada=0)
        TbOrganizacao.objects.create(
            nome='Liga do Norte', slug='liga-do-norte', regioes=['Auralon', 'Segredo', 'Desconhecida'],
            territorios=['Reino Auraliano'], aliados=['Casa da Luz'],
        )
        TbOrganizacao.objects.create(nome='Casa da Luz', slug='casa-da-luz')

        response = self.client.get(reverse('mundo_organizacoes'))
        self.assertEqual(response.status_code, 200)
        league = next(item for item in response.context['items'] if item['slug'] == 'liga-do-norte')
        self.assertEqual(league['references']['Regiões'], [
            {'label': 'Auralon', 'url': reverse('regiao_detail', args=['auralon'])},
            {'label': 'Segredo', 'url': ''},
            {'label': 'Desconhecida', 'url': ''},
        ])
        self.assertEqual(league['references']['Territórios'], [
            {'label': 'Reino Auraliano', 'url': reverse('territorio_detail', args=['reino-auraliano'])},
        ])
        self.assertEqual(league['references']['Aliados'], [{'label': 'Casa da Luz', 'url': '#casa-da-luz'}])

        self.client.force_login(self.editor)
        staff_response = self.client.get(reverse('mundo_organizacoes'))
        league = next(item for item in staff_response.context['items'] if item['slug'] == 'liga-do-norte')
        self.assertEqual(league['references']['Regiões'][1]['url'], reverse('regiao_detail', args=['segredo']))


class OrganizationReferencesBrowserTests(StaticLiveServerTestCase):
    def test_visible_references_navigate_from_catalog_on_mobile(self):
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

        TbMapLayer.objects.create(id_layer=0, nome='Superfície', publica=True)
        TbRegiao.objects.create(nome='Auralon', slug='auralon', camada=0)
        TbTerritorio.objects.create(nome='Reino Auraliano', slug='reino-auraliano', camada=0)
        TbOrganizacao.objects.create(
            nome='Liga do Norte', slug='liga-do-norte', regioes=['Auralon', 'Desconhecida'],
            territorios=['Reino Auraliano'], aliados=['Casa da Luz'],
            descricao='**Negrito** <img src=x onerror=alert(1)> [ruim](javascript:alert(1)) [bom](https://example.org)',
        )
        TbOrganizacao.objects.create(nome='Casa da Luz', slug='casa-da-luz')

        with tempfile.TemporaryDirectory(prefix='bonfire-org-', ignore_cleanup_errors=True) as profile:
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
                call('Page.navigate', {'url': self.live_server_url + reverse('mundo_organizacoes') + '#liga-do-norte'})
                wait_for('document.querySelector(".catalog-detail .detail-title")?.textContent === "Liga do Norte"')
                self.assertEqual(js('document.querySelectorAll(".catalog-detail script, .catalog-detail img[onerror]").length'), 0)
                self.assertEqual(js('document.querySelectorAll(".catalog-detail a[href^=javascript]").length'), 0)
                self.assertEqual(js('document.querySelectorAll(".catalog-detail strong").length'), 1)
                self.assertEqual(js('document.querySelectorAll(".catalog-detail a[href=\\"https://example.org\\"]").length'), 1)
                self.assertEqual(js('document.querySelectorAll(".detail-meta-value a[href=\\"/mundo/regioes/auralon/\\"]").length'), 1)
                self.assertEqual(js('document.querySelectorAll(".detail-meta-value a[href=\\"/mundo/territorios/reino-auraliano/\\"]").length'), 1)
                self.assertEqual(js('document.querySelectorAll(".detail-meta-value a[href=\\"#casa-da-luz\\"]").length'), 1)
                self.assertFalse(js('Array.from(document.querySelectorAll(".detail-meta-value a")).some(a => a.textContent === "Desconhecida")'))
                js('document.querySelector(".detail-meta-value a[href=\\"#casa-da-luz\\"]").click()')
                wait_for('location.hash === "#casa-da-luz" && document.querySelector(".detail-title")?.textContent === "Casa da Luz"')
                js('history.back()')
                wait_for('location.hash === "#liga-do-norte" && document.querySelector(".detail-title")?.textContent === "Liga do Norte"')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                js('window.renderBonfireMarkdown = undefined; document.querySelector(".catalog-card.is-active").click()')
                self.assertEqual(js('document.querySelectorAll(".catalog-detail img, .catalog-detail script, .catalog-detail a[href^=javascript]").length'), 0)
                self.assertTrue(js('document.querySelector(".catalog-detail .bonfire-markdown").textContent.includes("<img src=x")'))
                self.assertEqual(js('document.querySelectorAll(".detail-meta-value a[href=\\"/mundo/regioes/auralon/\\"]").length'), 1)
                js('document.querySelector(".detail-meta-value a[href=\\"/mundo/regioes/auralon/\\"]").click()')
                wait_for('location.pathname === "/mundo/regioes/auralon/" && document.readyState === "complete"')
                self.assertTrue(js('document.body.textContent.includes("Auralon")'))

                editor = get_user_model().objects.create_user(
                    'organization-browser-editor', password='test-password', is_staff=True)
                self.client.force_login(editor)
                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mundo_organizacoes')})
                wait_for('document.querySelector("#orgForm [name=csrfmiddlewaretoken]")?.value.length > 0')
                js('''(() => {
                    document.querySelector('#toggleOrgForm').click();
                    document.querySelector('#orgForm [name=nome]').value = 'Liga Navegador';
                    document.querySelector('#orgForm [name=regioes]').value = 'Auralon';
                    document.querySelector('#orgForm [name=descricao]').value = 'Criada pelo editor.';
                    document.querySelector('#orgForm button[type=submit]').click();
                })()''')
                wait_for('[...document.querySelectorAll(".catalog-card-title")].some(e => e.textContent === "Liga Navegador")')
                created = TbOrganizacao.objects.get(slug='liga-navegador')
                self.assertEqual(created.regioes, ['Auralon'])
                self.assertEqual(created.descricao, 'Criada pelo editor.')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
