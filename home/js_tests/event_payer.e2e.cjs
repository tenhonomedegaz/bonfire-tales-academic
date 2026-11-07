/* Payer radios and legacy select review; POSTs are captured locally, never sent to a server. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const root = path.resolve(__dirname, '../..');
  const render = spawnSync(process.env.BONFIRE_PYTHON || 'python', ['-c',
    "import json,django; django.setup(); from home.test_event_payer import browser_fixture; print(json.dumps({'events':browser_fixture(),'legacy':browser_fixture('legacy')}))"],
  { cwd: root, encoding: 'utf8', env: { ...process.env, DJANGO_DEBUG: '1', DB_ENGINE: 'postgresql',
    DJANGO_SETTINGS_MODULE: 'bonfire.settings', PYTHONIOENCODING: 'utf-8' } });
  assert.equal(render.status, 0, render.stderr);
  const fixtures = JSON.parse(render.stdout);
  const output = process.env.BONFIRE_ARTIFACT_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-payer-'));
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    for (const width of [360, 1280]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const posts = [];
      let current = 'events';
      await context.route('**/*', route => {
        const request = route.request();
        if (request.method() === 'POST') {
          posts.push({ url: request.url(), data: Object.fromEntries(new URLSearchParams(request.postData())) });
          return route.fulfill({ contentType: 'text/html', body: '<p>Captured locally</p>' });
        }
        if (request.url().startsWith('https://payer.invalid/static/')) {
          const relative = decodeURIComponent(new URL(request.url()).pathname.slice('/static/'.length));
          const asset = path.resolve(root, 'home/static', relative);
          assert.ok(asset.startsWith(path.join(root, 'home/static') + path.sep));
          return route.fulfill({ path: asset });
        }
        if (request.url().startsWith('https://payer.invalid/')) return route.fulfill({ contentType: 'text/html', body: fixtures[current] });
        return route.abort();
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('https://payer.invalid/eventos/');
      const first = page.locator('#event-offer-1 form');
      const second = page.locator('#event-offer-2 form');
      const before = await first.evaluate(form => Object.fromEntries(new FormData(form)));
      await first.locator('[name=character][value="8"]').check();
      assert.equal(posts.length, 0, 'selection must never submit');
      assert.equal(await second.locator('[name=character][value="7"]').isChecked(), true, 'forms own independent radio groups');
      const selected = await first.evaluate(form => Object.fromEntries(new FormData(form)));
      assert.equal(selected.character, '8');
      for (const key of ['offer', 'quoted_cost', 'request_id', 'csrfmiddlewaretoken']) assert.equal(selected[key], before[key]);
      await first.locator('[name=character][value="7"]').focus();
      await page.keyboard.press('ArrowRight');
      assert.equal(await first.locator('[name=character][value="8"]').isChecked(), true);
      await first.locator('button[type=submit]').click();
      const dialog = page.locator('#co-review');
      assert.equal(await dialog.isVisible(), true);
      assert.match(await dialog.locator('[data-co-note]').innerText(), /Darian das Montanhas do Norte · 50 braseiros/);
      assert.equal(posts.length, 0, 'opening review must never submit');
      await page.screenshot({ path: path.join(output, `review-${width}.png`) });
      await dialog.locator('[data-co-close]').first().click();
      assert.equal(posts.length, 0, 'cancel must never submit');
      const free = page.locator('#event-offer-3 form');
      assert.equal(await free.locator('[name=character]').count(), 0);
      await free.locator('button[type=submit]').click();
      assert.equal(await dialog.locator('[data-co-note]').innerText().then(text => text.includes('Personagem:')), false);
      await page.keyboard.press('Escape');
      const image = first.locator('[data-payer-avatar]');
      await image.evaluate(image => image.dispatchEvent(new Event('error')));
      assert.equal(await image.isVisible(), false, 'broken avatar exposes initial fallback');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      assert.equal(await page.locator('#event-offer-4 form').count(), 0);
      await page.evaluate(() => { document.activeElement?.blur(); document.documentElement.style.scrollBehavior='auto'; window.scrollTo({top:0,behavior:'instant'}); });
      await page.screenshot({ path: path.join(output, `payers-${width}.png`), fullPage: true });
      await first.locator('button[type=submit]').click();
      await Promise.all([page.waitForURL(url => url.pathname === '/eventos/'), dialog.locator('[data-co-proceed]').click()]);
      assert.equal(posts.length, 1, 'only confirmation submits once');
      assert.equal(posts[0].data.character, '8');
      for (const key of ['offer', 'quoted_cost', 'request_id', 'csrfmiddlewaretoken']) assert.equal(posts[0].data[key], before[key]);

      current = 'legacy';
      await page.goto('https://payer.invalid/legacy/');
      await page.locator('#legacy select').selectOption('8');
      await page.locator('#legacy button').click();
      assert.match(await page.locator('[data-co-note]').innerText(), /Darian · 50 braseiros/);
      await page.locator('#co-review [data-co-close]').first().click();
      await page.locator('#cash button').click();
      assert.equal(await page.locator('[data-co-proceed]').innerText(), 'Continuar para o Asaas');
      assert.equal(await page.locator('[data-co-note]').innerText().then(text => text.includes('Personagem:')), false);
      await page.locator('#co-review [data-co-close]').first().click();
      await page.locator('#readonly button').click();
      assert.equal(await page.locator('[data-co-proceed]').isDisabled(), true);
      assert.equal(posts.length, 1);
      assert.deepEqual(errors, []);
      await context.close();
      console.log(`${width}px: radio keyboard/groups, no-spend selection/cancel, exact confirmed POST, free/insufficient, avatar fallback, legacy select/cash/readonly OK`);
    }
    const nojs = await browser.newContext({ javaScriptEnabled: false });
    await nojs.route('**/*', route => route.request().url() === 'https://payer.invalid/eventos/'
      ? route.fulfill({ contentType:'text/html', body:fixtures.events }) : route.abort());
    const page = await nojs.newPage();
    await page.goto('https://payer.invalid/eventos/');
    await page.locator('#event-offer-1 [name=character][value="8"]').check();
    assert.equal(await page.locator('#event-offer-1 form').evaluate(form => new FormData(form).get('character')), '8');
    await nojs.close();
    console.log('Native no-JS radio POST contract OK. Screenshots: ' + output);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
