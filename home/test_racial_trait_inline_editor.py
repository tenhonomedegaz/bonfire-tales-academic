"""Browser QA for base traits and racial talents in the inline editor."""

import json
import math
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
from django.test import TestCase
from django.urls import reverse

from home.models import TbRaca, TbTracoracial


class RacialTraitInlineEditorTests(StaticLiveServerTestCase):
    def test_base_trait_and_racial_talent_edit_at_real_zoom(self):
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

        race = TbRaca.objects.create(nome='Povo Editorial', slug='povo-editorial')
        base = TbTracoracial.objects.create(
            id_raca=race, nome='Traço Base', descricao='Texto base publicado',
        )
        talent = TbTracoracial.objects.create(
            id_raca=race, nome='Talento Racial', descricao='Texto talento publicado',
            talento_racial=True, nivel_requisito=1,
        )
        editor = get_user_model().objects.create_superuser('trait-editor', 'trait@example.invalid', 'pass')
        self.client.force_login(editor)
        with tempfile.TemporaryDirectory(prefix='bonfire-trait-editor-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({'partition': {
                'default_zoom_level': {'x': math.log(2) / math.log(1.2)},
            }}), encoding='utf-8')
            process = subprocess.Popen([
                chrome, '--headless=new', '--no-first-run', '--disable-gpu',
                '--remote-debugging-port=0', '--remote-allow-origins=*',
                f'--user-data-dir={profile}', '--window-size=800,900', 'about:blank',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / 'DevToolsActivePort'
                for _ in range(80):
                    if port_file.is_file():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.is_file())
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
                        response = json.loads(ws.recv())
                        if response.get('id') == sequence:
                            self.assertNotIn('error', response, method)
                            return response['result']

                def js(expression):
                    result = call('Runtime.evaluate', {
                        'expression': expression, 'returnByValue': True, 'awaitPromise': True,
                    })
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def until(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Network.enable')
                call('Network.setCookie', {
                    'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'url': self.live_server_url,
                })
                call('Page.enable')
                call('Page.navigate', {'url': self.live_server_url + reverse('raca_detail', args=[race.slug])})
                until('document.readyState === "complete" && !!document.querySelector("[data-race-trait-card]")')
                metrics = json.loads(js('JSON.stringify({dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth})'))
                self.assertAlmostEqual(metrics['dpr'], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics['scale'], 1, metrics)
                self.assertLessEqual(metrics['scroll'], metrics['client'], metrics)
                js('window.qaBaseId=%d;window.qaTalentId=%d' % (base.pk, talent.pk))
                js('window.qaCard=id=>Array.from(document.querySelectorAll("[data-race-trait-card]")).find(card=>card.dataset.traitId===String(id))')
                js('document.querySelector("[data-tab-btn=regras]").click()')
                js('window.qaBaseCard=window.qaCard(window.qaBaseId)')
                self.assertIn('Texto base publicado', js('window.qaBaseCard.querySelector("[data-trait-preview]").textContent'))

                js('window.qaBaseCard.querySelector("[data-trait-edit]").click()')
                self.assertEqual(js('document.activeElement.name'), 'descricao')
                js('''{let field=window.qaBaseCard.querySelector('[name=descricao]');
                    field.value='Rascunho';field.dispatchEvent(new Event('input'));
                    field.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));}''')
                self.assertFalse(js('window.qaBaseCard.querySelector("[data-trait-form]").classList.contains("is-open")'))
                self.assertIn('Texto base publicado', js('window.qaBaseCard.querySelector("[data-trait-preview]").textContent'))
                self.assertEqual(js('window.qaBaseCard.querySelector("[name=descricao]").value'), 'Texto base publicado')
                self.assertTrue(js('document.activeElement.hasAttribute("data-trait-edit")'))
                js('''window.qaBaseCard.querySelector('[data-trait-edit]').click();
                    window.qaBaseCard.querySelector('[name=descricao]').value='Outro rascunho';
                    window.qaBaseCard.querySelector('[name=descricao]').dispatchEvent(new Event('input'));
                    window.qaBaseCard.querySelector('[data-trait-cancel]').click();''')
                self.assertIn('Texto base publicado', js('window.qaBaseCard.querySelector("[data-trait-preview]").textContent'))

                js('''window.qaBaseCard.querySelector('[data-trait-edit]').click();
                    window.qaBaseCard.querySelector('[name=nome]').value='Traco Revisado';
                    window.qaBaseCard.querySelector('[name=descricao]').value='Texto base revisado';
                    window.qaBaseCard.querySelector('[name=descricao]').dispatchEvent(new Event('input'));
                    window.qaBaseCard.querySelector('[name=tags_json_text]').value='tag-qa';
                    window.qaFetch=window.fetch;window.qaCalls=0;
                    window.fetch=()=>{window.qaCalls++;return new Promise(resolve=>window.qaResolve=resolve)};
                    window.qaBaseCard.querySelector('[data-trait-form]').requestSubmit();''')
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                until('window.qaBaseCard.querySelector("[data-trait-form]").getAttribute("aria-busy") === "true"')
                js('window.qaBaseCard.querySelector("[data-trait-form]").dispatchEvent(new Event("submit",{cancelable:true}))')
                self.assertEqual(js('window.qaCalls'), 1)
                self.assertTrue(js('window.qaBaseCard.querySelector("[data-trait-cancel]").disabled'))
                js('window.qaResolve(new Response(JSON.stringify({error:"Falha temporaria"}),{status:503,headers:{"Content-Type":"application/json"}}))')
                until('!window.qaBaseCard.querySelector("[data-trait-cancel]").disabled')
                self.assertIn('Falha temporaria', js('window.qaBaseCard.querySelector(".wiki-inline-error").textContent'))
                self.assertEqual(js('document.activeElement.className'), 'wiki-inline-error')
                self.assertEqual(js('window.qaBaseCard.querySelector("[name=descricao]").value'), 'Texto base revisado')
                base.refresh_from_db()
                self.assertEqual(base.descricao, 'Texto base publicado')

                js('window.fetch=window.qaFetch;window.qaBaseCard.querySelector("[data-trait-form]").requestSubmit()')
                until('window.qaCard(window.qaBaseId)?.querySelector("[data-trait-title]")?.textContent === "Traco Revisado"')
                base.refresh_from_db()
                self.assertEqual(base.descricao, 'Texto base revisado')
                self.assertEqual(base.tags_json, ['tag-qa'])
                self.assertEqual(js('document.querySelector("#raceDetailContainer").getAttribute("data-active-tab")'), 'regras')
                self.assertTrue(js('document.activeElement.hasAttribute("data-trait-edit")'))

                js('document.querySelector("[data-tab-btn=talentos]").click()')
                js('window.qaTalentCard=window.qaCard(window.qaTalentId)')
                self.assertTrue(js('!!window.qaTalentCard'))
                js('''window.qaTalentCard.querySelector('[data-trait-edit]').click();
                    window.qaTalentCard.querySelector('[name=descricao]').value='Texto talento revisado';
                    window.qaTalentCard.querySelector('[name=descricao]').dispatchEvent(new Event('input'));
                    window.qaTalentCard.querySelector('[name=pre_requisito]').value='Forca 12';
                    window.qaTalentCard.querySelector('[name=pre_requisito]').dispatchEvent(new Event('input',{bubbles:true}));''')
                self.assertIn('Forca 12', js('window.qaTalentCard.querySelector("[data-trait-prereq]").textContent'))
                js('window.qaTalentCard.querySelector("[data-trait-form]").requestSubmit()')
                until('window.qaCard(window.qaTalentId)?.querySelector("[data-trait-preview]")?.textContent.includes("Texto talento revisado") && !window.qaCard(window.qaTalentId)?.querySelector("[data-trait-form]")?.classList.contains("is-open")')
                talent.refresh_from_db()
                self.assertEqual(talent.descricao, 'Texto talento revisado')
                self.assertEqual(talent.pre_requisito, 'Forca 12')
                self.assertEqual(js('document.querySelector("#raceDetailContainer").getAttribute("data-active-tab")'), 'talentos')
                self.assertTrue(js('document.activeElement.hasAttribute("data-trait-edit")'))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                call('Page.reload')
                until('document.readyState === "complete" && document.querySelector("#raceDetailContainer")?.textContent.includes("Texto talento revisado")')
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


class RacialTraitBooleanContractTests(TestCase):
    def test_editor_accepts_boolean_representations_and_rejects_invalid_value(self):
        race = TbRaca.objects.create(nome='Povo', slug='povo')
        trait = TbTracoracial.objects.create(id_raca=race, nome='Traço', descricao='Texto')
        staff = get_user_model().objects.create_user('trait-staff', password='pass', is_staff=True)
        self.client.force_login(staff)
        url = reverse('wiki_update_racial_trait', args=[trait.pk])
        for raw, expected in (('false', False), ('true', True), (0, False), (1, True), (False, False), (True, True)):
            response = self.client.post(url, json.dumps({'talento_racial': raw}), content_type='application/json')
            self.assertEqual(response.status_code, 200, raw)
            trait.refresh_from_db()
            self.assertEqual(trait.talento_racial, expected, raw)
        rejected = self.client.post(url, json.dumps({
            'nome': 'Nome indevido', 'talento_racial': 'talvez',
        }), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        trait.refresh_from_db()
        self.assertEqual(trait.nome, 'Traço')
        self.assertTrue(trait.talento_racial)
