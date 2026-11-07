/* Real discovery templates/assets with a read-only account fixture; zero transactions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const root = path.resolve(__dirname, '../..');
  const result = spawnSync(process.env.BONFIRE_PYTHON || 'python', ['-c',
    "import json,django; django.setup(); from home.test_cosmetic_discovery import browser_fixture; print(json.dumps({'all':browser_fixture(),'filtered':browser_fixture({'q':'gelo'})}))"],
  { cwd: root, encoding: 'utf8', env: { ...process.env, DJANGO_DEBUG: '1', DB_ENGINE: 'postgresql',
    DJANGO_SETTINGS_MODULE: 'bonfire.settings', PYTHONIOENCODING: 'utf-8' } });
  assert.equal(result.status, 0, result.stderr);
  const rendered = JSON.parse(result.stdout);
  const output = process.env.BONFIRE_ARTIFACT_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-discovery-'));
  fs.mkdirSync(output, { recursive: true });
  for (const [key, html] of Object.entries(rendered)) fs.writeFileSync(path.join(output, key + '.html'), html);
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const missing = new Set();
  let posts = 0;
  async function assets(context) {
    await context.route('**/*', route => {
      const request = route.request();
      if (request.method() !== 'GET') { posts++; return route.abort(); }
      if (request.url().startsWith('https://discovery.invalid/static/')) {
        const relative = decodeURIComponent(new URL(request.url()).pathname.slice('/static/'.length));
        const file = path.resolve(root, 'home/static', relative);
        assert.ok(file.startsWith(path.join(root, 'home/static') + path.sep));
        if (!fs.existsSync(file)) { missing.add(relative); return route.fulfill({ status: 404, body: '' }); }
        return route.fulfill({ path: file });
      }
      return request.url().startsWith('file:') ? route.continue() : route.abort();
    });
  }
  try {
    for (const width of [360, 1280]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      await assets(context);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(pathToFileURL(path.join(output, 'all.html')).href);
      const cards = page.locator('[data-discovery-card]');
      const shown = () => page.locator('[data-discovery-card]:visible').count();
      assert.equal(await cards.count(), 20);
      assert.equal(await shown(), 20);
      const form = page.locator('[data-discovery-filters]');
      await form.locator('[name=q]').fill('TRANCA');
      assert.equal(await shown(), 1);
      await form.locator('[name=q]').fill('moldura-frost');
      assert.equal(await shown(), 1);
      await form.locator('[name=q]').fill('');
      await form.locator('[name=colecao]').selectOption('classicos');
      assert.equal(await shown(), 3);
      await page.locator('[data-discovery-reset]').click();
      await form.locator('[name=colecao]').selectOption('luas');
      await form.locator('[name=tipo]').selectOption('moldura');
      assert.equal(await shown(), 3);
      await page.locator('[data-discovery-reset]').click();
      await form.locator('[name=estado]').selectOption('preparacao');
      assert.equal(await shown(), 8);
      assert.equal(await page.locator('[data-discovery-card]:visible .discovery-actions a').count(), 0);
      assert.equal(await page.locator('[data-discovery-card]:visible form').count(), 0);
      const proposal = page.locator('#discovery-moldura-lua-vermelha');
      await page.evaluate(() => {
        const mount = window.CosmeticRenderer.mount;
        window.discoveryMountCalls = 0;
        window.CosmeticRenderer.mount = root => { window.discoveryMountCalls++; return mount(root); };
      });
      await proposal.locator('[data-discovery-preview]').click();
      const dialog = page.locator('[data-discovery-dialog]');
      assert.equal(await dialog.isVisible(), true);
      assert.equal(await page.evaluate(() => window.discoveryMountCalls), 1);
      assert.match(await dialog.innerText(), /obtenção ainda não publicada/);
      assert.equal(await dialog.locator('a,form').count(), 0);
      for (const image of await dialog.locator('img').all()) await image.evaluate(image => image.decode());
      await page.screenshot({ path: path.join(output, `preview-${width}.png`) });
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(), false);
      await page.locator('[data-discovery-reset]').click();
      await form.locator('[name=estado]').selectOption('suspenso');
      assert.equal(await shown(), 1);
      assert.equal(await page.locator('[data-discovery-card]:visible .discovery-actions a').count(), 0);
      await form.locator('[name=q]').fill('nothing-matches');
      assert.equal(await page.locator('[data-discovery-empty]').isVisible(), true);
      await page.locator('[data-discovery-reset]').click();
      const eventLink = page.locator('#discovery-badge-beta .discovery-actions a');
      assert.equal(await eventLink.getAttribute('href'), '/cosmeticos/eventos/#event-offer-1');
      for (const image of await cards.locator('img').all()) {
        await image.evaluate(async image => { image.loading = 'eager'; await image.decode(); });
      }
      const layout = await page.evaluate(() => ({
        fits: document.documentElement.scrollWidth <= innerWidth + 1,
        clear: [...document.querySelectorAll('[data-discovery-card]')].every(card =>
          card.querySelector('.discovery-art').getBoundingClientRect().bottom <=
          card.querySelector('.discovery-card-body').getBoundingClientRect().top + 1),
        noTransactions: [...document.querySelectorAll('main form')].every(form => form.method === 'get'),
      }));
      assert.deepEqual(layout, { fits: true, clear: true, noTransactions: true });
      await page.evaluate(() => { document.activeElement?.blur(); document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo({ top: 0, behavior: 'instant' }); });
      await page.screenshot({ path: path.join(output, `discovery-${width}.png`), fullPage: true });
      assert.deepEqual(errors, []);
      await context.close();
      console.log(`${width}px: all published/unowned, 8 proposals, legacy search, filters, modal, media, locks and layout OK`);
    }
    const nojs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 360, height: 900 } });
    await assets(nojs);
    const page = await nojs.newPage();
    await page.goto(pathToFileURL(path.join(output, 'filtered.html')).href);
    assert.equal(await page.locator('[data-discovery-card]:visible').count(), 1);
    assert.equal(await page.locator('#discovery-moldura-frost').isVisible(), true);
    assert.equal(await page.locator('[data-discovery-filters]').getAttribute('method'), 'get');
    assert.equal(await page.locator('[data-discovery-preview]:visible').count(), 0);
    await nojs.close();
    assert.equal(posts, 0);
    assert.deepEqual([...missing], []);
    console.log('No-JS server filtering OK; zero POSTs; all local assets present. Screenshots: ' + output);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
