"""E2E opt-in do Pathbuilder: navegador real contra template, API e engine reais."""
import json
import os
import shutil
import subprocess
import unittest

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from home.models import TbPersonagem, TbRegra
from home.test_criador import _CriadorBase


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_ROOT, "home", "js_tests", "pathbuilder.e2e.cjs")


@unittest.skipUnless(
    os.environ.get("BONFIRE_PLAYWRIGHT_MODULE"),
    "E2E opt-in: configure BONFIRE_PLAYWRIGHT_MODULE para o Playwright existente.",
)
class PathbuilderRealE2ETests(StaticLiveServerTestCase):
    """Um fluxo único para não recarregar o fixture grande em cada caso."""

    _novo_usuario = _CriadorBase._novo_usuario
    _payload = _CriadorBase._payload

    @classmethod
    def setUpClass(cls):
        if connection.vendor != "postgresql" or not connection.settings_dict["NAME"].startswith("test_"):
            raise unittest.SkipTest("E2E requer PostgreSQL isolado em banco test_.")
        super().setUpClass()

    def setUp(self):
        super().setUp()
        # StaticLiveServerTestCase limpa o banco entre métodos desta classe.
        # A migration cria esta regra com PK local; o fixture traz a linha canônica.
        TbRegra.objects.filter(slug="aumento-de-atributo").delete()
        call_command("loaddata", "home/fixtures/conteudo.json", verbosity=0)
        self.user = self._novo_usuario("pathbuilder-e2e")
        self.client.force_login(self.user)

    def test_fluxo_real_resiliente_preview_reload_sem_persistencia(self):
        """Template+JS+API reais preservam uma edição e nunca salvam personagem."""
        session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        payload = self._payload("guerreiro")
        builds = [{
            "modo": "sandbox",
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "atributos_bonus": {}, "escolhas": {}, "talentos": [],
            "talentos_raciais": [], "itens": [], "magias": [],
        }, {
            "modo": "sandbox",
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "atributos_bonus": {}, "escolhas": {}, "talentos": [],
            "talentos_raciais": [], "itens": [], "magias": [],
        }]
        before = TbPersonagem.objects.count()
        env = os.environ.copy()
        env.update({
            "PATHBUILDER_E2E_URL": self.live_server_url,
            "PATHBUILDER_E2E_COOKIE_NAME": settings.SESSION_COOKIE_NAME,
            "PATHBUILDER_E2E_COOKIE_VALUE": session_cookie,
            "PATHBUILDER_E2E_BASE": json.dumps(payload),
            "PATHBUILDER_E2E_BUILDS": json.dumps(builds),
        })
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js não está disponível para executar o Playwright.")
        try:
            completed = subprocess.run(
                [node, _SCRIPT], cwd=_ROOT, env=env, text=True,
                capture_output=True, timeout=360, check=False,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired as exc:
            output = '\n'.join(
                part.decode('utf-8', errors='replace') if isinstance(part, bytes) else part
                for part in (exc.stdout, exc.stderr) if part
            )
            self.fail("E2E do Pathbuilder excedeu o timeout de 360 s: %s\n%s" % (
                exc, output))
        if completed.returncode:
            self.fail("E2E do Pathbuilder falhou.\nSTDOUT:\n%s\nSTDERR:\n%s" % (
                completed.stdout, completed.stderr))
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_q09_q10_revisao_de_mago_preserva_selecao(self):
        payload = self._payload('mago')
        before = TbPersonagem.objects.count()
        env = dict(os.environ,
            PATHBUILDER_E2E_URL=self.live_server_url,
            PATHBUILDER_E2E_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
            PATHBUILDER_E2E_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            PATHBUILDER_E2E_BASE=json.dumps(payload))
        result = subprocess.run(['node', os.path.join(_ROOT, 'home/js_tests/pathbuilder_review.e2e.cjs')],
            cwd=_ROOT, env=env, capture_output=True, encoding='utf-8', timeout=100)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_q15_planar_menus_at_creation(self):
        before = TbPersonagem.objects.count()
        env = dict(os.environ, PATHBUILDER_E2E_URL=self.live_server_url,
            PATHBUILDER_E2E_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
            PATHBUILDER_E2E_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            result = subprocess.run(['node', os.path.join(_ROOT, 'home/js_tests/planar_creation.e2e.cjs')],
                cwd=_ROOT, env=env, capture_output=True, encoding='utf-8', timeout=90)
        print(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_s10_teclado_e_larguras_da_matriz(self):
        """Navega nas etapas reais e verifica que a ficha cabe em cada largura do aceite."""
        base = self._payload('guerreiro')
        build = {
            'modo': 'sandbox',
            'classes': [{'slug': 'guerreiro', 'nivel': 4, 'subclasse': ''}],
            'atributos_bonus': {}, 'escolhas': {}, 'talentos': [],
            'talentos_raciais': [], 'itens': [], 'magias': [],
        }
        before = TbPersonagem.objects.count()
        env = dict(os.environ,
            PATHBUILDER_E2E_URL=self.live_server_url,
            PATHBUILDER_E2E_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
            PATHBUILDER_E2E_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value,
            PATHBUILDER_E2E_BASE=json.dumps(base),
            PATHBUILDER_E2E_BUILDS=json.dumps([build, build]))
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);
(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    const context = await browser.newContext();
    const origin = process.env.PATHBUILDER_E2E_URL;
    await context.addCookies([{ name: process.env.PATHBUILDER_E2E_COOKIE_NAME,
      value: process.env.PATHBUILDER_E2E_COOKIE_VALUE, url: origin }]);
    await context.addInitScript(({ base, builds }) => {
      localStorage.setItem('bonfire:pathbuilder:base', JSON.stringify(base));
      localStorage.setItem('bonfire:pathbuilder:builds', JSON.stringify(builds));
    }, { base: JSON.parse(process.env.PATHBUILDER_E2E_BASE),
      builds: JSON.parse(process.env.PATHBUILDER_E2E_BUILDS) });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/sistemas/pathbuilder/laboratorio/');
    await page.locator('#pb-folha [data-pb-folha]').waitFor();
    const tab = page.locator('[data-step-tab="1"]');
    await tab.focus();
    await page.keyboard.press('Enter');
    assert.equal(await tab.getAttribute('aria-current'), 'step');
    assert.equal(await page.locator('[data-step="1"]').isVisible(), true);
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('[data-step-tab="2"]').evaluate(
      element => element === document.activeElement), true);
    await page.keyboard.press('Space');
    assert.equal(await page.locator('[data-step-tab="2"]').getAttribute('aria-current'), 'step');
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const dimensions = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        content: document.documentElement.scrollWidth,
      }));
      assert.ok(dimensions.content <= dimensions.viewport + 1,
        `${width}px: conteúdo ${dimensions.content}px, viewport ${dimensions.viewport}px`);
      for (const selector of ['#pb-status', '.pb-head-tools', '.pb-sheet']) {
        const box = await page.locator(selector).boundingBox();
        assert.ok(box && box.x >= -1 && box.x + box.width <= width + 1,
          `${width}px: ${selector} fora da tela`);
      }
      if (process.env.S10_SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.S10_SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({
          path: path.join(process.env.S10_SCREENSHOT_DIR, `pathbuilder-${width}.png`),
          fullPage: true,
        });
      }
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(['node', '-e', script], cwd=_ROOT, env=env,
            capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(TbPersonagem.objects.count(), before)
