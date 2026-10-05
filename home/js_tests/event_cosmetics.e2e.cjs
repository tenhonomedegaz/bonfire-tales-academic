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
    const origin = process.env.EVENT_SHOP_ORIGIN;
    const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
    await context.addCookies([{ name: 'sessionid', value: process.env.EVENT_SHOP_SESSION,
      url: origin, httpOnly: true }]);
    const page = await context.newPage();
    const response = await page.goto(origin + process.env.EVENT_SHOP_PATH, { waitUntil: 'networkidle' });
    assert.equal(response.status(), 200);
    assert.equal(await page.getByRole('heading', { name: 'Cosméticos de evento' }).count(), 1);
    assert.equal(await page.getByText('Moldura do evento').count(), 1);
    assert.equal(await page.getByText('25 braseiros').count(), 1);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    assert.ok(overflow <= 1, `largura excede a tela em ${overflow}px`);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'event-shop-mobile.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 1280, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 1);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'event-shop-desktop.png'), fullPage: true });
    }
    await page.getByRole('button', { name: 'Resgatar cosmético' }).click();
    await page.waitForURL(/resgate=\d+/);
    assert.equal(await page.getByRole('status').count(), 1);
    assert.match(await page.getByRole('status').innerText(), /Saldo após o resgate: 15/);
    assert.equal(await page.getByRole('button', { name: 'Resgatar cosmético' }).count(), 0);
    assert.equal(await page.getByText('Você já possui este cosmético.').count(), 1);
    console.log('Loja de evento: resgate móvel concluído uma vez.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
