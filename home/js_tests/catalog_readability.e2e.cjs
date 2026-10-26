const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require(process.env.BONFIRE_PLAYWRIGHT_MODULE);

(async () => {
  const root = path.resolve(__dirname, '../..');
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'bonfire-catalog-readability-'));
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    for (const kind of ['bestiary', 'organizations']) {
      const render = spawnSync('py', ['-3.14', '-c',
        `import django; django.setup(); from home.test_catalog_readability import browser_fixture; print(browser_fixture('${kind}'))`],
      { cwd: root, encoding: 'utf8', env: { ...process.env, DJANGO_SETTINGS_MODULE: 'bonfire.settings',
        DJANGO_DEBUG: '1', DB_ENGINE: 'postgresql', POSTGRES_URL: '', PYTHONIOENCODING: 'utf-8' } });
      assert.equal(render.status, 0, render.stderr);
      fs.writeFileSync(path.join(output, `${kind}.html`), render.stdout);
      for (const width of [1440, 390]) {
        const page = await browser.newPage({ viewport: { width, height: 1000 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('https://qa.invalid/**', route => {
          const url = new URL(route.request().url());
          if (!url.pathname.startsWith('/static/')) return route.fulfill({ contentType: 'text/html', body: render.stdout });
          const asset = path.resolve(root, 'home/static', decodeURIComponent(url.pathname.slice(8)));
          assert.ok(asset.startsWith(path.join(root, 'home/static') + path.sep));
          return fs.existsSync(asset) ? route.fulfill({ path: asset }) : route.fulfill({ status: 404, body: '' });
        });
        await page.goto(`https://qa.invalid/${kind}/`);
        await page.waitForTimeout(150);
        if (kind === 'organizations') {
          await page.locator('.organization-image img').evaluate(image => image.decode());
          assert.ok(await page.locator('.organization-prose strong').count() > 0, 'Markdown bold rendered');
          assert.equal(await page.locator('.organization-prose script').count(), 0);
          if (width > 1100) {
            const boxes = await page.evaluate(() => {
              const left = document.querySelector('.catalog-sidebar');
              const right = document.querySelector('.catalog-detail');
              return { delta: Math.abs(left.getBoundingClientRect().height - right.getBoundingClientRect().height),
                scrolls: right.scrollHeight > right.clientHeight && getComputedStyle(right).overflowY === 'auto' };
            });
            assert.ok(boxes.delta < 2, 'matching left and right heights');
            assert.ok(boxes.scrolls, 'long prose scrolls inside detail on desktop');
          } else {
            assert.equal(await page.locator('.catalog-detail').evaluate(node => getComputedStyle(node).overflowY), 'visible');
          }
          await page.screenshot({ path: path.join(output, `${kind}-${width}.png`), fullPage: true });
          if (width < 1100) await page.locator('#catalogMobileMenuButton').click();
          await page.locator('.catalog-card[data-slug="companhia-01"]').click();
          assert.match(await page.locator('.detail-title').textContent(), /01/);
          assert.equal(await page.locator('.organization-image img').count(), 0);
        } else {
          assert.equal((await page.locator('.be-list-nd b').allTextContents())[0], '4');
          assert.match(await page.locator('.be-challenge-meta').first().textContent(), /XP 1.100.*PB \+2/);
          const spacing = await page.locator('.be-challenge-meta').first().evaluate(node => {
            const [xp, pb] = node.children;
            return pb.getBoundingClientRect().left - xp.getBoundingClientRect().right;
          });
          assert.ok(spacing >= 9, 'XP and PB are separate fields with visible spacing');
          assert.ok(await page.locator('[data-creature-type="humanoide"]').count());
          await page.screenshot({ path: path.join(output, `${kind}-${width}.png`), fullPage: true });
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `no overflow: ${kind}/${width}`);
        assert.deepEqual(errors, []);
        await page.close();
      }
    }
    console.log(JSON.stringify({ status: 'ok', pages: 2, viewports: [1440, 390], artifacts: output }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
