"""Browser QA for public editorial pages with real Chrome page zoom."""

import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse

from .models import TbConteudoEstatico, TbJornal, TbMapLayer, TbRegiao, TbTerritorio, UserProfile


class JornalListZoomTests(StaticLiveServerTestCase):
    def test_cards_and_hero_at_real_200_percent_zoom(self):
        if connection.vendor != "postgresql" or not connection.settings_dict["NAME"].startswith("test_"):
            self.skipTest("Requer PostgreSQL de teste isolado")
        try:
            import websocket
        except ImportError:
            self.skipTest("websocket-client indisponivel")
        chrome = shutil.which("chrome") or next((str(path) for path in (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ) if path.exists()), None)
        if not chrome:
            self.skipTest("Chrome ou Edge indisponivel")

        TbJornal.objects.create(titulo="Notícia em destaque", slug="noticia-destaque", resumo="Resumo do artigo", destaque=True,
                                imagem_url="/static/assets/logo.png")
        TbJornal.objects.create(titulo="Notícia comum", slug="noticia-comum", resumo="Outro resumo")
        TbJornal.objects.create(titulo="Capa antiga", slug="capa-antiga", imagem_url="/static/assets/logo.png');color:red;--evil:'")
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={"nome": "Superfície", "ordem": 0, "publica": True},
        )
        TbTerritorio.objects.create(
            nome="Território de teste", slug="territorio-zoom-qa", camada=0,
            lore_markdown="## Visão Geral\nUm território com história para leitura.",
        )
        TbRegiao.objects.create(
            nome="Região de teste", slug="regiao-zoom-qa", territorio="Território de teste",
            camada=0, lore_markdown="## Visão Geral\nUma região com história para leitura.",
        )
        TbConteudoEstatico.objects.create(
            chave="sobre-zoom-qa", pagina="sobre", titulo="Sobre o Bonfire Tales",
            conteudo_markdown="Conheça a comunidade Bonfire Tales.",
        )
        with tempfile.TemporaryDirectory(prefix="bonfire-jornal-zoom-", ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / "profile"
            prefs = profile / "Default" / "Preferences"
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({
                "partition": {"default_zoom_level": {"x": math.log(2) / math.log(1.2)}}
            }), encoding="utf-8")
            process = subprocess.Popen([
                chrome, "--headless=new", "--no-first-run", "--disable-gpu",
                "--remote-debugging-port=0", "--remote-allow-origins=*",
                f"--user-data-dir={profile}", "--window-size=800,900", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / "DevToolsActivePort"
                for _ in range(80):
                    if port_file.is_file():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.is_file(), "Chrome não iniciou")
                with urlopen(f"http://127.0.0.1:{port_file.read_text().splitlines()[0]}/json", timeout=5) as response:
                    target = next(item for item in json.load(response) if item["type"] == "page")
                ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
                    while True:
                        result = json.loads(ws.recv())
                        if result.get("id") == sequence:
                            self.assertNotIn("error", result, method)
                            return result["result"]

                def js(expression):
                    result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    self.assertNotIn("exceptionDetails", result, expression)
                    return result["result"].get("value")

                call("Page.enable")
                call("Page.navigate", {"url": self.live_server_url + reverse("mundo_jornal")})
                for _ in range(80):
                    if js("document.readyState") == "complete" and js('document.querySelectorAll(".jornal-card").length') == 3:
                        break
                    time.sleep(.1)
                metrics = json.loads(js("JSON.stringify({outer:outerWidth,dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,cards:document.querySelectorAll('.jornal-card').length,featured:document.querySelectorAll('.jornal-card.is-destaque').length,bg:getComputedStyle(document.querySelector('.jornal-hero')).backgroundImage})"))
                self.assertEqual(metrics["outer"], 800, metrics)
                self.assertAlmostEqual(metrics["dpr"], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics["scale"], 1, metrics)
                self.assertEqual(metrics["cards"], 3, metrics)
                self.assertEqual(metrics["featured"], 1, metrics)
                self.assertLessEqual(metrics["scroll"], metrics["client"], metrics)
                self.assertIn("radial-gradient", metrics["bg"])
                self.assertNotIn("url(", metrics["bg"])
                self.assertTrue(js("[...document.querySelectorAll('.jornal-card')].every(card => card.getBoundingClientRect().right <= document.documentElement.clientWidth)"))
                self.assertEqual(js("document.querySelector('.jornal-card[href$=\"capa-antiga/\"] .jornal-card-cover').style.getPropertyValue('color')"), "")
                self.assertEqual(js("document.querySelector('.jornal-card[href$=\"capa-antiga/\"] .jornal-card-cover').style.getPropertyValue('--evil')"), "")
                call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
                card_point = json.loads(js("JSON.stringify((()=>{const e=document.querySelector('.jornal-card');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})())"))
                call("Input.dispatchMouseEvent", {"type": "mouseMoved", **card_point})
                self.assertTrue(js("document.querySelector('.jornal-card').matches(':hover')"))
                self.assertEqual(js("getComputedStyle(document.querySelector('.jornal-card')).transform"), "none")
                self.assertEqual(js("getComputedStyle(document.querySelector('.jornal-card')).transitionDuration"), "0s")
                for route_name, route_args, selector in (
                    ("home", [], "#home-primary-action"),
                    ("mundo_regioes", [], ".territory-card"),
                    ("territorio_detail", ["territorio-zoom-qa"], "#articleTitle"),
                    ("regiao_detail", ["regiao-zoom-qa"], "#articleTitle"),
                    ("sobre", [], "main h1"),
                ):
                    call("Page.navigate", {"url": self.live_server_url + reverse(route_name, args=route_args)})
                    for _ in range(80):
                        if js("document.readyState") == "complete" and js(f'document.querySelector("{selector}") !== null') and (
                            route_name not in ("territorio_detail", "regiao_detail") or
                            js('document.querySelector("#articleTitle").textContent.includes("de teste")')
                        ):
                            break
                        time.sleep(.1)
                    page = json.loads(js("JSON.stringify({dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,h1:document.querySelectorAll('main h1').length})"))
                    self.assertAlmostEqual(page["dpr"], 2, delta=.05, msg=(route_name, page))
                    self.assertEqual(page["scale"], 1, (route_name, page))
                    self.assertLessEqual(page["scroll"], page["client"], (route_name, page))
                    self.assertEqual(page["h1"], 1, (route_name, page))
                    if route_name == "mundo_regioes":
                        card_point = json.loads(js("JSON.stringify((()=>{const e=document.querySelector('.territory-card');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})())"))
                        call("Input.dispatchMouseEvent", {"type": "mouseMoved", **card_point})
                        self.assertTrue(js("document.querySelector('.territory-card').matches(':hover')"))
                        self.assertEqual(js("getComputedStyle(document.querySelector('.territory-card-bg')).transform"), "none")
                        self.assertEqual(js("getComputedStyle(document.querySelector('.territory-card-bg')).transitionDuration"), "0s")
                editor = get_user_model().objects.create_superuser(
                    username="world-zoom-editor", email="world-zoom@example.invalid", password="test-only",
                )
                self.client.force_login(editor)
                call("Network.enable")
                call("Network.setCookie", {
                    "name": "sessionid", "value": self.client.cookies["sessionid"].value,
                    "url": self.live_server_url,
                })
                call("Page.navigate", {"url": self.live_server_url + reverse("mundo_regioes")})
                for _ in range(80):
                    if js('document.querySelector("#btnNewRegion") !== null'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('document.querySelector("#btnNewRegion") !== null'))
                js('document.querySelector("#btnNewRegion").focus()')
                call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "text": "\r", "windowsVirtualKeyCode": 13})
                call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                self.assertTrue(js('document.querySelector("#newRegionModal").open'))
                self.assertEqual(js('document.querySelector("#newRegionModal").getAttribute("aria-labelledby")'), 'newRegionModalTitle')
                self.assertTrue(js('document.querySelector("#newRegionModalTitle").textContent.includes("Criar")'))
                call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                self.assertFalse(js('document.querySelector("#newRegionModal").open'))
                self.assertEqual(js('document.activeElement.id'), 'btnNewRegion')
                js('document.querySelector("#btnNewRegion").click()')
                self.assertTrue(js("[...document.querySelectorAll('#newRegionModal input, #newRegionModal select, #newRegionModal textarea, #newRegionModal button')].filter(e => e.getClientRects().length).every(e => e.getBoundingClientRect().right <= document.documentElement.clientWidth + 1)"))
                self.assertLessEqual(js('document.documentElement.scrollWidth'), js('document.documentElement.clientWidth'))
                js("document.querySelector('#nr-nome').value = 'Regiao modal QA'")
                js("document.querySelector('#nr-territorio').value = " + json.dumps(TbTerritorio.objects.get(slug='territorio-zoom-qa').nome))
                js('document.querySelector("#btnSaveNewRegion").click()')
                for _ in range(80):
                    if js('location.pathname === ' + json.dumps(reverse('regiao_detail', args=['regiao-modal-qa'])) + ' && document.readyState === "complete"'):
                        break
                    time.sleep(.1)
                created_region = TbRegiao.objects.get(slug='regiao-modal-qa')
                self.assertEqual(created_region.territorio, TbTerritorio.objects.get(slug='territorio-zoom-qa').nome)
                self.assertEqual(js('location.pathname'), reverse('regiao_detail', args=[created_region.slug]))
                self.assertContains(Client().get(reverse('regiao_detail', args=[created_region.slug])), 'Regiao modal QA')
                call('Page.navigate', {'url': self.live_server_url + reverse('mundo_regioes')})
                for _ in range(80):
                    if js('document.querySelector("#btnNewRegion") !== null'):
                        break
                    time.sleep(.1)
                js('document.querySelector("#btnNewRegion").click()')
                js('document.querySelector("#btnShowCreateTerritoryRegion").click()')
                self.assertEqual(js('document.activeElement.id'), 'ntr-nome')
                js('document.querySelector("#btnCancelCreateTerritoryRegion").click()')
                self.assertEqual(js('document.activeElement.id'), 'btnShowCreateTerritoryRegion')
                js('document.querySelector("#btnShowCreateTerritoryRegion").click()')
                js("document.querySelector('#ntr-nome').value = 'Territorio inline QA'")
                js('document.querySelector("#btnConfirmCreateTerritoryRegion").click()')
                for _ in range(80):
                    if js('document.querySelector("#nr-territorio").value === "Territorio inline QA"'):
                        break
                    time.sleep(.1)
                created_territory = TbTerritorio.objects.get(slug='territorio-inline-qa')
                self.assertEqual(js('document.querySelector("#nr-territorio").value'), created_territory.nome)
                self.assertEqual(js('document.activeElement.id'), 'nr-territorio')
                self.assertEqual(js('document.querySelector("#createTerritorySectionRegion").style.display'), 'none')
                js("document.querySelector('#nr-nome').value = 'Regiao inline QA'")
                js('document.querySelector("#btnSaveNewRegion").click()')
                for _ in range(80):
                    if js('location.pathname === ' + json.dumps(reverse('regiao_detail', args=['regiao-inline-qa'])) + ' && document.readyState === "complete"'):
                        break
                    time.sleep(.1)
                linked_region = TbRegiao.objects.get(slug='regiao-inline-qa')
                self.assertEqual(linked_region.territorio, created_territory.nome)
                self.assertContains(Client().get(reverse('regiao_detail', args=[linked_region.slug])), 'Regiao inline QA')
                call("Page.navigate", {"url": self.live_server_url + reverse("regiao_detail", args=["regiao-zoom-qa"])})
                for _ in range(80):
                    if js('document.querySelector("#btnEditRegion") !== null'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('document.querySelector("#btnEditRegion") !== null'))
                js('document.querySelector("#btnEditRegion").click()')
                self.assertTrue(js('document.querySelector("#regionForm").classList.contains("is-open")'))
                js('document.querySelector("#btnEditRegion").focus()')
                for _ in range(2):
                    call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                    call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                self.assertEqual(js("document.activeElement.id"), "edit-nr-territorio")
                self.assertEqual(js("getComputedStyle(document.activeElement).outlineStyle"), "solid")
                self.assertEqual(js("getComputedStyle(document.activeElement).outlineWidth"), "2px")
                self.assertLessEqual(js("document.querySelector('#regionForm').getBoundingClientRect().right"), js("document.documentElement.clientWidth"))
                self.assertLessEqual(js("document.activeElement.getBoundingClientRect().right"), js("document.documentElement.clientWidth"))
                self.assertTrue(js("[...document.querySelectorAll('#regionForm input, #regionForm select, #regionForm textarea, #regionForm button')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().right<=document.documentElement.clientWidth+1)"))
                self.assertTrue(js("document.querySelector('#regionForm').checkValidity()"))
                js("""(()=>{
                    const originalFetch = window.fetch.bind(window);
                    window.fetch = async (...args) => {
                        const response = await originalFetch(...args);
                        if (String(args[0]).includes('/wiki/regioes/')) {
                            sessionStorage.setItem('region-save-qa', JSON.stringify({
                                status: response.status, body: await response.clone().text()
                            }));
                        }
                        return response;
                    };
                    document.querySelector('#regionForm [name=lore_markdown]').value =
                        '## Visão Geral\\nLore salva pelo navegador.';
                    document.querySelector('#regionForm').requestSubmit();
                })()""")
                save_result = None
                for _ in range(80):
                    stored = js("sessionStorage.getItem('region-save-qa')")
                    if stored:
                        save_result = json.loads(stored)
                        break
                    time.sleep(.1)
                self.assertIsNotNone(save_result, "POST do editor não respondeu")
                self.assertEqual(save_result["status"], 200, save_result)
                saved_region = TbRegiao.objects.get(nome="Região de teste")
                self.assertEqual(json.loads(save_result["body"])["redirect"],
                                 reverse("regiao_detail", args=[saved_region.slug]))
                for _ in range(80):
                    if js("document.readyState") == "complete" and js("document.body.textContent.includes('Lore salva pelo navegador.')"):
                        break
                    time.sleep(.1)
                self.assertTrue(js("document.body.textContent.includes('Lore salva pelo navegador.')"),
                                js("JSON.stringify({url:location.href,text:document.body.textContent.slice(0,250)})"))
                self.assertEqual(js("location.pathname"), reverse("regiao_detail", args=[saved_region.slug]))
                call("Page.navigate", {"url": self.live_server_url + reverse("territorio_detail", args=["territorio-zoom-qa"])})
                for _ in range(80):
                    if js('document.querySelector("#btnEditTerritory") !== null'):
                        break
                    time.sleep(.1)
                self.assertTrue(js('document.querySelector("#btnEditTerritory") !== null'))
                js('document.querySelector("#btnEditTerritory").click()')
                self.assertTrue(js("[...document.querySelectorAll('#territoryForm input, #territoryForm textarea, #territoryForm button')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().right<=document.documentElement.clientWidth+1)"))
                js("document.querySelector('#territoryForm [name=lore_markdown]').value = '## Visão Geral\\nLore do território salva pelo navegador.'")
                js("document.querySelector('#territoryForm').requestSubmit()")
                for _ in range(80):
                    if js("document.readyState") == "complete" and js("document.body.textContent.includes('Lore do território salva pelo navegador.')"):
                        break
                    time.sleep(.1)
                self.assertTrue(js("document.body.textContent.includes('Lore do território salva pelo navegador.')"),
                                js("JSON.stringify({url:location.href,text:document.body.textContent.slice(0,250)})"))
                self.assertEqual(js("location.pathname"), reverse("territorio_detail", args=["territorio-zoom-qa"]))
                profile = UserProfile.objects.get_or_create(user=editor)[0]
                profile.banner_url = "https://cdn.example/banner.png');color:red;--evil:'"
                profile.background_url = "https://cdn.example/bg.png');color:red;--evil:'"
                profile.save()
                call("Page.navigate", {"url": self.live_server_url + reverse("jogadores")})
                for _ in range(80):
                    if js("document.readyState") == "complete" and js("document.querySelector('.player-card-banner span') !== null"):
                        break
                    time.sleep(.1)
                self.assertEqual(js("document.querySelector('.player-card-banner span').style.color"), "")
                self.assertEqual(js("document.querySelector('.player-card-banner span').style.getPropertyValue('--evil')"), "")
                self.assertLessEqual(js("document.documentElement.scrollWidth"), js("document.documentElement.clientWidth"))
                call("Page.navigate", {"url": self.live_server_url + reverse("public_profile", args=[editor.username])})
                for _ in range(80):
                    if js("document.readyState") == "complete" and js("document.querySelector('.public-profile-banner-media') !== null"):
                        break
                    time.sleep(.1)
                self.assertEqual(js("document.querySelector('.public-profile-banner-media').style.color"), "")
                self.assertEqual(js("document.querySelector('.profile-bg-media').style.getPropertyValue('--evil')"), "")
                self.assertLessEqual(js("document.documentElement.scrollWidth"), js("document.documentElement.clientWidth"))
                call("Page.navigate", {"url": self.live_server_url + reverse("jornal_detail", args=["capa-antiga"])})
                for _ in range(80):
                    if js("document.readyState") == "complete" and js("document.querySelector('.artigo-hero') !== null"):
                        break
                    time.sleep(.1)
                self.assertEqual(js("document.querySelector('.artigo-hero').style.getPropertyValue('color')"), "")
                self.assertEqual(js("document.querySelector('.artigo-hero').style.getPropertyValue('--evil')"), "")
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
