from importlib import import_module
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.db import connection
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase
from django.templatetags.static import static
from django.urls import reverse

from .models import TbConteudoEstatico, TbMapLayer, TbRegiao, TbTerritorio
from .views import _parse_lore_topics


class WorldLorePresentationTests(TestCase):
    def test_world_editorial_default_cover_cannot_break_css_url(self):
        from .admin import _ConteudoEstaticoForm
        from .views import _world_cover_fallback, _world_cover_url

        unsafe = "https://example.com/a.png');--hero-bg:url(https://evil.invalid/x)"
        form = _ConteudoEstaticoForm(data={
            'chave': 'mundo-capa-padrao', 'pagina': 'mundo', 'imagem_url': unsafe,
            'ordem': '0', 'ativo': 'on',
        })
        self.assertTrue(form.is_valid())  # Delimitadores são codificados na apresentação.
        TbConteudoEstatico.objects.update_or_create(
            chave='mundo-capa-padrao', defaults={'pagina': 'mundo', 'imagem_url': unsafe, 'ativo': True},
        )
        self.assertEqual(
            _world_cover_fallback(),
            'https://example.com/a.png%27%29;--hero-bg:url%28https://evil.invalid/x%29',
        )
        self.assertEqual(_world_cover_url('', _world_cover_fallback()), _world_cover_fallback())
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        TbTerritorio.objects.create(nome='Território editorial', slug='territorio-editorial', camada=0)
        listing = self.client.get(reverse('mundo_regioes'))
        self.assertContains(listing, "--territory-image: url('%s')" % _world_cover_fallback())
        self.assertNotContains(listing, "a.png');--hero-bg")

        TbConteudoEstatico.objects.filter(chave='mundo-capa-padrao').update(imagem_url='javascript:alert(1)')
        self.assertEqual(_world_cover_fallback(), '')
        self.assertNotContains(self.client.get(reverse('mundo_regioes')), 'javascript:alert(1)')

    def test_generated_region_covers_resolve_without_replacing_editorial_images(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superficie', 'ordem': 0, 'publica': True},
        )
        territory = TbTerritorio.objects.create(nome='Teste', slug='teste', camada=0)
        migration = import_module('home.migrations.0129_world_region_covers')
        regions = {}
        for slug, cover in migration.REGION_COVERS.items():
            self.assertIsNotNone(finders.find(cover))
            regions[slug] = TbRegiao.objects.create(
                nome=slug.replace('-', ' ').title(), slug=slug,
                territorio=territory.nome, camada=0,
            )
        original = TbRegiao.objects.create(
            nome='Auralon', slug='auralon', territorio=territory.nome,
            camada=0, brasao_url='https://example.invalid/original-auralon.png',
        )

        migration.assign_region_covers(apps, None)
        for slug, cover in migration.REGION_COVERS.items():
            region = regions[slug]
            region.refresh_from_db()
            self.assertEqual(region.brasao_url, cover)
            detail = self.client.get(reverse('regiao_detail', args=[slug]))
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.context['imagem_url'], static(cover))
            self.assertContains(detail, static(cover))

        first = self.client.get(reverse('regiao_detail', args=['agrabbar']))
        cards = {item['slug']: item for item in first.context['client_regions']}
        for slug, cover in migration.REGION_COVERS.items():
            self.assertEqual(cards[slug]['imagem_url'], static(cover))
        self.assertEqual(cards['auralon']['imagem_url'], original.brasao_url)

        regions['velaryn'].brasao_url = 'https://example.invalid/editorial-velaryn.png'
        regions['velaryn'].save(update_fields=['brasao_url'])
        migration.assign_region_covers(apps, None)
        regions['velaryn'].refresh_from_db()
        self.assertEqual(regions['velaryn'].brasao_url,
                         'https://example.invalid/editorial-velaryn.png')

    def test_generated_territory_covers_resolve_in_catalog_and_details(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superficie', 'ordem': 0, 'publica': True},
        )
        migrations = [
            import_module('home.migrations.0127_world_territory_covers'),
            import_module('home.migrations.0128_remaining_world_territory_covers'),
        ]
        covers = {slug: cover for migration in migrations
                  for slug, cover in migration.TERRITORY_COVERS.items()}
        territories = {}
        for slug, cover in covers.items():
            self.assertIsNotNone(finders.find(cover))
            territories[slug] = TbTerritorio.objects.create(
                nome=slug.replace('-', ' ').title(), slug=slug, camada=0,
            )

        for migration in migrations:
            migration.assign_territory_covers(apps, None)
        listing = self.client.get(reverse('mundo_regioes'))
        self.assertEqual(listing.status_code, 200)
        cards = {card['slug']: card for card in listing.context['territorios_cards']}
        for slug, cover in covers.items():
            territory = territories[slug]
            territory.refresh_from_db()
            self.assertEqual(territory.imagem_url, cover)
            self.assertEqual(cards[slug]['imagem_url'], static(cover))
            detail = self.client.get(reverse('territorio_detail', args=[slug]))
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.context['imagem_url'], static(cover))

        territory = territories['reino-eryndor']
        territory.imagem_url = 'https://example.invalid/approved-editorial.png'
        territory.save(update_fields=['imagem_url'])
        for migration in migrations:
            migration.assign_territory_covers(apps, None)
        territory.refresh_from_db()
        self.assertEqual(territory.imagem_url, 'https://example.invalid/approved-editorial.png')

    def test_realm_cover_matches_reference_without_changing_auralon_image(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superficie', 'ordem': 0, 'publica': True},
        )
        realm = TbTerritorio.objects.create(
            nome='Reino Auraliano', slug='reino-auraliano', camada=0,
        )
        auralon_image = 'https://i.imgur.com/KIAfZx2.png'
        city = TbRegiao.objects.create(
            nome='Auralon', slug='auralon', territorio=realm.nome,
            camada=0, brasao_url=auralon_image,
        )
        migration = import_module('home.migrations.0126_reino_auraliano_cover')
        self.assertIsNotNone(finders.find(migration.REALM_COVER))

        migration.assign_realm_cover(apps, None)
        realm.refresh_from_db()
        city.refresh_from_db()
        self.assertEqual(realm.imagem_url, migration.REALM_COVER)
        self.assertEqual(city.brasao_url, auralon_image)

        cover_url = static(migration.REALM_COVER)
        listing = self.client.get(reverse('mundo_regioes'))
        card = next(item for item in listing.context['territorios_cards']
                    if item['slug'] == realm.slug)
        self.assertEqual(card['imagem_url'], cover_url)
        detail = self.client.get(reverse('territorio_detail', args=[realm.slug]))
        self.assertEqual(detail.context['imagem_url'], cover_url)
        self.assertEqual(detail.context['client_territories'][realm.nome]['imagem_url'], cover_url)

        realm.imagem_url = 'https://example.invalid/editorial.png'
        realm.save(update_fields=['imagem_url'])
        migration.assign_realm_cover(apps, None)
        realm.refresh_from_db()
        self.assertEqual(realm.imagem_url, 'https://example.invalid/editorial.png')

    def test_staff_can_find_regions_missing_their_own_image(self):
        TbRegiao.objects.create(nome='Região sem imagem', slug='regiao-sem-imagem')
        TbRegiao.objects.create(nome='Região vazia', slug='regiao-vazia', brasao_url='')
        TbRegiao.objects.create(
            nome='Região ilustrada', slug='regiao-ilustrada',
            brasao_url='https://example.invalid/regiao.png',
        )
        staff = get_user_model().objects.create_superuser(
            username='region-editor', email='region@example.invalid', password='test-password',
        )
        self.client.force_login(staff)
        url = reverse('admin:home_tbregiao_changelist')

        missing = self.client.get(url, {'imagem_propria': 'pendente'})
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(
            {item.nome for item in missing.context['cl'].result_list},
            {'Região sem imagem', 'Região vazia'},
        )
        covered = self.client.get(url, {'imagem_propria': 'pronta'})
        self.assertEqual(covered.status_code, 200)
        self.assertEqual(
            [item.nome for item in covered.context['cl'].result_list],
            ['Região ilustrada'],
        )
        self.assertContains(covered, 'https://example.invalid/regiao.png')

    def test_staff_can_find_territories_missing_their_own_cover(self):
        TbTerritorio.objects.create(nome='Sem imagem', slug='sem-imagem')
        TbTerritorio.objects.create(nome='Imagem vazia', slug='imagem-vazia', imagem_url='')
        TbTerritorio.objects.create(
            nome='Com imagem', slug='com-imagem', imagem_url='https://example.invalid/capa.png',
        )
        TbTerritorio.objects.create(
            nome='Imagem local', slug='imagem-local', imagem_url='assets/cineria.jpg',
        )
        staff = get_user_model().objects.create_superuser(
            username='cover-editor', email='cover@example.invalid', password='test-password',
        )
        self.client.force_login(staff)
        url = reverse('admin:home_tbterritorio_changelist')

        missing = self.client.get(url, {'capa_propria': 'pendente'})
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(
            {item.nome for item in missing.context['cl'].result_list},
            {'Sem imagem', 'Imagem vazia'},
        )
        covered = self.client.get(url, {'capa_propria': 'pronta'})
        self.assertEqual(covered.status_code, 200)
        self.assertEqual(
            {item.nome for item in covered.context['cl'].result_list},
            {'Com imagem', 'Imagem local'},
        )
        self.assertContains(covered, 'https://example.invalid/capa.png')
        self.assertContains(covered, static('assets/cineria.jpg'))

    def test_explicit_overview_does_not_create_empty_duplicate(self):
        topics = _parse_lore_topics(
            'Introducao editorial.\n## Visão Geral\nCorpo.\n## História\nPrimeira.\n'
            '## História\nSegunda.'
        )
        self.assertEqual([topic['title'] for topic in topics],
                         ['Visão Geral', 'História', 'História'])
        self.assertEqual([topic['slug'] for topic in topics],
                         ['base', 'historia', 'historia-2'])
        self.assertIn('Introducao editorial.', topics[0]['content'][0])
        self.assertIn('Corpo.', topics[0]['content'][0])
        self.assertEqual(_parse_lore_topics('   '), [])

    def test_region_and_territory_use_explicit_covers_or_shared_placeholder(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superficie', 'ordem': 0, 'publica': True},
        )
        territory = TbTerritorio.objects.create(
            nome='Vale Azul', slug='vale-azul', camada=0,
            lore_markdown='## Visão Geral\nTerritório.',
        )
        region = TbRegiao.objects.create(
            nome='Cidade A', slug='cidade-a', territorio=territory.nome,
            camada=0, brasao_url='https://example.invalid/a.png',
            lore_markdown='## Visão Geral\nCidade.',
        )
        TbRegiao.objects.create(
            nome='Cidade B', slug='cidade-b', territorio=territory.nome,
            camada=0,
        )
        placeholder = static('assets/fire_background.png')
        listing = self.client.get(reverse('mundo_regioes'))
        self.assertEqual(listing.status_code, 200)
        card = next(card for card in listing.context['territorios_cards']
                    if card['slug'] == territory.slug)
        self.assertEqual(card['imagem_url'], placeholder)
        self.assertContains(listing, f'href="{reverse("territorio_detail", args=[territory.slug])}"')
        self.assertContains(listing, f'href="{reverse("mapa")}?region={region.slug}"')
        self.assertNotContains(listing, "onclick=\"location.href=")

        detail = self.client.get(reverse('territorio_detail', args=[territory.slug]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context['imagem_url'], placeholder)
        self.assertEqual(detail.context['client_territories'][territory.nome]['imagem_url'],
                         placeholder)
        self.assertEqual([topic['title'] for topic in detail.context['lore_topics']],
                         ['Visão Geral'])
        self.assertContains(detail, 'data-topic-slug="base"', count=1)
        region_detail = self.client.get(reverse('regiao_detail', args=[region.slug]))
        self.assertEqual(region_detail.context['imagem_url'],
                         'https://example.invalid/a.png')

        editor = get_user_model().objects.create_superuser(
            username='world-cover-editor', email='editor@example.invalid', password='test-only',
        )
        self.client.force_login(editor)
        admin_save = self.client.post(reverse('admin:home_tbconteudoestatico_add'), {
            'chave': 'mundo-capa-padrao', 'pagina': 'mundo',
            'titulo': 'Capa padrão do Mundo', 'subtitulo': '',
            'conteudo_markdown': '', 'imagem_url': 'https://example.invalid/mundo.png',
            'cta_texto': '', 'cta_url': '', 'ativo': 'on', 'ordem': '0',
        })
        self.assertEqual(admin_save.status_code, 302)
        self.client.logout()
        fallback = TbConteudoEstatico.objects.get(chave='mundo-capa-padrao')
        listing = self.client.get(reverse('mundo_regioes'))
        card = next(card for card in listing.context['territorios_cards']
                    if card['slug'] == territory.slug)
        self.assertEqual(card['imagem_url'], fallback.imagem_url)
        self.assertContains(listing, f"--territory-image: url('{fallback.imagem_url}')")
        detail = self.client.get(reverse('territorio_detail', args=[territory.slug]))
        self.assertEqual(detail.context['imagem_url'], fallback.imagem_url)
        self.assertContains(detail, f"--hero-bg: url('{fallback.imagem_url}')")
        self.assertEqual(detail.context['client_territories'][territory.nome]['imagem_url'],
                         fallback.imagem_url)
        self.assertEqual(next(item for item in detail.context['client_regions']
                              if item['slug'] == 'cidade-b')['imagem_url'], fallback.imagem_url)
        region_detail = self.client.get(reverse('regiao_detail', args=[region.slug]))
        self.assertEqual(region_detail.context['imagem_url'], region.brasao_url)
        self.assertEqual(region_detail.context['territory_image_url'], fallback.imagem_url)

        fallback.ativo = False
        fallback.save(update_fields=['ativo'])
        self.assertEqual(self.client.get(reverse('territorio_detail', args=[territory.slug]))
                         .context['imagem_url'], placeholder)
        fallback.ativo = True
        fallback.save(update_fields=['ativo'])

        territory.imagem_url = 'https://example.invalid/vale.png'
        territory.save(update_fields=['imagem_url'])
        listing = self.client.get(reverse('mundo_regioes'))
        card = next(card for card in listing.context['territorios_cards']
                    if card['slug'] == territory.slug)
        self.assertEqual(card['imagem_url'], territory.imagem_url)
        detail = self.client.get(reverse('territorio_detail', args=[territory.slug]))
        self.assertEqual(detail.context['imagem_url'], territory.imagem_url)
        self.assertEqual(next(item for item in detail.context['client_regions']
                              if item['slug'] == 'cidade-b')['imagem_url'], territory.imagem_url)

    def test_staff_region_edit_persists_and_public_detail_remains_available(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        territory = TbTerritorio.objects.create(nome='Vale editorial', slug='vale-editorial', camada=0)
        region = TbRegiao.objects.create(
            nome='Cidade editorial', slug='cidade-editorial', territorio=territory.nome,
            camada=0, lore_markdown='## Visão Geral\nTexto inicial.',
        )
        editor = get_user_model().objects.create_superuser(
            username='editor-regiao', email='editor-regiao@example.invalid', password='test-only',
        )
        self.client.force_login(editor)
        response = self.client.post(
            reverse('wiki_update_region', args=[region.pk]),
            data=json.dumps({
                'nome': region.nome, 'territorio': territory.nome,
                'lore_markdown': '## Visão Geral\nLore revisada no editor.',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect'], reverse('regiao_detail', args=[region.slug]))
        region.refresh_from_db()
        self.assertEqual(region.lore_markdown, '## Visão Geral\nLore revisada no editor.')
        self.client.logout()
        self.assertContains(self.client.get(reverse('regiao_detail', args=[region.slug])),
                            'Lore revisada no editor.')


class WorldLoreBrowserSafetyTests(StaticLiveServerTestCase):
    def test_world_lore_and_editor_keep_hostile_content_literal_at_360px(self):
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

        injected = '<img src=x onerror="window.__worldInjected=1">'
        territory_name = f'Vale {injected}'
        region_name = f'Cidade {injected}'
        territory_lore = f'## História {injected}\n**Seguro**\n[color=page]Brasa[/color]\n<svg onload="window.__worldInjected=1"></svg>'
        region_lore = f'## História {injected}\n**Seguro**\n<a href="javascript:window.__worldInjected=1">Inseguro</a>'
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        TbTerritorio.objects.create(
            nome=territory_name, slug='vale-literal', camada=0,
            lore_markdown=territory_lore, descricao_breve=f'Descrição </textarea>{injected}',
        )
        TbRegiao.objects.create(
            nome=region_name, slug='cidade-literal', territorio=territory_name,
            camada=0, lore_markdown=region_lore,
            brasao_url=f'/static/missing.png" onerror="window.__worldInjected=1',
            etiquetas_adicionais=f'Magia, {injected}',
        )
        TbRegiao.objects.create(
            nome='Cidade órfã', slug='cidade-orfa', territorio='Território ausente', camada=0,
        )
        TbRegiao.objects.create(nome='Cidade solta', slug='cidade-solta', camada=0)
        editor = get_user_model().objects.create_superuser(
            username='world-browser-editor', email='world-browser@example.invalid', password='test-only',
        )
        self.client.force_login(editor)
        session_key = self.client.cookies['sessionid'].value

        with tempfile.TemporaryDirectory(prefix='bonfire-world-', ignore_cleanup_errors=True) as profile:
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
                call('Network.enable')
                call('Network.setCookie', {
                    'name': 'sessionid', 'value': session_key, 'url': self.live_server_url,
                })

                call('Page.navigate', {'url': self.live_server_url + reverse('regiao_detail', args=['cidade-literal'])})
                wait_for('document.querySelector("#regionForm input[name=nome]")?.value.includes("Cidade")')
                self.assertEqual(js('document.querySelector("#regionForm input[name=nome]").value'), region_name)
                self.assertEqual(js('document.querySelector("#regionForm textarea[name=lore_markdown]").value'), region_lore)
                self.assertIn(injected, js('document.querySelector("#regionForm input[name=etiquetas_adicionais]").value'))
                self.assertTrue(js('document.querySelector("#currentTopicTitle").textContent.includes(' + json.dumps(injected) + ')'))
                self.assertEqual(js('document.querySelectorAll("#articleContent img, #articleContent svg, #articleContent a[href^=javascript], .topic-nav img").length'), 0)
                self.assertEqual(js('document.querySelector("#activeTopicBody strong")?.textContent'), 'Seguro')
                self.assertFalse(js('window.__worldInjected === 1'))

                call('Page.navigate', {'url': self.live_server_url + reverse('territorio_detail', args=['vale-literal'])})
                wait_for('document.querySelector("#territoryForm input[name=nome]")?.value.includes("Vale")')
                self.assertEqual(js('document.querySelector("#territoryForm input[name=nome]").value'), territory_name)
                self.assertEqual(js('document.querySelector("#territoryForm textarea[name=lore_markdown]").value'), territory_lore)
                self.assertTrue(js('document.querySelector("#territoryForm textarea[name=descricao_breve]").value.includes("</textarea>" )'))
                self.assertEqual(js('document.querySelectorAll("#articleContent img, #articleContent svg, .topic-nav img").length'), 0)
                self.assertEqual(js('document.querySelector("#activeTopicBody strong")?.textContent'), 'Seguro')
                self.assertEqual(js('document.querySelector(".bonfire-color-page")?.textContent'), 'Brasa')
                self.assertFalse(js('window.__worldInjected === 1'))

                region_path = reverse('regiao_detail', args=['cidade-literal'])
                territory_path = reverse('territorio_detail', args=['vale-literal'])
                for group_name, region_slug, region_title in (
                    ('Território ausente', 'cidade-orfa', 'Cidade órfã'),
                    ('Sem território', 'cidade-solta', 'Cidade solta'),
                ):
                    js('document.querySelector("#regionMobileMenuButton").click()')
                    orphan_summary = ('[...document.querySelectorAll(".region-mobile-drawer [data-territory-title]")]'
                                      '.find(node => node.dataset.territoryTitle === ' + json.dumps(group_name) + ')')
                    self.assertTrue(js('Boolean(' + orphan_summary + ')'))
                    js(orphan_summary + '.click()')
                    self.assertEqual(js('location.pathname'), territory_path)
                    self.assertEqual(js('document.querySelector("#articleTitle").textContent'), territory_name)
                    self.assertTrue(js(orphan_summary + '.closest("details").open'))
                    js('document.querySelector(".region-mobile-drawer [data-region-link=' + region_slug + ']").click()')
                    wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(region_title))
                    self.assertEqual(js('location.pathname'), reverse('regiao_detail', args=[region_slug]))
                    js('history.back()')
                    wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(territory_name))
                    self.assertEqual(js('location.pathname'), territory_path)
                js('document.querySelector("#regionMobileMenuButton").click()')
                self.assertTrue(js('document.body.classList.contains("region-menu-open")'))
                js('document.querySelector(".region-mobile-drawer [data-region-link=cidade-literal]").click()')
                wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(region_name))
                self.assertEqual(js('location.pathname'), region_path)
                self.assertFalse(js('document.body.classList.contains("region-menu-open")'))
                self.assertEqual(js('document.activeElement?.id'), 'articleTitle')

                js('history.back()')
                wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(territory_name))
                self.assertEqual(js('location.pathname'), territory_path)
                js('history.forward()')
                wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(region_name))
                self.assertEqual(js('location.pathname'), region_path)

                js('document.querySelector(".region-mobile-drawer [data-territory-title]").click();'
                   'document.querySelector(".region-mobile-drawer [data-region-link=cidade-literal]").click()')
                time.sleep(.35)
                self.assertEqual(js('document.querySelector("#articleTitle")?.textContent'), region_name)
                self.assertEqual(js('location.pathname'), region_path)
                history_length = js('history.length')
                js('document.querySelector(".region-mobile-drawer [data-region-link=cidade-literal]").click()')
                self.assertEqual(js('history.length'), history_length)

                # 768 px a 200% equivale a uma area util de 384 CSS px.
                call('Emulation.setEmulatedMedia', {'features': [
                    {'name': 'prefers-reduced-motion', 'value': 'reduce'},
                ]})
                for width in (360, 384):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 800, 'deviceScaleFactor': 1, 'mobile': True,
                    })
                    call('Page.navigate', {'url': self.live_server_url + territory_path})
                    wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(territory_name))
                    js('document.querySelector("#regionMobileMenuButton").click()')
                    self.assertTrue(js('document.body.classList.contains("region-menu-open")'))
                    self.assertLessEqual(js('document.querySelector("#regionMobileMenuButton").getBoundingClientRect().right'), js('innerWidth'))
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
                    self.assertEqual(js('getComputedStyle(document.querySelector("#regionMobileDrawer")).transitionDuration'), '0s')
                    js('document.querySelector(".region-mobile-drawer [data-region-link=cidade-solta]").click()')
                    self.assertEqual(js('document.querySelector("#articleTitle").textContent'), 'Cidade solta')
                    self.assertEqual(js('document.activeElement?.id'), 'articleTitle')
                for width in (768, 1280, 1920):
                    call('Emulation.setDeviceMetricsOverride', {
                        'width': width, 'height': 800, 'deviceScaleFactor': 1, 'mobile': width <= 768,
                    })
                    call('Page.navigate', {'url': self.live_server_url + territory_path})
                    wait_for('document.querySelector("#articleTitle")?.textContent === ' + json.dumps(territory_name))
                    self.assertLessEqual(js('document.documentElement.scrollWidth'), js('innerWidth'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
