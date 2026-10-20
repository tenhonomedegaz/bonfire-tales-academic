"""Previa e leitura segura do Jornal, inclusive layout Atlas."""

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

from .models import TbJornal


class JornalMarkdownPresentationTests(StaticLiveServerTestCase):
    def test_public_article_and_editor_preview_are_safe_in_both_layouts(self):
        if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
            self.skipTest('Requer PostgreSQL de teste isolado.')
        try:
            import websocket
        except ImportError:
            self.skipTest('websocket-client indisponivel.')
        chrome = shutil.which('chrome') or next((str(path) for path in (
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest('Chrome ou Edge indisponivel.')

        source = '**Destaque** <img src=x onerror=alert(1)> [perigo](javascript:alert(1)) [referencia](https://example.org)'
        editor = get_user_model().objects.create_superuser('jornal-editor', 'jornal-editor@example.invalid', 'test-pass')
        self.client.force_login(editor)
        for title, layout, markdown in (
            ('Jornal Normal', 'padrao', source),
            ('Jornal Atlas', 'atlas', '::header\nNo: 12\nAssunto: Teste\n::\n\n' + source),
        ):
            response = self.client.post(reverse('jornal_create'), data=json.dumps({
                'titulo': title, 'layout': layout, 'conteudo_markdown': markdown,
            }), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['ok'])
        regular = TbJornal.objects.get(slug='jornal-normal')
        atlas = TbJornal.objects.get(slug='jornal-atlas')

        with tempfile.TemporaryDirectory(prefix='bonfire-jornal-md-', ignore_cleanup_errors=True) as profile:
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
                self.assertTrue(port_file.exists(), 'Chrome nao iniciou.')
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

                def assert_safe(selector):
                    self.assertTrue(js(f'document.querySelector({json.dumps(selector + " strong")}) !== null'))
                    self.assertEqual(js(f'document.querySelectorAll({json.dumps(selector + " img[onerror], " + selector + " a[href^=javascript], " + selector + " script")}).length'), 0)
                    self.assertEqual(js(f'document.querySelectorAll({json.dumps(selector + " a[href=\"https://example.org\"]")}).length'), 1)

                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('mundo_jornal')})
                wait_for('document.querySelectorAll(".jornal-card").length === 2')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                self.assertTrue(js('[...document.querySelectorAll(".jornal-card")].every(card => card.getBoundingClientRect().right <= document.documentElement.clientWidth)'))
                self.assertNotIn('url(', js('getComputedStyle(document.querySelector(".jornal-hero")).backgroundImage'))
                for article in (regular, atlas):
                    call('Page.navigate', {'url': self.live_server_url + reverse('jornal_detail', args=[article.slug])})
                    wait_for('document.querySelector("[data-jornal-markdown] strong") !== null')
                    assert_safe('[data-jornal-markdown]')
                    self.assertTrue(js('document.querySelector("[data-jornal-markdown]").dataset.markdownManual === "true"'))
                    if article is atlas:
                        self.assertEqual(js('document.querySelector(".artigo-atlas-meta h1")?.textContent.trim()'), article.titulo)
                        self.assertIn('jornal-editor', js('document.querySelector(".artigo-atlas-meta p")?.textContent'))
                        self.assertTrue(js('document.querySelector("[data-jornal-markdown] .atlas-header") !== null'))
                        self.assertTrue(js('document.querySelector("[data-jornal-markdown] .atlas-columns") !== null'))
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.navigate', {'url': self.live_server_url + reverse('jornal_create')})
                wait_for('document.querySelector("#edMarkdown") !== null')
                js('''(() => {
                    const editor = document.querySelector('#edMarkdown');
                    editor.value = %s;
                    editor.dispatchEvent(new Event('input', { bubbles: true }));
                })()''' % json.dumps(source))
                js('''document.querySelector('#edTitulo').value = 'Prévia do Jornal';
                    document.querySelector('#edTitulo').dispatchEvent(new Event('input'));
                    document.querySelector('#edImagem').value = '/static/assets/logo.png';
                    document.querySelector('#edImagem').dispatchEvent(new Event('input'));''')
                self.assertEqual(js('document.querySelector("#edPreviewTitle").textContent'), 'Prévia do Jornal')
                self.assertFalse(js('document.querySelector("#edPreviewCover").hidden'))
                self.assertEqual(js('document.querySelector("#edPreviewCoverImage").getAttribute("src")'), '/static/assets/logo.png')
                self.assertTrue(js('document.querySelector("#edPreviewFeatured").hidden'))
                self.assertEqual(js('getComputedStyle(document.querySelector("#edPreviewFeatured")).display'), 'none')
                js('''document.querySelector('#edResumo').value = 'Resumo inicial';
                    document.querySelector('#edResumo').dispatchEvent(new Event('input'));
                    document.querySelector('#edDestaque').value = 'true';
                    document.querySelector('#edDestaque').dispatchEvent(new Event('change'));
                    document.querySelector('#edDataPublicacao').value = '2024-04-15T10:30';
                    document.querySelector('#edDataPublicacao').dispatchEvent(new Event('input'));''')
                self.assertFalse(js('document.querySelector("#edPreviewFeatured").hidden'))
                self.assertNotEqual(js('getComputedStyle(document.querySelector("#edPreviewFeatured")).display'), 'none')
                self.assertEqual(js('document.querySelector("#edPreviewDate").textContent'), '15/04/2024')
                self.assertIn('Resumo inicial', js('document.querySelector("#edPreviewSummary").textContent'))
                js('''document.querySelector('#edImagem').value = 'javascript:alert(1)';
                    document.querySelector('#edImagem').dispatchEvent(new Event('input'));''')
                self.assertTrue(js('document.querySelector("#edPreviewCover").hidden'))
                self.assertFalse(js('document.querySelector("#edPreviewCoverImage").hasAttribute("src")'))
                assert_safe('#edPreview')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                js('''document.querySelector('#edImagem').value = '/static/assets/logo.png';
                    document.querySelector('#edImagem').dispatchEvent(new Event('input'));''')
                js('document.querySelector("#edLayout").value = "atlas"; document.querySelector("#edLayout").dispatchEvent(new Event("change"))')
                self.assertTrue(js('document.querySelector("#edPreviewCover").hidden'))
                self.assertEqual(js('document.querySelector("#edPreviewTitle").textContent'), 'Prévia do Jornal')
                assert_safe('#edPreview')
                self.assertTrue(js('document.querySelector("#edPreview .atlas-columns") !== null'))
                js('window.renderBonfireMarkdown = undefined; document.querySelector("#edMarkdown").dispatchEvent(new Event("input"))')
                self.assertEqual(js('document.querySelectorAll("#edPreview img, #edPreview a").length'), 0)
                self.assertTrue(js('document.querySelector("#edPreview").textContent.includes("<img src=x")'))

                # Submit from the real browser with CSRF enforcement enabled.
                self.assertTrue(js('!!document.querySelector("#jornalEditorForm [name=csrfmiddlewaretoken]").value'))
                js('''(() => {
                    document.querySelector('#edTitulo').value = 'Jornal pelo Navegador';
                    document.querySelector('#edResumo').value = 'Resumo inicial';
                    document.querySelector('#edLayout').value = 'padrao';
                    document.querySelector('#edMarkdown').value = '**Publicado** no editor';
                    document.querySelector('#jornalEditorForm button[type=submit]').click();
                })()''')
                wait_for('location.pathname === "/mundo/jornal/jornal-pelo-navegador/" && document.querySelector(".artigo-title")?.textContent === "Jornal pelo Navegador"')
                created = TbJornal.objects.get(slug='jornal-pelo-navegador')
                self.assertEqual(created.conteudo_markdown, '**Publicado** no editor')
                self.assertEqual(created.resumo, 'Resumo inicial')
                self.assertEqual(created.imagem_url, '/static/assets/logo.png')
                self.assertTrue(created.destaque)
                self.assertEqual(created.data_publicacao.year, 2024)
                self.assertEqual(js('document.querySelector(".journal-article-figure .journal-print-image")?.getAttribute("src")'), '/static/assets/logo.png')
                self.assertIn('2024', js('document.querySelector(".artigo-meta").textContent'))
                self.assertContains(self.client.get(reverse('mundo_jornal')), 'jornal-badge-destaque')

                self.assertTrue(js('!!document.querySelector("#articleForm [name=csrfmiddlewaretoken]").value'))
                js('''(() => {
                    document.querySelector('#btnEditArticle').click();
                    document.querySelector('#articleForm [name=titulo]').value = 'Rascunho descartado';
                    document.querySelector('#articleForm [name=conteudo_markdown]').value = 'Texto descartado';
                    document.querySelector('#btnCancelArticle').click();
                })()''')
                self.assertFalse(js('document.querySelector("#articleForm").classList.contains("is-open")'))
                self.assertEqual(js('document.activeElement.id'), 'btnEditArticle')
                self.assertEqual(js('document.querySelector("#btnEditArticle").getAttribute("aria-expanded")'), 'false')
                js('document.querySelector("#btnEditArticle").click()')
                self.assertEqual(js('document.querySelector("#articleForm [name=titulo]").value'), 'Jornal pelo Navegador')
                self.assertEqual(js('document.querySelector("#articleForm [name=conteudo_markdown]").value'), '**Publicado** no editor')
                self.assertEqual(js('document.activeElement.getAttribute("name")'), 'titulo')
                js('document.querySelector("#articleForm [name=titulo]").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}))')
                self.assertFalse(js('document.querySelector("#articleForm").classList.contains("is-open")'))
                self.assertEqual(js('document.activeElement.id'), 'btnEditArticle')

                js('''(() => {
                    document.querySelector('#btnEditArticle').click();
                    document.querySelector('#articleForm [name=titulo]').value = 'Jornal Revisado';
                    document.querySelector('#articleForm [name=resumo]').value = 'Resumo revisado';
                    document.querySelector('#articleForm [name=conteudo_markdown]').value = '**Revisado** pelo editor';
                    window.qaFetch = window.fetch;
                    window.qaCalls = 0;
                    window.fetch = () => { window.qaCalls++; return new Promise(resolve => { window.qaResolve = resolve; }); };
                    document.querySelector('#articleForm').requestSubmit();
                })()''')
                wait_for('document.querySelector("#articleForm .wiki-inline-save").disabled')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                js('document.querySelector("#articleForm").dispatchEvent(new Event("submit", {cancelable:true}))')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertTrue(js('document.querySelector("#btnCancelArticle").disabled'))
                self.assertEqual(js('document.querySelector("#articleForm").getAttribute("aria-busy")'), 'true')
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}), {status:503,headers:{"Content-Type":"application/json"}}))')
                wait_for('!document.querySelector("#articleForm .wiki-inline-save").disabled')
                self.assertIn('Falha temporaria', js('document.querySelector("#articleSaveError").textContent'))
                self.assertEqual(js('document.activeElement.id'), 'articleSaveError')
                self.assertEqual(js('document.querySelector("#articleForm [name=conteudo_markdown]").value'), '**Revisado** pelo editor')
                created.refresh_from_db()
                self.assertEqual(created.titulo, 'Jornal pelo Navegador')

                js('''(() => {
                    window.fetch = window.qaFetch;
                    document.querySelector('#articleForm button[type=submit]').click();
                })()''')
                wait_for('document.querySelector(".artigo-title")?.textContent === "Jornal Revisado"')
                created.refresh_from_db()
                self.assertEqual(created.titulo, 'Jornal Revisado')
                self.assertEqual(created.resumo, 'Resumo revisado')
                self.assertEqual(created.conteudo_markdown, '**Revisado** pelo editor')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
