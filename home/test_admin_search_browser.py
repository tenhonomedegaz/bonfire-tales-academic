"""Integrated browser check for the admin dashboard search."""

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
from django.urls import reverse


class AdminSearchBrowserTests(StaticLiveServerTestCase):
    def test_search_and_keyboard_clear_keep_editorial_and_model_navigation(self):
        try:
            import websocket
        except ImportError:
            self.skipTest("websocket-client indisponivel")
        browser = shutil.which("chrome") or next((str(path) for path in (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ) if path.exists()), None)
        if not browser:
            self.skipTest("Chrome ou Edge indisponivel")

        user = get_user_model().objects.create_superuser("search-admin", "search@example.invalid", "test-pass")
        self.client.force_login(user)
        with tempfile.TemporaryDirectory(prefix="bonfire-admin-search-", ignore_cleanup_errors=True) as scratch:
            profile = Path(scratch) / "profile"
            process = subprocess.Popen([
                browser, "--headless=new", "--no-first-run", "--disable-gpu",
                "--remote-debugging-port=0", "--remote-allow-origins=*",
                f"--user-data-dir={profile}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ws = None
            try:
                port_file = profile / "DevToolsActivePort"
                for _ in range(80):
                    if port_file.exists():
                        break
                    time.sleep(.1)
                self.assertTrue(port_file.exists())
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
                        result = json.loads(ws.recv())
                        if result.get("id") == sequence:
                            self.assertNotIn("error", result, method)
                            return result["result"]

                def js(expression):
                    result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    self.assertNotIn("exceptionDetails", result, expression)
                    return result["result"].get("value")

                def until(expression):
                    for _ in range(80):
                        if js(expression):
                            return
                        time.sleep(.1)
                    self.fail(f"Tempo esgotado: {expression}")

                call("Network.enable")
                call("Network.setCookie", {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                })
                call("Emulation.setDeviceMetricsOverride", {
                    "width": 360, "height": 800, "deviceScaleFactor": 1, "mobile": True,
                })
                call("Page.navigate", {"url": self.live_server_url + reverse("admin:index")})
                until('document.readyState === "complete" && !!document.querySelector("#dashboard-search-status").textContent')
                self.assertTrue(js("document.querySelector('.bonfire-admin-tools a[href*=jornal]') !== null"))
                self.assertLessEqual(js("document.documentElement.scrollWidth"), js("document.documentElement.clientWidth"))
                js('''(() => { const input = document.querySelector('#dashboard-search-input');
                    input.value = 'CRONICAS'; input.dispatchEvent(new Event('input', {bubbles:true})); })()''')
                self.assertTrue(js('''Array.from(document.querySelectorAll('.bonfire-admin-tools a'))
                    .some(a => !a.hidden && a.textContent.includes('Revisão de crônicas'))'''))
                self.assertFalse(js('document.querySelector("#dashboard-search-clear").hidden'))
                js('''Array.from(document.querySelectorAll('.bonfire-admin-tools a'))
                    .find(a => !a.hidden && a.textContent.includes('Revisão de crônicas')).click()''')
                until('location.pathname.includes("cronicas") && document.readyState === "complete" && !!document.querySelector(".review-shell")')
                self.assertEqual(js('location.pathname'), reverse("cronicas_review"))
                call("Page.navigate", {"url": self.live_server_url + reverse("admin:index")})
                until('document.readyState === "complete" && !!document.querySelector("#dashboard-search-status").textContent')
                js('''(() => { const input = document.querySelector('#dashboard-search-input');
                    input.value = 'inexistente xyz'; input.dispatchEvent(new Event('input', {bubbles:true})); })()''')
                self.assertIn("Nenhuma tarefa", js('document.querySelector("#dashboard-search-status").textContent'))
                js('''document.querySelector('#dashboard-search-input').dispatchEvent(
                    new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));''')
                self.assertEqual(js('document.querySelector("#dashboard-search-input").value'), "")
                self.assertTrue(js('document.querySelector("#dashboard-search-clear").hidden'))
                self.assertTrue(js('''Array.from(document.querySelectorAll('.app-list .module tr'))
                    .some(row => !row.hidden && row.querySelector('a'))'''))
                self.assertLessEqual(js("document.documentElement.scrollWidth"), js("document.documentElement.clientWidth"))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                process.wait(timeout=10)
