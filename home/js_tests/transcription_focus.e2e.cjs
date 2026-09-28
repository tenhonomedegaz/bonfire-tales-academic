const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const origin = process.env.TRANSCRIPTION_ORIGIN;
    const context = await browser.newContext();
    context.setDefaultTimeout(15000);
    await context.route('**/*', route => route.request().url().startsWith(origin)
      ? route.continue() : route.abort());
    await context.addCookies([{ name: process.env.TRANSCRIPTION_COOKIE_NAME,
      value: process.env.TRANSCRIPTION_COOKIE_VALUE, url: origin }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const width of [1280, 360]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(origin + process.env.TRANSCRIPTION_WORKSHOP);
      await page.locator('.workshop-book summary').click();
      const quotes = page.locator('[data-workshop-panel="transcription"] [data-transcription-terms]');
      assert.equal(await quotes.count(), 2);
      for (const quote of await quotes.all()) {
        assert.match(await quote.innerText(), /Base: 50 PO/);
        assert.match(await quote.innerText(), /Escola de Foco: Abjuração/);
        assert.match(await quote.innerText(), /Total: 25/);
        assert.equal(await quote.evaluate(element => {
          const box = element.getBoundingClientRect();
          return box.left >= 0 && box.right <= window.innerWidth;
        }), true, 'prévia cabe na largura disponível');
      }
      const artifacts = process.env.BONFIRE_ARTIFACT_DIR;
      if (artifacts) {
        fs.mkdirSync(artifacts, { recursive: true });
        await page.screenshot({ path: path.join(artifacts, `transcription-${width}.png`), fullPage: true });
      }
      await page.goto(origin + process.env.TRANSCRIPTION_SHEET);
      assert.match(await page.locator('.banner-classes').innerText(), /Mago da Guerra/);
      assert.match(await page.locator('[data-transcription-terms]').innerText(), /Escola de Foco: Abjuração/);
      if (artifacts) await page.screenshot({ path: path.join(artifacts, `sheet-${width}.png`), fullPage: true });
      console.log(`Q03: oficina e ficha reais aprovadas em ${width}px`);
    }
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
