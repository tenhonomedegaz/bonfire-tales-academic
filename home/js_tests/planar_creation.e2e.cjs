const assert = require('node:assert/strict');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);
(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH
      ? {executablePath: process.env.BONFIRE_CHROMIUM_EXECUTABLE_PATH}
      : {channel: 'msedge'})});
  try {
    const context = await browser.newContext();
    const origin = process.env.PATHBUILDER_E2E_URL;
    await context.addCookies([{name: process.env.PATHBUILDER_E2E_COOKIE_NAME,
      value: process.env.PATHBUILDER_E2E_COOKIE_VALUE, url: origin}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(origin + '/sistemas/criacao-de-ficha/');
    if (await page.locator('#cf-raca').count() !== 1) {
      throw new Error(`Criador não abriu: HTTP ${response.status()}, URL ${page.url()}, ` +
        `título ${await page.title()}`);
    }
    // Select identity while leaving unrelated creation steps untouched.
    await page.locator('#cf-raca').selectOption('anao', {force: true});
    await page.locator('#cf-essencia').selectOption('nephilim', {force: true});
    for (const [kind, value] of [['polo', 'celestial'], ['energia', 'lumen'], ['elemento', 'fogo']]) {
      const group = page.locator(`[data-racial-menu="${kind}"]`);
      assert.equal(await group.count(), 1);
      await group.locator(`input[value="${value}"]`).evaluate(input => input.click());
      assert.equal(await group.locator('input:checked').count(), 1);
      assert.equal(await group.locator('input:not(:checked):enabled').count(), 0);
    }
    assert.deepEqual(errors, []);
    console.log('Q15: three level-one menus rendered; selection limits enforced; no JS errors.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
