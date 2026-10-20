"""The class catalogue remains readable and navigable on a narrow screen."""

import base64
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import TbClasse, TbClassehabilidade


class ClassCatalogReadabilityBrowserTests(StaticLiveServerTestCase):
    def test_mobile_class_search_ajax_detail_and_progression_at_200_percent(self):
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

        classe = TbClasse.objects.create(
            nome='Arcanista do QA', slug='arcanista-do-qa',
            tagline='Classe para leitura móvel.', atributo_principal='Inteligência',
            dado_vida='d8',
        )
        TbClasse.objects.create(nome='Guardião do QA', slug='guardiao-do-qa')
        TbClassehabilidade.objects.create(
            id_classe=classe, nome='Luz da Leitura',
            descricao='Texto de habilidade legível no celular.', niveladquirido=1,
        )
        mystic_fixture = json.loads((Path(__file__).parent / 'fixtures' / 'conteudo.json').read_text(encoding='utf-8'))
        feature_pks = (1428, 1431, 1444, 1446, 1332, 894, 964, 1382, 1355, 1342,
                       1181, 917, 956, 887, 910, 987, 985, 992, 993)
        mystic_features = {item['pk']: item['fields'] for item in mystic_fixture
                           if item['model'] == 'home.tbclassehabilidade'
                           and item['pk'] in feature_pks}
        for pk in feature_pks:
            TbClassehabilidade.objects.create(
                id_classe=classe, nome=mystic_features[pk]['nome'],
                descricao=mystic_features[pk]['descricao'], niveladquirido=1,
            )
        detail_url = reverse('classe_detail', kwargs={'slug': classe.slug})
        full_detail = self.client.get(detail_url)
        self.assertEqual(full_detail.status_code, 200)
        self.assertContains(full_detail, 'Texto de habilidade legível no celular.')
        self.assertContains(full_detail, 'text-[14px] leading-[1.4]')
        partial = self.client.get(detail_url + '?ajax=1')
        self.assertEqual(partial.status_code, 200)
        self.assertContains(partial, 'Texto de habilidade legível no celular.')
        self.assertContains(partial, 'text-[14px] leading-[1.4]')

        with tempfile.TemporaryDirectory(prefix='bonfire-class-readability-', ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / 'profile'
            prefs = profile / 'Default' / 'Preferences'
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({
                'partition': {'default_zoom_level': {'x': math.log(2) / math.log(1.2)}}
            }), encoding='utf-8')
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
                self.assertTrue(port_file.is_file(), 'Chrome nao iniciou.')
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
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                def wait_for(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f'Tempo esgotado: {expression}')

                call('Page.navigate', {'url': self.live_server_url + reverse('classes')})
                wait_for('document.readyState === "complete" && !!document.querySelector("[data-class-menu-toggle]")')
                self.assertAlmostEqual(js('devicePixelRatio'), 2, delta=.05)
                call('Emulation.setDeviceMetricsOverride', {
                    'width': 360, 'height': 800, 'deviceScaleFactor': 2, 'mobile': True,
                })
                js('document.querySelector("[data-class-menu-toggle]").click()')
                self.assertEqual(js('document.querySelector("[data-class-menu-toggle]").getAttribute("aria-expanded")'), 'true')
                self.assertEqual(js('document.activeElement.id'), 'classSearch')
                layout = js('''({width:innerWidth,scroll:document.documentElement.scrollWidth,
                    client:document.documentElement.clientWidth,
                    sidebar:document.querySelector('#classSidebar').getBoundingClientRect().toJSON(),
                    toggle:document.querySelector('[data-class-menu-toggle]').getBoundingClientRect().toJSON(),
                    navFont:parseFloat(getComputedStyle(document.querySelector('.class-nav-item')).fontSize)})''')
                self.assertEqual(layout['width'], 360, layout)
                self.assertLessEqual(layout['scroll'], layout['client'], layout)
                self.assertGreaterEqual(layout['sidebar']['width'], 280, layout)
                self.assertLessEqual(layout['toggle']['right'], layout['client'], layout)
                self.assertGreaterEqual(layout['navFont'], 12, layout)

                js('''(() => { const input=document.querySelector('#classSearch');
                    input.value='Arcanista do QA'; input.dispatchEvent(new Event('input', {bubbles:true}));
                    input.focus(); })()''')
                self.assertEqual(js('document.querySelectorAll(".class-nav-item:not(.hidden)").length'), 1)
                call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
                wait_for('location.pathname === ' + json.dumps(detail_url) +
                         ' && !!document.querySelector("[data-feature-list] [data-markdown]")')
                self.assertFalse(js('document.body.classList.contains("class-menu-open")'))
                self.assertLessEqual(js('document.querySelector("[data-class-menu-toggle]").getBoundingClientRect().bottom'),
                                     js('document.querySelector(".class-detail-layout h1").getBoundingClientRect().top'))
                detail = js('''({scroll:document.documentElement.scrollWidth,
                    client:document.documentElement.clientWidth,
                    feature:parseFloat(getComputedStyle(document.querySelector('[data-feature-list] [data-markdown]')).fontSize),
                    table:parseFloat(getComputedStyle(document.querySelector('.class-progression-scroll table')).fontSize),
                    tableScroll:document.querySelector('.class-progression-scroll').scrollWidth,
                    tableClient:document.querySelector('.class-progression-scroll').clientWidth,
                    rowDisplay:getComputedStyle(document.querySelector('.class-progression-table tbody tr')).display,
                    rows:document.querySelectorAll('.class-progression-table tbody tr').length})''')
                self.assertLessEqual(detail['scroll'], detail['client'], detail)
                self.assertGreaterEqual(detail['feature'], 14, detail)
                self.assertGreaterEqual(detail['table'], 12, detail)
                self.assertEqual(detail['rowDisplay'], 'grid', detail)
                self.assertEqual(detail['rows'], 20, detail)
                self.assertLessEqual(detail['tableScroll'], detail['tableClient'], detail)
                contrast = js('''(() => {
                    const title = document.querySelector('[data-feature-title]');
                    const card = title.closest('[data-feature-card]');
                    const rgb = value => value.match(/\\d+/g).slice(0, 3).map(Number);
                    const luminance = channels => channels.map(channel => {
                        const c = channel / 255;
                        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
                    }).reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
                    const foreground = luminance(rgb(getComputedStyle(title).color));
                    const background = luminance(rgb(getComputedStyle(card).backgroundColor));
                    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
                })()''')
                self.assertGreaterEqual(contrast, 4.5)
                mystic_layout = js('''(() => {
                    const card = [...document.querySelectorAll('[data-feature-card]')]
                        .find(item => item.querySelector('[data-feature-title]')?.textContent.includes('Feitiçaria Mística'));
                    const body = card?.querySelector('[data-markdown]');
                    return {paragraphs: body?.querySelectorAll('p').length || 0,
                        headings: body?.querySelectorAll('h4, h5').length || 0,
                        tables: body?.querySelectorAll('table').length || 0};
                })()''')
                self.assertGreaterEqual(mystic_layout['paragraphs'], 5, mystic_layout)
                self.assertGreaterEqual(mystic_layout['headings'], 5, mystic_layout)
                self.assertEqual(mystic_layout['tables'], 1, mystic_layout)
                other_class_layout = js('''(() => {
                    const cards = [...document.querySelectorAll('[data-feature-card]')];
                    const layout = name => {
                        const body = cards.find(item => item.querySelector('[data-feature-title]')?.textContent.includes(name))?.querySelector('[data-markdown]');
                        return {paragraphs: body?.querySelectorAll('p').length || 0,
                            headings: body?.querySelectorAll('h5, h4').length || 0,
                            lists: body?.querySelectorAll('ul').length || 0,
                            tables: body?.querySelectorAll('table').length || 0,
                            toggles: body?.querySelectorAll('details.bonfire-toggle').length || 0,
                            nested: body?.querySelectorAll('li li').length || 0};
                    };
                    return {wizard: layout('Conjura'),
                        artificer: layout('Elixires Alqu'),
                        barbarian: layout('Magia Selvagem'),
                        wizardSignature: layout('Magia Assinatura'),
                        wizardGravity: layout('Graviturgia'),
                        wizardTime: layout('Cronoturgia'),
                        druid: layout('Surto Selvagem'),
                        artificerDefender: layout('Defensor Aprimorado'),
                        barbarianRunes: layout('Runas Elementais'),
                        infusions: layout('Infus'),
                        arcaneWeapon: layout('Arma Arcana'),
                        colossalCharge: layout('Investida Colossal Aprimorada'),
                        intimidatingPresence: layout('Presen'),
                        runicAwakening: layout('Despertar R'),
                        huntCall: layout('Chamado da Ca')};
                })()''')
                self.assertGreaterEqual(other_class_layout['wizard']['paragraphs'], 7, other_class_layout)
                self.assertGreaterEqual(other_class_layout['wizard']['headings'], 4, other_class_layout)
                self.assertGreaterEqual(other_class_layout['artificer']['paragraphs'], 7, other_class_layout)
                self.assertGreaterEqual(other_class_layout['artificer']['lists'], 1, other_class_layout)
                self.assertGreaterEqual(other_class_layout['barbarian']['paragraphs'], 3, other_class_layout)
                self.assertEqual(other_class_layout['barbarian']['tables'], 1, other_class_layout)
                for feature in ('wizardSignature', 'wizardGravity', 'wizardTime'):
                    self.assertGreaterEqual(other_class_layout[feature]['paragraphs'], 2,
                                            (feature, other_class_layout))
                self.assertGreaterEqual(other_class_layout['druid']['paragraphs'], 10,
                                        other_class_layout)
                self.assertGreaterEqual(other_class_layout['druid']['headings'], 5,
                                        other_class_layout)
                self.assertEqual(other_class_layout['druid']['tables'], 4,
                                 other_class_layout)
                self.assertGreaterEqual(other_class_layout['artificerDefender']['paragraphs'], 5,
                                        other_class_layout)
                self.assertGreaterEqual(other_class_layout['artificerDefender']['lists'], 1,
                                        other_class_layout)
                self.assertEqual(other_class_layout['barbarianRunes']['tables'], 1,
                                 other_class_layout)
                for feature in ('infusions', 'arcaneWeapon'):
                    self.assertEqual(other_class_layout[feature]['toggles'], 1,
                                     (feature, other_class_layout))
                    self.assertGreaterEqual(other_class_layout[feature]['paragraphs'], 3,
                                            (feature, other_class_layout))
                for feature in ('colossalCharge', 'intimidatingPresence',
                                'runicAwakening', 'huntCall'):
                    self.assertGreaterEqual(other_class_layout[feature]['lists'], 1,
                                            (feature, other_class_layout))
                self.assertGreaterEqual(other_class_layout['colossalCharge']['nested'], 1,
                                        other_class_layout)
                mystic_heading = js('''(() => {
                    const heading = [...document.querySelectorAll('[data-markdown] h4')]
                        .find(item => item.textContent.includes('Truques'));
                    return {weight: parseInt(getComputedStyle(heading).fontWeight, 10),
                        size: parseFloat(getComputedStyle(heading).fontSize)};
                })()''')
                self.assertGreaterEqual(mystic_heading['size'], 14, mystic_heading)
                self.assertGreaterEqual(mystic_heading['weight'], 600, mystic_heading)
                other_sections = js('''(() => {
                    const card = name => [...document.querySelectorAll('[data-feature-card]')]
                        .find(item => item.querySelector('[data-feature-title]')?.textContent.includes(name));
                    return {toggle: card('Manifestação Mística Aprimorada')?.querySelectorAll('.bonfire-toggle, .subtopic-btn').length || 0,
                        table: card('Receptáculo do Gênio')?.querySelectorAll('table').length || 0,
                        list: card('Sussurro dos Antigos')?.querySelectorAll('li').length || 0};
                })()''')
                self.assertGreater(other_sections['toggle'], 0, other_sections)
                self.assertEqual(other_sections['table'], 1, other_sections)
                self.assertGreaterEqual(other_sections['list'], 2, other_sections)
                toggle_state = js('''(() => {
                    const card = [...document.querySelectorAll('[data-feature-card]')]
                        .find(item => item.querySelector('[data-feature-title]')?.textContent.includes('Manifestação Mística Aprimorada'));
                    const buttons = card.querySelectorAll('.subtopic-btn');
                    buttons[1].click();
                    const panels = card.querySelectorAll('.h1-group-panel');
                    return {count: buttons.length, active: buttons[1].classList.contains('is-active'),
                        firstHidden: getComputedStyle(panels[0]).display === 'none',
                        secondVisible: getComputedStyle(panels[1]).display !== 'none'};
                })()''')
                self.assertGreaterEqual(toggle_state['count'], 2, toggle_state)
                self.assertTrue(toggle_state['active'] and toggle_state['firstHidden']
                                and toggle_state['secondVisible'], toggle_state)
                self.assertEqual(js('sanitizeBonfireMarkdownHtml("<button onclick=alert(1)>Unsafe</button>")'), '')
                screenshot_path = os.environ.get('BONFIRE_QA_CLASS_SCREENSHOT')
                if screenshot_path:
                    screenshot = call('Page.captureScreenshot', {'captureBeyondViewport': True})
                    Path(screenshot_path).write_bytes(base64.b64decode(screenshot['data']))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
