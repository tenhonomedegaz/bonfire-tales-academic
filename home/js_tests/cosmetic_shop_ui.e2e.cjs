/* Full storefront templates + real static assets; never creates a transaction. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const root = path.resolve(__dirname, '../..');
  const output = process.env.BONFIRE_ARTIFACT_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-shop-'));
  fs.mkdirSync(output, { recursive: true });
  const fixtures = {};
  const result = spawnSync(process.env.BONFIRE_PYTHON || 'python', ['-c',
      "import json,django; django.setup(); from home.test_cosmetic_shop_ui import browser_fixture; print(json.dumps({mode:browser_fixture(mode) for mode in ('shop','events','empty','status')}))"],
    { cwd: root, encoding: 'utf8', env: { ...process.env, DJANGO_DEBUG: '1', DB_ENGINE: 'postgresql',
      DJANGO_SETTINGS_MODULE: 'bonfire.settings', PYTHONIOENCODING: 'utf-8' } });
  assert.equal(result.status, 0, result.stderr);
  const rendered = JSON.parse(result.stdout);
  for (const mode of ['shop', 'events', 'empty', 'status']) {
    fixtures[mode] = path.join(output, mode + '.html');
    fs.writeFileSync(fixtures[mode], rendered[mode]);
  }
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    for (const width of [360, 1280]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      const errors = [];
      const transactions = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => {
        const request = route.request();
        if (request.method() === 'POST') { transactions.push(request.url()); return route.abort(); }
        if (request.url().startsWith('https://store.invalid/static/')) {
          const relative = decodeURIComponent(new URL(request.url()).pathname.slice('/static/'.length));
          const asset = path.resolve(root, 'home/static', relative);
          assert.ok(asset.startsWith(path.join(root, 'home/static') + path.sep));
          return fs.existsSync(asset) ? route.fulfill({ path: asset }) : route.fulfill({ status: 404, body: '' });
        }
        return request.url().startsWith('file:') ? route.continue() : route.abort();
      });
      for (const mode of ['shop', 'events', 'empty', 'status']) {
        await page.goto(pathToFileURL(fixtures[mode]).href);
        await page.locator('.co-main').waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${mode} ${width}px overflow`);
        const broken = await page.locator('.co-visual img').evaluateAll(images => images.filter(image => image.complete && !image.naturalWidth).length);
        assert.equal(broken, 0);
        if (mode === 'shop' || mode === 'events') {
          const cards = page.locator('[data-co-item]');
          const total = await cards.count();
          await page.locator('[data-co-search]').fill('nao-existe');
          assert.equal(await page.locator('[data-co-item]:visible').count(), 0);
          assert.equal(await page.locator('[data-co-empty]').isVisible(), true);
          await page.locator('[data-co-reset]').first().click();
          assert.equal(await page.locator('[data-co-item]:visible').count(), total);
          await page.locator('[data-co-kind]').selectOption('moldura');
          assert.equal(await page.locator('[data-co-item]:visible:not([data-kind="moldura"])').count(), 0);
          await page.locator('[data-co-reset]').first().click();
          const form = page.locator('form[data-purchase-review]').first();
          await form.locator('button[type=submit]').click();
          assert.equal(await page.locator('#co-review').isVisible(), true);
          assert.ok((await page.locator('[data-co-amount]').innerText()).trim());
          await page.locator('#co-review [data-co-close]').first().click();
          assert.equal(await page.locator('#co-review').isVisible(), false);
          if (mode === 'shop') assert.equal(await form.getAttribute('action'), '/cosmeticos/checkout/');
        }
        await page.evaluate(() => {
          document.activeElement?.blur();
          document.documentElement.style.scrollBehavior = 'auto';
          window.scrollTo({ top: 0, behavior: 'instant' });
        });
        await page.waitForFunction(() => window.scrollY === 0);
        await page.screenshot({ path: path.join(output, `${mode}-${width}.png`), fullPage: true });
      }
      assert.deepEqual(transactions, [], 'QA must not initiate payments or redemptions');
      assert.deepEqual(errors, []);
      await context.close();
      console.log(`${width}px: shop/events/empty/status, filters, review/cancel, forms and layout OK; zero POSTs`);
    }
  } finally { await browser.close(); }
  console.log('Screenshots: ' + output);
})().catch(error => { console.error(error); process.exit(1); });
