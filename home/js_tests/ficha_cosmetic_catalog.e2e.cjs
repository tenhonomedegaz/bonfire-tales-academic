const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH }
      : { channel: 'msedge' }) });
  try {
    const origin = process.env.FICHA_COSMETIC_ORIGIN;
    const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
    await context.addCookies([{ name: 'sessionid', value: process.env.FICHA_COSMETIC_SESSION,
      url: origin, httpOnly: true }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const width of [360, 1280]) {
      await page.setViewportSize({ width, height: 800 });
      const response = await page.goto(origin + process.env.FICHA_COSMETIC_PATH,
        { waitUntil: 'domcontentloaded' });
      assert.equal(response.status(), 200);
      await page.getByRole('tab', { name: 'Informações' }).click();
      const owned = page.locator('.tema-swatch').filter({ hasText: 'Tema Evento' });
      const locked = page.locator('.tema-swatch').filter({ hasText: 'Tema Bloqueado' });
      assert.equal(await owned.count(), 1);
      assert.equal(await owned.locator('.tema-swatch-source').innerText(), 'Resgate de evento');
      assert.equal(await owned.locator('input').isEnabled(), true);
      assert.equal(await locked.locator('input').isDisabled(), true);
      const rect = await page.locator('#ficha-theme-group').boundingBox();
      assert.ok(rect && rect.x >= 0 && rect.x + rect.width <= width + 1,
        `${width}px: theme selector exceeds viewport`);
      if (process.env.BONFIRE_ARTIFACT_DIR) {
        fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR,
          `ficha-cosmetic-${width}.png`), fullPage: true });
      }
    }
    assert.deepEqual(errors, []);
    console.log('Ficha cosmetic catalog: mobile and desktop OK');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
