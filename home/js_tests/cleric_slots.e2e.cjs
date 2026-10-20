const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    const origin = process.env.Q04_ORIGIN;
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    context.setDefaultTimeout(15000);
    await context.route('**/*', r => r.request().url().startsWith(origin) ? r.continue() : r.abort());
    await context.addCookies([{ name: process.env.Q04_COOKIE_NAME, value: process.env.Q04_COOKIE_VALUE, url: origin }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const url = origin + process.env.Q04_PATH;
    await page.goto(url);
    const card = page.locator('[data-spell-slot-card][data-slot-level="5"]');
    assert.equal(await card.locator('[data-slot-total]').innerText(), '3');
    assert.equal(await card.locator('[data-slot-atual]').innerText(), '3');
    const artifacts = process.env.BONFIRE_ARTIFACT_DIR;
    if (artifacts) {
      fs.mkdirSync(artifacts, { recursive: true });
      await page.screenshot({ path: path.join(artifacts, 'cleric-desktop.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 360, height: 800 });
    for (const remaining of [2, 1, 0]) {
      const response = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes('/usar-slot-magia/'));
      await card.locator('[data-slot-action="gastar"]').click();
      assert.equal((await response).status(), 200);
      await page.waitForFunction(() => document.querySelector('[data-slot-level="5"]').getAttribute('aria-busy') === 'false');
      assert.equal(await card.locator('[data-slot-atual]').innerText(), String(remaining));
      assert.equal(await page.locator('[data-slot-summary="5"]').innerText(), `${remaining}/3`);
      assert.equal(page.url(), url);
    }
    assert.equal(await card.locator('[data-slot-action="gastar"]').isDisabled(), true);
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'cleric-mobile.png'), fullPage: true });
    await page.reload();
    assert.equal(await card.locator('[data-slot-atual]').innerText(), '0');
    assert.equal(await card.locator('[data-slot-total]').innerText(), '3');
    assert.deepEqual(errors, []);
    console.log('Q04: três gastos, bloqueio no limite, círculo/cartão e reload aprovados; 1280/360px.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
