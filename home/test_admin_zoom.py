"""Browser QA for the editorial admin at a real 200% Chrome page zoom."""

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
from django.urls import reverse


class AdminZoomBrowserTests(StaticLiveServerTestCase):
    def test_editorial_admin_remains_usable_at_200_percent(self):
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

        user = get_user_model().objects.create_superuser(
            "zoom-editor", "zoom-editor@example.invalid", "test-pass"
        )
        self.client.force_login(user)
        with tempfile.TemporaryDirectory(prefix="bonfire-admin-zoom-", ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / "profile"
            prefs = profile / "Default" / "Preferences"
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({
                "partition": {
                    "default_zoom_level": {"x": math.log(2) / math.log(1.2)}
                }
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
                self.assertTrue(port_file.is_file())
                port = port_file.read_text(encoding="utf-8").splitlines()[0]
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                    target = next(item for item in json.load(response) if item["type"] == "page")
                ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)
                sequence = 0

                def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
                    while True:
                        response = json.loads(ws.recv())
                        if response.get("id") == sequence:
                            self.assertNotIn("error", response, method)
                            return response["result"]

                def js(expression):
                    result = call("Runtime.evaluate", {
                        "expression": expression, "returnByValue": True,
                    })
                    self.assertNotIn("exceptionDetails", result, expression)
                    return result["result"].get("value")

                call("Network.enable")
                call("Network.setCookie", {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                })
                call("Page.enable")
                for name, url in (
                    ("dashboard", reverse("admin:index")),
                    ("spells", reverse("admin:home_tbmagia_changelist")),
                    ("spell_import", reverse("admin:home_tbmagia_importar_excel")),
                ):
                    call("Page.navigate", {"url": self.live_server_url + url})
                    for _ in range(80):
                        if js("document.readyState") == "complete":
                            break
                        time.sleep(.1)
                    metrics = js("JSON.stringify({width:innerWidth,outer:outerWidth,dpr:devicePixelRatio,scale:visualViewport.scale,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,title:document.title,headings:[...document.querySelectorAll('#content h1')].map(el=>el.textContent.trim())})")
                    metrics = json.loads(metrics)
                    self.assertEqual(metrics["outer"], 800, metrics)
                    self.assertAlmostEqual(metrics["dpr"], 2, delta=.05, msg=metrics)
                    self.assertEqual(metrics["scale"], 1, metrics)
                    self.assertLessEqual(metrics["scroll"], metrics["client"], f"{name}: {metrics}")
                    self.assertIn("Bonfire", metrics["title"])
                    if name == "dashboard":
                        js("(() => { const input = document.querySelector('#dashboard-search-input'); input.value = 'magias'; input.dispatchEvent(new Event('input', {bubbles: true})); input.focus(); })()")
                        self.assertTrue(js("document.querySelector('#dashboard-search-status').textContent.includes('encontrada')"))
                        self.assertTrue(js("document.querySelector('a[href*=" + json.dumps(reverse('admin:home_tbmagia_changelist')) + "]') !== null"))
                        self.assertTrue(js("[...document.querySelectorAll('#content-main .app-list .module:not([hidden]) tr:not([hidden])')].some(row => row.textContent.includes('Magias'))"))
                        js("(() => { const input = document.querySelector('#dashboard-search-input'); input.value = 'termo-inexistente-qa'; input.dispatchEvent(new Event('input', {bubbles: true})); })()")
                        self.assertTrue(js("document.querySelector('#dashboard-search-status').textContent.includes('Nenhuma tarefa')"))
                        self.assertEqual(js("document.querySelectorAll('#content-main .app-list .module:not([hidden])').length"), 0)
                        call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                        call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                        self.assertEqual(js("document.querySelector('#dashboard-search-input').value"), "")
                        self.assertTrue(js("document.querySelectorAll('#content-main .app-list .module:not([hidden])').length > 0"))
                        self.assertEqual(js("document.activeElement.id"), "dashboard-search-input")
                        js("(() => { const input = document.querySelector('#dashboard-search-input'); input.value = 'magias'; input.dispatchEvent(new Event('input', {bubbles: true})); })()")
                        js("document.querySelector('#content-main .app-list a[href*=" + json.dumps(reverse('admin:home_tbmagia_changelist')) + "]').click()")
                        for _ in range(80):
                            if js("location.pathname === " + json.dumps(reverse('admin:home_tbmagia_changelist')) + " && document.readyState === 'complete'"):
                                break
                            time.sleep(.1)
                        self.assertEqual(js("location.pathname"), reverse('admin:home_tbmagia_changelist'))
                    if name == "spell_import":
                        self.assertEqual(metrics["headings"], ["Importar magias por Excel"])
                        self.assertTrue(js('document.querySelector("input[type=file]") !== null'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
