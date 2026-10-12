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
    await page.setViewportSize({ width: 640, height: 900 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    const enlargedOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(enlargedOverflow <= 1, `texto ampliado excede a tela em ${enlargedOverflow}px`);
    assert.equal(await page.locator('h1').isVisible(), true);
    assert.equal(await region.isVisible(), true);
    const skillLabels = page.getByRole('region', { name: 'Perícias públicas' }).locator('dt');
    const overflowingSkills = await skillLabels.evaluateAll(labels => labels
      .filter(label => label.scrollWidth - label.clientWidth > 1)
      .map(label => label.textContent.trim()));
    assert.deepEqual(overflowingSkills, [], `perícias sobrepostas: ${overflowingSkills.join(', ')}`);
    assert.equal(await page.getByText('Segredo privado da personagem').count(), 0);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'public-character-enlarged-text.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 360, height: 800 });
    const longResponse = await page.goto(process.env.PUBLIC_CHARACTER_ORIGIN + process.env.PUBLIC_CHARACTER_LONG_PATH,
      { waitUntil: 'networkidle' });
    assert.equal(longResponse.status(), 200);
    const longTitle = page.locator('article.ficha h1');
    const longDescription = page.getByRole('region', { name: 'Descrição pública' }).locator('p');
    for (const [label, element] of [['nome', longTitle], ['descrição', longDescription]]) {
      const overflow = await element.evaluate(node => node.scrollWidth - node.clientWidth);
      assert.ok(overflow <= 1, `${label} longo excede seu bloco em ${overflow}px`);
    }
    const longPageOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(longPageOverflow <= 1, `ficha de texto longo excede a tela em ${longPageOverflow}px`);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'public-character-long-text.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 640, height: 900 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    for (const [label, element] of [['nome', longTitle], ['descrição', longDescription]]) {
      const overflow = await element.evaluate(node => node.scrollWidth - node.clientWidth);
      assert.ok(overflow <= 1, `${label} longo com texto ampliado excede seu bloco em ${overflow}px`);
    }
    const longEnlargedOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(longEnlargedOverflow <= 1, `ficha longa com texto ampliado excede a tela em ${longEnlargedOverflow}px`);
    await page.setViewportSize({ width: 1280, height: 900 });
    const playersResponse = await page.goto(process.env.PUBLIC_CHARACTER_ORIGIN + process.env.PUBLIC_CHARACTER_PLAYERS_PATH,
      { waitUntil: 'networkidle' });
    assert.equal(playersResponse.status(), 200);
    const ownerCard = page.locator('.player-card').filter({ hasText: 'public-browser-owner' });
    assert.equal(await ownerCard.count(), 1);
    assert.match(await ownerCard.locator('.player-card-count').textContent(), /2 personagens públicos/);
    assert.equal(await ownerCard.getByText('Segredo visual privado').count(), 0);
    assert.equal(await ownerCard.locator(`a[href="${process.env.PUBLIC_CHARACTER_PATH}"]`).count(), 1);
    assert.ok(await ownerCard.isVisible());
    const desktopPlayersOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(desktopPlayersOverflow <= 1, `vitrine desktop excede a tela em ${desktopPlayersOverflow}px`);
    await page.setViewportSize({ width: 360, height: 800 });
    const playersOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(playersOverflow <= 1, `vitrine excede a tela em ${playersOverflow}px`);
    const clippedNames = await ownerCard.locator('.player-card-characters strong').evaluateAll(names => names
      .filter(name => name.scrollWidth - name.clientWidth > 1)
      .map(name => name.textContent.trim()));
    assert.deepEqual(clippedNames, [], `nomes de personagens cortados: ${clippedNames.join(', ')}`);
    if (process.env.BONFIRE_ARTIFACT_DIR) {
      await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR, 'public-players-mobile.png'), fullPage: true });
    }
    await ownerCard.locator(`a[href="${process.env.PUBLIC_CHARACTER_PATH}"]`).click();
    await page.waitForURL(`**${process.env.PUBLIC_CHARACTER_PATH}`);
    assert.equal(await page.locator('article.ficha h1').count(), 1);
    assert.equal(await page.getByText('Segredo visual privado').count(), 0);
    console.log('Ficha pública: desktop, celular e texto ampliado sem dados privados nem overflow.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
