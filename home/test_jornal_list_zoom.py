"""Browser QA for the public Jornal listing with real Chrome page zoom."""

import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from .models import TbJornal


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

        TbJornal.objects.create(titulo="Notícia em destaque", slug="noticia-destaque", resumo="Resumo do artigo", destaque=True)
        TbJornal.objects.create(titulo="Notícia comum", slug="noticia-comum", resumo="Outro resumo")
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
                    if js("document.readyState") == "complete" and js('document.querySelectorAll(".jornal-card").length') == 2:
                        break
                    time.sleep(.1)
                metrics = json.loads(js("JSON.stringify({outer:outerWidth,dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,cards:document.querySelectorAll('.jornal-card').length,featured:document.querySelectorAll('.jornal-card.is-destaque').length,bg:getComputedStyle(document.querySelector('.jornal-hero')).backgroundImage})"))
                self.assertEqual(metrics["outer"], 800, metrics)
                self.assertAlmostEqual(metrics["dpr"], 2, delta=.05, msg=metrics)
                self.assertEqual(metrics["scale"], 1, metrics)
                self.assertEqual(metrics["cards"], 2, metrics)
                self.assertEqual(metrics["featured"], 1, metrics)
                self.assertLessEqual(metrics["scroll"], metrics["client"], metrics)
                self.assertIn("radial-gradient", metrics["bg"])
                self.assertNotIn("url(", metrics["bg"])
                self.assertTrue(js("[...document.querySelectorAll('.jornal-card')].every(card => card.getBoundingClientRect().right <= document.documentElement.clientWidth)"))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
