/* Full Django-rendered owner and public profile visual acceptance. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const base = process.env.ACHIEVEMENT_E2E_BASE_URL;
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH } : {}) });
  try {
    const owner = await browser.newContext({ viewport: { width: 360, height: 800 } });
    await owner.addCookies([{ name: process.env.ACHIEVEMENT_E2E_COOKIE_NAME,
      value: process.env.ACHIEVEMENT_E2E_COOKIE_VALUE, url: base }]);
    const publicContext = await browser.newContext({ viewport: { width: 360, height: 800 } });
    const pages = [
      { label: 'owner', page: await owner.newPage(), url: process.env.ACHIEVEMENT_E2E_OWNER_PATH },
      { label: 'public', page: await publicContext.newPage(), url: process.env.ACHIEVEMENT_E2E_PUBLIC_PATH },
    ];
    const ownerPage = pages[0].page;
    await ownerPage.goto(base + process.env.ACHIEVEMENT_E2E_INBOX_PATH);
    const notice = ownerPage.locator('.cronica-inbox-action').filter({ hasText: 'Jornada Iniciada' });
    await notice.click();
    assert.ok(ownerPage.url().endsWith('#conquista-visual-earned'), 'unread notice targets its achievement');
    await ownerPage.locator('#conquista-visual-earned details[open]').waitFor();
    await ownerPage.goto(base + process.env.ACHIEVEMENT_E2E_INBOX_PATH);
    assert.equal(await ownerPage.locator('.cronica-inbox-item.is-unread').count(), 0);
    await notice.click();
    assert.ok(ownerPage.url().endsWith('#conquista-visual-earned'), 'read notice keeps its target');
    await ownerPage.locator('#conquista-visual-earned details[open]').waitFor();
    for (const { label, page, url } of pages) {
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const response = await page.goto(base + url, { waitUntil: 'domcontentloaded' });
      assert.equal(response.status(), 200, `${label} HTTP status`);
      const selector = label === 'owner' ? '#conquistas .conquista-grid' :
        '.public-profile-section .conquista-grid';
      const cards = page.locator(`${selector} .conquista-item`);
      assert.ok(await cards.count() >= 2, `${label} shows the earned and locked achievements`);
      const earned = cards.filter({ hasText: 'Jornada Iniciada' });
      const locked = cards.filter({ hasText: 'Jornada Seguinte' });
      assert.equal(await earned.count(), 1);
      assert.equal(await locked.count(), 1);
      await earned.locator('summary').focus();
      await page.keyboard.press('Enter');
      assert.equal(await earned.locator('.conquista-info-body').isVisible(), true);
      assert.match(await earned.innerText(), /Primeiro feito confirmado/);
      await locked.locator('summary').click();
      assert.equal(await locked.locator('.conquista-info-body').isVisible(), true);
      for (const width of [360, 768, 1280]) {
        await page.setViewportSize({ width, height: 800 });
        const size = await page.evaluate(selector => ({ width: innerWidth,
          scroll: document.documentElement.scrollWidth,
          cards: [...document.querySelectorAll(`${selector} .conquista-item`)]
            .map(card => card.getBoundingClientRect().right) }), selector);
        assert.ok(size.scroll <= size.width, `${label} has horizontal overflow at ${width}: ${JSON.stringify(size)}`);
        assert.ok(size.cards.every(right => right <= width), `${label} cards fit ${width}`);
        if (process.env.BONFIRE_ARTIFACT_DIR) {
          await page.evaluate(() => scrollTo(0, 0));
          fs.mkdirSync(process.env.BONFIRE_ARTIFACT_DIR, { recursive: true });
          await page.screenshot({ path: path.join(process.env.BONFIRE_ARTIFACT_DIR,
            `achievement-${label}-${width}.png`), fullPage: true });
        }
      }
      await page.setViewportSize({ width: 360, height: 800 });
      await page.evaluate(() => { document.body.style.zoom = '2'; });
      const zoom = await page.evaluate(() => ({ width: innerWidth,
        scroll: document.documentElement.scrollWidth }));
      assert.ok(zoom.scroll <= zoom.width, `${label} has horizontal overflow at 200%: ${JSON.stringify(zoom)}`);
      assert.deepEqual(errors, [], `${label} JavaScript errors`);
    }
    assert.equal(await pages[1].page.locator('.conquista-evidencias').count(), 0,
      'visitor receives no private achievement proof');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
