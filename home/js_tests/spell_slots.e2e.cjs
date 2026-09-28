const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const started = Date.now();
  const trace = stage => console.log(`[slots-e2e ${Date.now() - started}ms] ${stage}`);
  const origin = process.env.SLOTS_E2E_ORIGIN;
  const url = origin + process.env.SLOTS_E2E_PATH;
  const browser = await chromium.launch({ headless: true });
  trace('browser aberto');
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    context.setDefaultTimeout(15000);
    context.setDefaultNavigationTimeout(15000);
    await context.route('**/*', route => route.request().url().startsWith(origin)
      ? route.continue() : route.abort());
    await context.addCookies([{ name: process.env.SLOTS_E2E_COOKIE_NAME,
      value: process.env.SLOTS_E2E_COOKIE_VALUE, url: origin }]);
    const page = await context.newPage();
    const other = await context.newPage();
    const errors = [];
    for (const tab of [page, other]) tab.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await other.goto(url);
    trace('duas fichas carregadas');
    const card = tab => tab.locator('[data-spell-slot-card][data-slot-level="1"]');
    const number = tab => card(tab).locator('[data-slot-atual]').innerText();
    const circleNumber = tab => tab.locator('[data-slot-summary="1"]').innerText();
    async function command(tab, action, status) {
      const responsePromise = tab.waitForResponse(response =>
        response.request().method() === 'POST' && response.url().includes('/usar-slot-magia/'));
      await card(tab).locator(`[data-slot-action="${action}"]`).click();
      const response = await responsePromise;
      assert.equal(response.status(), status);
      await card(tab).locator('[data-spell-slot-feedback]').filter({ hasText: /atualizados|mudaram/ }).waitFor();
      await tab.waitForFunction(() => document.querySelector('[data-slot-level="1"]').getAttribute('aria-busy') === 'false');
      assert.equal(tab.url(), url, 'comando preserva aba e URL');
      trace(`${action}: HTTP ${status}`);
      return response.json();
    }
    assert.equal(await number(page), '2');
    const first = await command(page, 'gastar', 200);
    assert.equal(first.slot.atual, 1);
    assert.equal(await number(page), '1');
    assert.equal(await circleNumber(page), '1/2', 'círculo e cartão usam o mesmo snapshot');
    const stale = await command(other, 'gastar', 409);
    assert.equal(stale.code, 'stale_version');
    assert.equal(await number(other), '1');
    assert.equal(await circleNumber(other), '1/2', 'conflito atualiza também o círculo');
    await command(page, 'desfazer', 200);
    assert.equal(await number(page), '2');
    assert.equal(await circleNumber(page), '2/2');
    const artifacts = process.env.BONFIRE_ARTIFACT_DIR;
    if (artifacts) {
      trace('início das capturas');
      fs.mkdirSync(artifacts, { recursive: true });
      await page.screenshot({ path: path.join(artifacts, 'slots-desktop.png'), fullPage: true });
      await page.setViewportSize({ width: 360, height: 800 });
      await page.screenshot({ path: path.join(artifacts, 'slots-mobile.png'), fullPage: true });
      await other.screenshot({ path: path.join(artifacts, 'slots-conflict.png'), fullPage: true });
      trace('capturas concluídas');
    }
    assert.equal(await card(page).evaluate(element => {
      const box = element.getBoundingClientRect();
      return Array.from(element.querySelectorAll('button, [data-spell-slot-feedback]'))
        .filter(child => !child.hidden).every(child => {
          const rect = child.getBoundingClientRect();
          return rect.left >= box.left && rect.right <= box.right;
        });
    }), true, 'mensagem e botões cabem no cartão móvel');
    await page.reload();
    trace('reload concluído');
    assert.equal(await number(page), '2');
    // Alternativa HTML: impede apenas carregar o cliente parcial, mantém os demais scripts.
    const legacy = await context.newPage();
    await legacy.route('**/js/spell_slots.js*', route => route.abort());
    await legacy.goto(url);
    trace('formulário HTML carregado');
    await Promise.all([
      legacy.waitForNavigation({ waitUntil: 'load' }),
      card(legacy).locator('[data-slot-action="gastar"]').click(),
    ]);
    assert.equal(await number(legacy), '1');
    assert.equal(legacy.url(), url, 'fallback HTML preserva a URL da aba');
    trace('formulário HTML confirmado');
    assert.deepEqual(errors, []);
  } finally {
    trace('fechando browser');
    await browser.close();
    trace('browser fechado');
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
