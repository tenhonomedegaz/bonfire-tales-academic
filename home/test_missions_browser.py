"""Official mission schedule and synopsis in the integrated mobile/desktop page."""

import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse


class MissionsBrowserTests(StaticLiveServerTestCase):
    def test_official_mission_schedule_and_synopsis_at_mobile_and_desktop_widths(self):
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

        quest = SimpleNamespace(
            id='qa-mission', name='Travessia das Brumas',
            description='A ponte se abre.\nO grupo decide o caminho.',
            questDate=datetime(2026, 11, 5, 1, 30, tzinfo=timezone.utc),
            playersAmount=4, questPlayers=[], participationRequests=[], subscribedPlayers=[],
            mandatoryPlayers=[], highPriorityPlayers=[], status='idle', type='Aventura',
            tags=[], questMaster='Mestre QA', tableUrl='', guildId='', channelId='',
        )
        queryset = MagicMock()
        queryset.exclude.return_value = queryset
        queryset.order_by.return_value.__getitem__.return_value = [quest]

        with tempfile.TemporaryDirectory(prefix='bonfire-missions-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([
                browser, '--headless=new', '--no-sandbox', '--disable-gpu',
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
                            self.assertNotIn('error', result, method)
                            return result['result']

                def js(expression):
                    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                    self.assertNotIn('exceptionDetails', result, expression)
                    return result['result'].get('value')

                with patch('home.models.BotQuest.objects.filter', return_value=queryset):
                    for width in (360, 1440):
                        call('Emulation.setDeviceMetricsOverride', {
                            'width': width, 'height': 900, 'deviceScaleFactor': 1,
                            'mobile': width == 360,
                        })
                        call('Page.navigate', {'url': self.live_server_url + reverse('sistemas_missoes')})
                        for _ in range(80):
                            if js('document.readyState === "complete" && !!document.querySelector(".mh-quest")'):
                                break
                            time.sleep(.1)
                        self.assertTrue(js('!!document.querySelector(".mh-quest")'))
                        self.assertLessEqual(js('document.documentElement.scrollWidth'), width)
                        self.assertIn('04/11/2026 · 22:30 · Brasília',
                                      js('document.querySelector(".mh-quest time").textContent'))
                        self.assertFalse(js('document.querySelector(".mh-synopsis").open'))
                        js('document.querySelector(".mh-synopsis summary").click()')
                        self.assertTrue(js('document.querySelector(".mh-synopsis").open'))
                        self.assertIn('O grupo decide o caminho.',
                                      js('document.querySelector(".mh-synopsis p").textContent'))
            finally:
                if ws:
                    ws.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
