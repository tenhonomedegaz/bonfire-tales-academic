const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    const origin = process.env.PRIMAL_ORIGIN;
    const paths = JSON.parse(process.env.PRIMAL_PATHS);
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    context.setDefaultTimeout(12000);
    await context.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.abort());
    await context.addCookies([{ name: process.env.PRIMAL_COOKIE_NAME, value: process.env.PRIMAL_COOKIE_VALUE, url: origin }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const tab = name => page.locator('[data-sn-tab]').filter({ hasText: name }).first();
    async function snapshot(name) {
      if (!process.env.BONFIRE_ARTIFACT_DIR) return;
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, name+'.png'), fullPage: true });
    }
    async function confirm() {
      await tab('Confirmar').click();
      const response = page.waitForResponse(r => r.request().method()==='POST' && r.url().includes('/aplicar'));
      await page.locator('[data-sn-confirm]').click();
      const result = await response;
      assert.equal(result.status(), 200);
      await page.waitForTimeout(200);
    }
    for (const choice of ['guardiao', 'xama']) {
      await page.goto(origin+paths[choice]);
      await tab('Opções de classe').click();
      const card = page.locator('[data-slug=ordem_primal]');
      const select = card.locator('select');
      assert.deepEqual(await select.locator('option').evaluateAll(items => items.map(o=>o.value)), ['', 'xama', 'guardiao']);
      await select.selectOption(choice);
      await snapshot(choice+'-choice');
      await confirm();
      await page.goto(origin+paths[choice]);
      assert.equal(await page.locator('[data-slug=ordem_primal] select').count(), 0);
      if (choice==='xama') {
        await page.setViewportSize({ width: 360, height: 800 });
        await tab('Magias concedidas').click();
        const spells = page.locator('[data-lvl-card=magias_concedidas] input[type=checkbox]');
        assert.equal(await spells.count(), 3);
        await spells.nth(0).check();
        await spells.nth(1).check();
        assert.equal(await spells.nth(2).isDisabled(), true);
        await snapshot('xama-spells-mobile');
        await confirm();
        await page.goto(origin+paths[choice]);
        assert.equal(await page.locator('[data-lvl-card=magias_concedidas]').count(), 0);
      }
      console.log(choice+': escolha persistida e recarregada');
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
