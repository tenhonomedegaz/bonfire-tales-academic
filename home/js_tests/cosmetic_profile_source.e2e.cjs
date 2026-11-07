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
    const origin = process.env.PROFILE_SOURCE_ORIGIN;
    const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
    await context.addCookies([{ name: 'sessionid', value: process.env.PROFILE_SOURCE_SESSION,
      url: origin, httpOnly: true }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const width of [360, 1280]) {
      await page.setViewportSize({ width, height: 800 });
      const response = await page.goto(origin + '/perfil/', { waitUntil: 'networkidle' });
      assert.equal(response.status(), 200);
      const theme = page.locator('.tema-swatch').filter({ hasText: 'Tema do evento' });
      assert.equal(await theme.count(), 1);
      assert.equal(await theme.locator('.tema-swatch-source').innerText(), 'Resgate de evento');
      assert.equal(await theme.locator('input').isEnabled(), true);
      assert.match(await page.locator('#id_avatar_frame option[value="paga-visual"]').innerText(),
        /Compra confirmada/);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      assert.ok(overflow <= 1, `${width}px: horizontal overflow ${overflow}px`);
      if (process.env.BONFIRE_ARTIFACT_DIR) {
        fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR,
          `cosmetic-profile-source-${width}.png`), fullPage: true });
      }
    }
    assert.deepEqual(errors, []);
    console.log('Profile sources: mobile and desktop OK');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
