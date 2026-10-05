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
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const url = process.env.PUBLIC_CHARACTER_ORIGIN + process.env.PUBLIC_CHARACTER_PATH;
    const response = await page.goto(url, { waitUntil: 'networkidle' });
    assert.equal(response.status(), 200);
    assert.equal(await page.locator('h1').innerText(), 'Guardião da Aurora');
    const sheet = page.locator('article.ficha');
    assert.equal(await sheet.evaluate(el => el.classList.contains('theme-ember')), true);
    assert.equal(await sheet.evaluate(el => el.classList.contains('effect-soft-glow')), true);
    assert.equal(await sheet.locator('.banner-character-avatar.frame-gold-trim').count(), 1);
    assert.equal(await sheet.evaluate(el => getComputedStyle(el).getPropertyValue('--sheet-accent').trim()), '#f59e0b');
    assert.equal(await page.getByText('Lenda compartilhada pela jogadora.').count(), 1);
    assert.equal(await page.getByText('Segredo privado da personagem').count(), 0);
    for (const label of ['Atributos públicos', 'Perícias públicas', 'Resumo mecânico público']) {
      assert.equal(await page.getByRole('region', { name: label }).count(), 1);
    }
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'public-character-desktop.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 360, height: 800 });
    await page.waitForTimeout(150);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(overflow <= 1, `largura excede a tela em ${overflow}px`);
    const region = page.getByRole('region', { name: 'Resumo mecânico público' });
    assert.equal(await region.isVisible(), true);
    assert.equal(await sheet.evaluate(el => el.classList.contains('theme-ember')), true);
    assert.match(await region.innerText(), /PV máximo\s+—/);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'public-character-mobile.png'), fullPage: true });
    }
    console.log('Ficha pública: desktop e celular sem dados privados nem overflow.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
